"""PIH 运营者 CLI（S3.2.1 用户闭环 + Sprint 3 store 落库查询 + Sprint 4 process 批处理 + Sprint 6 事件聚类）。

命令：
  pih probe-source <id> | --all   试抓取验证（robots→列表→详情→快照），产出成败报告
  pih collect <id>                正式采集（enabled 门控）+ 默认落库（--no-ingest 回退）
  pih process [--source-id=<id>]  批处理 pending 条目：粗筛→抽取→校验，写回结构化字段 + 事件聚类
  pih query [筛选条件]            查询库中情报（--id 详情 / --source-id/--subject/
                                  --event-type/--tag 结构化筛选，Sprint 4）
  pih verify list                 列出已具备升级条件的事件（人工核实队列，Sprint 6 S3.1.1 子集）
  pih verify confirm <event_id>   跃迁 single_source → confirmed（人工终态）
  pih verify refute <event_id> --reason="..."  跃迁 → refuted（人工终态，必填理由）
  pih cluster --backfill          对存量 extracted 但未挂事件的条目跑聚类回填

退出码：0 成功 / 1 抓取失败或门控拒绝 / 2 用法或环境错误。
环境：从 cwd 的 .env 读取 MinIO、PG 与 LLM 凭据（python-dotenv）。
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from minio import Minio

import pih.collect.adapters  # noqa: F401  触发内置适配器注册
from pih.collect.base import SourceConfig
from pih.collect.httpclient import HttpClient
from pih.collect.probe import NullSnapshotStore, ProbeReport, probe_source
from pih.collect.run import SourceDisabledError, collect_source
from pih.collect.snapshot import BUCKET, SnapshotStore
from pih.domainpacks.errors import LoadError
from pih.domainpacks.loader import DEFAULT_PACK_DIR, load
from pih.envs import load_env
from pih.process.event import STATUS_LABELS, EventService
from pih.process.llm import LLMConfigError
from pih.process.run import ProcessRunner
from pih.store.db import close_pool, get_pool
from pih.store.event_repository import EventRepository
from pih.store.repository import IntelRepository, SaveOutcome
from pih.store.source_sync import sync_sources

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pih",
        description="PIH 产品情报中心——运营者 CLI（信源试抓取与采集门控）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    pp = sub.add_parser(
        "probe-source",
        help="试抓取验证：robots → 列表页 → 详情 → 快照，产出成败报告（S3.2.1 AC1）",
    )
    pp.add_argument("source_id", nargs="?", default=None, help="信源 id（与 --all 二选一）")
    pp.add_argument("--all", action="store_true", help="对领域包全部信源逐一试抓取")
    pp.add_argument("--details", type=int, default=1, help="试抓详情条数（默认 1）")
    pp.add_argument("--no-snapshot", action="store_true", help="不落 MinIO 快照（快速可达性验证）")
    pp.add_argument(
        "--proxy-env", action="store_true",
        help="继承环境代理变量（默认不继承；socks 代理需自装 socksio）",
    )
    pp.add_argument(
        "--pack", default=None,
        help="领域包 YAML 路径（默认 ./domain_packs/construction_machinery/pack.yaml）",
    )

    cp = sub.add_parser(
        "collect",
        help="正式采集单源（enabled 门控：仅运行领域包中 enabled: true 的信源）+ 默认落库",
    )
    cp.add_argument("source_id", help="信源 id")
    cp.add_argument("--max-items", type=int, default=10, help="单次采集详情条数上限（默认 10）")
    cp.add_argument(
        "--no-ingest",
        action="store_true",
        help="不落库，仅 stdout 摘要（Sprint 2 行为）",
    )
    cp.add_argument("--proxy-env", action="store_true", help="继承环境代理变量（默认不继承）")
    cp.add_argument("--pack", default=None, help="领域包 YAML 路径（默认同 probe-source）")

    qp = sub.add_parser(
        "query",
        help="查询情报库（Sprint 4：结构化筛选；--id 单条详情）",
    )
    qp.add_argument("--source-id", default=None, help="按信源过滤")
    qp.add_argument("--subject", default=None, help="按主体过滤（精确匹配，Sprint 4）")
    qp.add_argument("--event-type", default=None, help="按事件类型过滤（精确匹配，Sprint 4）")
    qp.add_argument("--tag", default=None, help="按标签过滤（JSONB containment，Sprint 4）")
    qp.add_argument("--limit", type=int, default=10, help="返回条数上限（默认 10）")
    qp.add_argument(
        "--before",
        default=None,
        help="只返回 fetched_at 早于此时间的条目（ISO8601；仅与 --source-id 组合生效）",
    )
    qp.add_argument("--id", type=int, default=None, help="按 intel_item.id 查单条详情")
    qp.add_argument("--pack", default=None, help="领域包 YAML 路径（默认同 probe-source）")

    prp = sub.add_parser(
        "process",
        help="批处理 pending 条目：粗筛→抽取→校验（LangGraph），写回结构化字段与状态（Sprint 4）",
    )
    prp.add_argument("--source-id", default=None, help="仅处理该信源的 pending 条目")
    prp.add_argument("--limit", type=int, default=20, help="单次处理条数上限（默认 20）")
    prp.add_argument("--pack", default=None, help="领域包 YAML 路径（默认同 probe-source）")

    # ---- Sprint 6 事件聚类 ----
    vp = sub.add_parser(
        "verify",
        help="人工核实队列（Sprint 6 S3.1.1 子集）：列出已具备升级条件的事件，确认/证伪终态跃迁",
    )
    vsub = vp.add_subparsers(dest="verify_action", required=True)
    vsub.add_parser("list", help="列出已具备升级条件的事件（ready_for_manual=TRUE）")
    vc = vsub.add_parser("confirm", help="单源确认 → 多源确认（人工终态）")
    vc.add_argument("event_id", type=int, help="event.id")
    vc.add_argument("--operator", default="operator", help="操作人标识（默认 operator）")
    vr = vsub.add_parser("refute", help="证伪（人工终态，必填理由）")
    vr.add_argument("event_id", type=int, help="event.id")
    vr.add_argument("--reason", required=True, help="证伪理由（必填）")
    vr.add_argument("--operator", default="operator", help="操作人标识（默认 operator）")

    clp = sub.add_parser(
        "cluster",
        help="事件聚类（Sprint 6 S4.2.2）：在线已在 process 内触发，本命令用于历史回填",
    )
    clp.add_argument(
        "--backfill", action="store_true",
        help="对 extracted 但 event_id IS NULL 的存量条目按 fetched_at ASC 逐条聚类",
    )
    clp.add_argument("--source-id", default=None, help="仅回填该信源")
    clp.add_argument("--limit", type=int, default=200, help="单次回填条数上限（默认 200）")
    clp.add_argument("--pack", default=None, help="领域包 YAML 路径（默认同 probe-source）")

    return parser


def _default_pack() -> Path:
    cwd_pack = Path("domain_packs/construction_machinery/pack.yaml")
    if cwd_pack.exists():
        return cwd_pack
    return DEFAULT_PACK_DIR / "construction_machinery" / "pack.yaml"


def _load_pack(pack_arg: str | None) -> tuple[list[SourceConfig], str]:
    """加载领域包，返回 (sources, domain_id)。"""
    path = Path(pack_arg) if pack_arg else _default_pack()
    pack = load(path)
    sources = [SourceConfig.from_dict(d) for d in pack["sources"]]
    domain_id = pack["meta"]["domain_id"]
    return sources, domain_id


def _load_sources(pack_arg: str | None) -> list[SourceConfig]:
    """保留旧入口（probe 用），仅返回 sources。"""
    sources, _ = _load_pack(pack_arg)
    return sources


def _make_snapshot_store(no_snapshot: bool) -> SnapshotStore | NullSnapshotStore | None:
    if no_snapshot:
        return NullSnapshotStore()
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    client = Minio(
        endpoint,
        access_key=os.environ.get("MINIO_ROOT_USER", "pih"),
        secret_key=os.environ.get("MINIO_ROOT_PASSWORD", "pih12345"),
        secure=False,
    )
    try:
        client.bucket_exists(BUCKET)
    except Exception as exc:
        print(
            f"MinIO 不可达（{endpoint}）：{type(exc).__name__}。"
            f"请先 docker compose up -d，或加 --no-snapshot 跳过快照。",
            file=sys.stderr,
        )
        return None
    return SnapshotStore(client)


def _print_probe_report(report: ProbeReport, source: SourceConfig) -> None:
    flag = "true" if source.enabled else "false"
    print(f"== 试抓取：{source.id}（{source.name}，enabled={flag}）==")
    print(f"robots  : {'允许' if report.robots_allowed else '拒绝'}——{report.robots_note}")
    print(f"列表页  : {'✓' if report.list_ok else '✗'} {report.list_note or '（未执行）'}")
    for i, d in enumerate(report.detail_results, 1):
        if d.ok:
            print(f"详情 {i}  : ✓「{d.title}」 快照 {d.snapshot_id[:12]}…")
        else:
            print(f"详情 {i}  : ✗ {d.note}")
    if report.success:
        if source.enabled:
            print("结论    : ✓ 试抓取通过")
        else:
            print("结论    : ✓ 试抓取通过；信源未启用——可将领域包 YAML 中该源 enabled 置 true")
    else:
        print("结论    : ✗ 试抓取未通过")
    print()


def _cmd_probe(args: argparse.Namespace) -> int:
    if bool(args.source_id) == args.all:
        print("须指定 source_id 或 --all 之一", file=sys.stderr)
        return EXIT_USAGE
    sources = _load_sources(args.pack)
    by_id = {s.id: s for s in sources}
    if args.all:
        targets = sources
    else:
        if args.source_id not in by_id:
            print(f"未知信源 id：{args.source_id}（可用：{', '.join(by_id)}）", file=sys.stderr)
            return EXIT_USAGE
        targets = [by_id[args.source_id]]

    snapshots = _make_snapshot_store(args.no_snapshot)
    if snapshots is None:
        return EXIT_USAGE
    http = HttpClient(trust_env=args.proxy_env)
    failures = 0
    try:
        for source in targets:
            try:
                report = probe_source(source, http, snapshots, details=args.details)
            except KeyError as exc:
                print(f"== 试抓取：{source.id}（{source.name}）==\n结论    : ✗ {exc}\n")
                failures += 1
                continue
            except NotImplementedError:
                print(
                    f"== 试抓取：{source.id}（{source.name}）==\n"
                    f"结论    : ✗ 该源暂无特化适配器（type={source.type} 的通用基类"
                    f"不含 {source.id} 的解析钩子），待适配器接入后再试\n"
                )
                failures += 1
                continue
            _print_probe_report(report, source)
            if not report.success:
                failures += 1
    finally:
        http.close()
    return EXIT_OK if failures == 0 else EXIT_FAILED


def _cmd_collect(args: argparse.Namespace) -> int:
    sources, domain_id = _load_pack(args.pack)
    by_id = {s.id: s for s in sources}
    if args.source_id not in by_id:
        print(f"未知信源 id：{args.source_id}（可用：{', '.join(by_id)}）", file=sys.stderr)
        return EXIT_USAGE
    source = by_id[args.source_id]

    snapshots = _make_snapshot_store(no_snapshot=False)
    if snapshots is None:
        return EXIT_USAGE
    http = HttpClient(trust_env=args.proxy_env)
    repo: IntelRepository | None = None
    try:
        if not args.no_ingest:
            pool = get_pool()
            sync_sources(sources, domain_id, pool)
            repo = IntelRepository(pool)
        try:
            items, outcomes = collect_source(
                source, http, snapshots, max_items=args.max_items, repository=repo
            )
        except SourceDisabledError as exc:
            print(f"✗ 门控拒绝：{exc}", file=sys.stderr)
            return EXIT_FAILED
        except KeyError as exc:
            print(f"✗ {exc}", file=sys.stderr)
            return EXIT_FAILED
        except NotImplementedError:
            print(
                f"✗ 该源暂无特化适配器（type={source.type} 的通用基类"
                f"不含 {source.id} 的解析钩子），待适配器接入后再试",
                file=sys.stderr,
            )
            return EXIT_FAILED
        print(f"== 采集：{source.id}（{source.name}，已启用）==")
        for item in items:
            print(f"  ✓ [{item.snapshot_id[:12]}…] {item.title}")
        if args.no_ingest:
            print(f"产出 {len(items)} 条 RawItem（--no-ingest 未落库）")
        else:
            saved = sum(1 for o in outcomes if o.status == SaveOutcome.SAVED)
            skipped = sum(1 for o in outcomes if o.status == SaveOutcome.SKIPPED)
            failed = sum(1 for o in outcomes if o.status == SaveOutcome.FAILED)
            print(
                f"产出 {len(items)} 条 RawItem → "
                f"入库 {saved} 新增 / {skipped} 幂等跳过 / {failed} 失败"
            )
        return EXIT_OK
    finally:
        http.close()
        close_pool()


def _cmd_query(args: argparse.Namespace) -> int:
    structured = [a for a in (args.subject, args.event_type, args.tag) if a]
    if args.id is None and args.source_id is None and not structured:
        print("须指定 --id 或筛选条件（--source-id/--subject/--event-type/--tag）之一",
              file=sys.stderr)
        return EXIT_USAGE
    try:
        pool = get_pool()
    except RuntimeError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE
    repo = IntelRepository(pool)
    try:
        if args.id is not None:
            rec = repo.get(args.id)
            if rec is None:
                print(f"未找到 id={args.id}", file=sys.stderr)
                return EXIT_FAILED
            _print_record_detail(rec)
            return EXIT_OK

        if structured:
            records = repo.list_by_filter(
                subject=args.subject, event_type=args.event_type, tag=args.tag,
                source_id=args.source_id, limit=args.limit,
            )
            conds = "、".join(
                f"{k}={v}" for k, v in (
                    ("subject", args.subject), ("event_type", args.event_type),
                    ("tag", args.tag), ("source_id", args.source_id),
                ) if v
            )
            print(f"== 查询：{conds} limit={args.limit} ==")
        else:
            before = None
            if args.before:
                try:
                    before = datetime.fromisoformat(args.before)
                except ValueError as exc:
                    print(f"✗ --before 解析失败：{exc}", file=sys.stderr)
                    return EXIT_USAGE
            records = repo.list_by_source(args.source_id, limit=args.limit, before=before)
            print(f"== 查询：source_id={args.source_id} limit={args.limit} ==")
        if not records:
            print("（无结果）——可放宽条件（如去掉 --tag 或换 --event-type）")
        for r in records:
            print(
                f"  [{r.id}] {r.fetched_at:%Y-%m-%d %H:%M}  "
                f"[{r.process_status or 'pending'}"
                f"{f'/{r.event_type}' if r.event_type else ''}"
                f"{f'/{r.admiralty_code}' if r.admiralty_code else ''}] {r.title}"
            )
        print(f"共 {len(records)} 条")
        return EXIT_OK
    finally:
        close_pool()


def _cmd_process(args: argparse.Namespace) -> int:
    path = Path(args.pack) if args.pack else _default_pack()
    try:
        pack = load(path)
    except LoadError as exc:
        print(f"领域包加载失败：{exc}", file=sys.stderr)
        return EXIT_USAGE

    try:
        pool = get_pool()
    except RuntimeError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE
    try:
        repo = IntelRepository(pool)
        # 配置校验先于取条目：LLM env 缺失不产生半写状态（AC8）
        runner = ProcessRunner(repo, pack)
    except LLMConfigError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE

    try:
        if args.source_id:
            known = {s["id"] for s in pack["sources"]}
            if args.source_id not in known:
                print(
                    f"未知信源 id：{args.source_id}（可用：{', '.join(sorted(known))}）",
                    file=sys.stderr,
                )
                return EXIT_USAGE
        stats = runner.run(source_id=args.source_id, limit=args.limit)
        print(f"== 处理：source_id={args.source_id or '全部'} limit={args.limit} ==")
        for line in stats.details:
            print(f"  {line}")
        print(stats.summary_line())
        print(stats.token_line())
        return EXIT_OK if stats.failed == 0 else EXIT_FAILED
    finally:
        close_pool()


def _cmd_verify(args: argparse.Namespace) -> int:
    """人工核实队列入口（Sprint 6 S3.1.1 子集）。"""
    try:
        pool = get_pool()
    except RuntimeError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE
    try:
        repo = EventRepository(pool)
        # verify 只读 event 表，领域包无需加载（不涉及主体归一化）
        svc = EventService(repo, IntelRepository(pool), pack={})

        if args.verify_action == "list":
            events = svc.list_ready_for_manual()
            print(f"== 待人工核实事件：{len(events)} 条（已具备升级条件）==")
            for e in events:
                label = STATUS_LABELS.get(e.status, e.status)
                print(
                    f"  #{e.id} [{label}] {e.subject} / {e.event_type}  "
                    f"独立信源 {e.source_count}  首见 {e.first_seen_at:%Y-%m-%d %H:%M}"
                )
            if not events:
                print("  （无已具备升级条件的事件——双独立信源命中后此处可见）")
            return EXIT_OK

        if args.verify_action == "confirm":
            ok = svc.confirm(args.event_id, operator=args.operator)
            if not ok:
                print(
                    f"✗ 事件 #{args.event_id} 不存在或不在 single_source 状态（仅单源确认可人工确认）",
                    file=sys.stderr,
                )
                return EXIT_FAILED
            print(f"✓ 事件 #{args.event_id} 跃迁 → 多源确认（confirmed）")
            return EXIT_OK

        if args.verify_action == "refute":
            try:
                ok = svc.refute(args.event_id, args.reason, operator=args.operator)
            except ValueError as exc:
                print(f"✗ {exc}", file=sys.stderr)
                return EXIT_USAGE
            if not ok:
                print(
                    f"✗ 事件 #{args.event_id} 不存在或已是终态（confirmed/refuted 不可再证伪）",
                    file=sys.stderr,
                )
                return EXIT_FAILED
            print(f"✓ 事件 #{args.event_id} 跃迁 → 已证伪（refuted）")
            return EXIT_OK

        return EXIT_USAGE
    finally:
        close_pool()


def _cmd_cluster(args: argparse.Namespace) -> int:
    """事件聚类回填入口（Sprint 6 S4.2.2）。"""
    if not args.backfill:
        print("仅支持 --backfill（在线聚类已在 process 内自动触发）", file=sys.stderr)
        return EXIT_USAGE

    path = Path(args.pack) if args.pack else _default_pack()
    try:
        pack = load(path)
    except LoadError as exc:
        print(f"领域包加载失败：{exc}", file=sys.stderr)
        return EXIT_USAGE

    try:
        pool = get_pool()
    except RuntimeError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return EXIT_USAGE
    try:
        intel_repo = IntelRepository(pool)
        event_repo = EventRepository(pool)
        svc = EventService(event_repo, intel_repo, pack)

        ids = event_repo.list_intel_ids_without_event(
            source_id=args.source_id, limit=args.limit
        )
        print(
            f"== 回填：source_id={args.source_id or '全部'} 待聚类 {len(ids)} 条 =="
        )
        attached = 0
        advanced = 0
        for intel_id in ids:
            rec = intel_repo.get(intel_id)
            if rec is None or not rec.subject or not rec.event_type:
                continue
            from pih.process.event import normalize_subject

            subject_norm = normalize_subject(rec.subject, pack)
            event_id = event_repo.find_matching_event(
                subject_norm, rec.event_type, rec.fetched_at
            )
            if event_id is None:
                event_id = event_repo.create_event(
                    subject_norm, rec.event_type, rec.fetched_at
                )
            outcome = event_repo.attach_and_advance(
                intel_id=intel_id,
                event_id=event_id,
                source_id=rec.source_id,
                fetched_at=rec.fetched_at,
            )
            attached += 1
            if outcome.status_advanced:
                advanced += 1
                print(
                    f"  [{intel_id}] ⋄ 挂入事件 #{event_id} → 单源确认（第二独立信源）"
                )
            else:
                print(f"  [{intel_id}] ⋄ 挂入事件 #{event_id}")
        print(f"完成：挂入 {attached} 条，触发自动跃迁 {advanced} 次")
        return EXIT_OK if attached == len(ids) else EXIT_FAILED
    finally:
        close_pool()


def _print_record_detail(rec) -> None:
    """单条详情打印。"""
    print(f"== 情报 #{rec.id} ==")
    print(f"标题      : {rec.title}")
    print(f"信源      : {rec.source_id}")
    print(f"URL       : {rec.url}")
    print(f"列表页    : {rec.list_url}")
    print(f"抓取时间  : {rec.fetched_at:%Y-%m-%d %H:%M:%S}")
    print(f"HTTP 状态 : {rec.http_status}")
    print(f"Content-Type: {rec.content_type}")
    print(f"编码      : {rec.encoding}")
    print(f"快照 ID   : {rec.snapshot_id}")
    print(f"内容指纹  : {rec.content_sha1}")
    print(f"入库时间  : {rec.created_at:%Y-%m-%d %H:%M:%S}")
    print(f"事件 ID   : {rec.event_id or '（未关联事件）'}")
    # ---- Sprint 4 结构化字段（未处理条目仅显示状态）----
    print(f"处理状态  : {rec.process_status or 'pending'}"
          + (f"（{rec.process_error}）" if rec.process_error else ""))
    if rec.subject is not None:
        print(f"主体      : {rec.subject}")
        print(f"事件类型  : {rec.event_type}")
        print(f"事实描述  : {rec.facts}")
        print(f"推断与判断: {rec.inferences or '（无）'}")
        print(f"标签      : {'、'.join(rec.tags) if rec.tags else '（无）'}")
        quant = "；".join(f"{k}={v}" for k, v in (rec.quant_params or {}).items())
        print(f"量化参数  : {quant or '（无）'}")
        print(f"Admiralty : {rec.admiralty_code}")
    if rec.processed_at is not None:
        print(f"处理时间  : {rec.processed_at:%Y-%m-%d %H:%M:%S}")


def main(argv: list[str] | None = None) -> int:
    load_env()
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "probe-source":
            return _cmd_probe(args)
        if args.command == "query":
            return _cmd_query(args)
        if args.command == "process":
            return _cmd_process(args)
        if args.command == "verify":
            return _cmd_verify(args)
        if args.command == "cluster":
            return _cmd_cluster(args)
        return _cmd_collect(args)
    except LoadError as exc:
        print(f"领域包加载失败：{exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
