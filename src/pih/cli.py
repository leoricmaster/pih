"""PIH 运营者 CLI（Backlog S3.2.1 用户闭环：试抓取报告 + 采集门控）。

命令：
  pih probe-source <id> | --all   试抓取验证（robots→列表→详情→快照），产出成败报告
  pih collect <id>                正式采集（enabled 门控），产出 RawItem 摘要

退出码：0 成功 / 1 抓取失败或门控拒绝 / 2 用法或环境错误。
环境：从 cwd 的 .env 读取 MinIO 凭据（python-dotenv），未起 MinIO 时可用
--no-snapshot 跳过快照（仅 probe）。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from minio import Minio

import pih.collect.adapters  # noqa: F401  触发内置适配器注册
from pih.collect.base import SourceConfig
from pih.collect.httpclient import HttpClient
from pih.collect.probe import NullSnapshotStore, ProbeReport, probe_source
from pih.collect.run import SourceDisabledError, collect_source
from pih.collect.snapshot import BUCKET, SnapshotStore
from pih.domainpacks.errors import LoadError
from pih.domainpacks.loader import DEFAULT_PACK_DIR, load

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
        help="正式采集单源（enabled 门控：仅运行领域包中 enabled: true 的信源）",
    )
    cp.add_argument("source_id", help="信源 id")
    cp.add_argument("--max-items", type=int, default=10, help="单次采集详情条数上限（默认 10）")
    cp.add_argument("--proxy-env", action="store_true", help="继承环境代理变量（默认不继承）")
    cp.add_argument("--pack", default=None, help="领域包 YAML 路径（默认同 probe-source）")

    return parser


def _default_pack() -> Path:
    cwd_pack = Path("domain_packs/construction_machinery/pack.yaml")
    if cwd_pack.exists():
        return cwd_pack
    return DEFAULT_PACK_DIR / "construction_machinery" / "pack.yaml"


def _load_sources(pack_arg: str | None) -> list[SourceConfig]:
    path = Path(pack_arg) if pack_arg else _default_pack()
    pack = load(path)
    return [SourceConfig.from_dict(d) for d in pack["sources"]]


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
    sources = _load_sources(args.pack)
    by_id = {s.id: s for s in sources}
    if args.source_id not in by_id:
        print(f"未知信源 id：{args.source_id}（可用：{', '.join(by_id)}）", file=sys.stderr)
        return EXIT_USAGE
    source = by_id[args.source_id]

    snapshots = _make_snapshot_store(no_snapshot=False)
    if snapshots is None:
        return EXIT_USAGE
    http = HttpClient(trust_env=args.proxy_env)
    try:
        try:
            items = collect_source(source, http, snapshots, max_items=args.max_items)
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
        print(f"产出 {len(items)} 条 RawItem（快照已存档，待 store 层落库）")
        return EXIT_OK
    finally:
        http.close()


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "probe-source":
            return _cmd_probe(args)
        return _cmd_collect(args)
    except LoadError as exc:
        print(f"领域包加载失败：{exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
