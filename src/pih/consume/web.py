"""FastAPI 应用——Web 出口 + JSON API 同源（ADR-006；反馈 TASK-4.03.01/4.03.02；事件 TASK-2.02.01）。

lifespan 起 PG pool；Jinja2 渲染列表/详情；include api router；
反馈三路由（POST /feedback 写入、GET /feedback 聚合视图、/feedback/export JSONL）。
列表/详情页事件核实状态已随 event 表上线实查激活（JOIN event）+ 排序 W_c×map(admiralty)。
本地启动：uv run uvicorn pih.consume.web:app --reload --port 8000
"""
from __future__ import annotations

import dataclasses
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pih.collect import adapters  # noqa: F401  # import 即注册信源适配器（试抓编排依赖）
from pih.collect.base import SourceConfig, has_adapter
from pih.collect.httpclient import HttpClient
from pih.collect.probe import ProbeReport, probe_source
from pih.collect.snapshot import SnapshotStore
from pih.consume.api import router as api_router
from pih.consume.labels import FIELD_LEGEND, FREQ_LABELS, TYPE_LABELS
from pih.consume.metrics import log_query
from pih.consume.pack_loader import (
    load_filter_vocab,
    load_pack,
    load_pack_vocab,
    load_sources_view,
    pack_ranking,
)
from pih.consume.query_service import IntelFilters, QueryService
from pih.consume.snapshot_url import make_snapshot_client, presigned_snapshot_url
from pih.envs import load_env
from pih.process.event import STATUS_LABELS, STATUS_ORDER, EventService
from pih.store.db import close_pool, get_pool
from pih.store.event_repository import EventRepository
from pih.store.feedback import FEEDBACK_TYPES, FeedbackRepository
from pih.store.notification import NotificationRepository
from pih.store.repository import (
    STATUS_DEAD,
    STATUS_FILTERED_OUT,
    STATUS_NEEDS_MANUAL,
    STATUS_PENDING,
    IntelRepository,
)
from pih.store.source_health import SourceHealthRepository

_BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))

# 呈现词映射作模板全局（doc-4「呈现」基线；漂移守卫见 tests/unit/consume/test_labels.py）
templates.env.globals["TYPE_LABELS"] = TYPE_LABELS
templates.env.globals["FREQ_LABELS"] = FREQ_LABELS
templates.env.globals["FIELD_LEGEND"] = FIELD_LEGEND

# facts/inferences 按 '；' 拆成事实清单（提示词规定多事实用全角分号分隔）
templates.env.filters["split_facts"] = lambda s: (
    [f.strip(" ；;。") for f in s.split("；") if f.strip(" ；;。")] if s else []
)

load_env()

# 时间范围预设 → 天数（TASK-2.01.01 D2；显式 since 直参优先）
_TIME_RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def _load_pack_vocab() -> tuple[list[str], list[str]]:
    """详情页反馈表单的候选清单（主体 datalist / 事件类型 select）。

    委托 pack_loader.load_pack_vocab——web 与 api 共用，避免循环 import。
    """
    return load_pack_vocab()


def _pack_ranking() -> dict | None:
    """从领域包取 ranking 节（注入 QueryService 排序权重）。

    委托 pack_loader.pack_ranking——web 与 api 共用，保证同源排序。
    """
    return pack_ranking()


def _load_pack() -> dict | None:
    """加载领域包 dict（EventService 主体归一化用）。委托 pack_loader.load_pack。"""
    return load_pack()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动建 PG pool，关闭释放。sync_sources 由 collect CLI 负责，本服务只读。"""
    app.state.pool = get_pool()
    try:
        yield
    finally:
        close_pool()


app = FastAPI(title="PIH 产品情报中心", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")
app.include_router(api_router)


def _svc(request: Request) -> QueryService:
    return QueryService(
        IntelRepository(request.app.state.pool),
        ranking=_pack_ranking(),
    )


def _event_svc(request: Request) -> EventService:
    """详情页事件区实查用——EventService 持有 pack 做主体归一化
    （详情页只读，归一化已落 event.subject 不再调用）。"""
    pool = request.app.state.pool
    return EventService(
        EventRepository(pool),
        IntelRepository(pool),
        _load_pack() or {},
    )


def _render(request: Request, name: str, context: dict):
    """统一渲染出口（TASK-4.02.01 D19）——每页注入铃铛上下文
    （未读数 + 最近未读，topbar 下拉用）；PG 异常降级为空铃铛不阻塞页面。"""
    bell: dict = {"bell_count": 0, "bell_recent": []}
    try:
        notifications = NotificationRepository(request.app.state.pool)
        bell["bell_count"] = notifications.unread_count()
        bell["bell_recent"] = notifications.list_unread(5)
    except Exception:  # noqa: BLE001 铃铛降级不炸页面（与 MinIO 降级同口径）
        pass
    bell.update(context)
    return templates.TemplateResponse(request, name, bell)


def _build_next_url(filters: IntelFilters, next_before: str | None) -> str | None:
    """拼下一页 URL——保留当前筛选非空参数 + before=next_before。"""
    if next_before is None:
        return None
    params = filters.nonempty()
    params["before"] = next_before
    # since/until 已在 nonempty() 里 ISO 化，before 同样是 ISO 字符串
    from urllib.parse import urlencode

    return f"/?{urlencode(params)}"


@app.get("/", response_class=HTMLResponse)
def list_page(
    request: Request,
    subject: str | None = Query(None),
    event_type: str | None = Query(None),
    tag: str | None = Query(None),
    admiralty: str | None = Query(None),
    source_id: str | None = Query(None),
    process_status: str | None = Query(None),
    event_status: str | None = Query(None),
    time_range: str | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    before: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> HTMLResponse:
    """列表页——筛选 form + 表格 + 下一页游标。

    time_range 预设（TASK-2.01.01 D2：7d/30d/90d）映射 since=now-N 天；
    显式 since 直参优先（API/URL 兼容路径）。
    """
    effective_since = since
    if effective_since is None and time_range in _TIME_RANGE_DAYS:
        effective_since = datetime.now() - timedelta(
            days=_TIME_RANGE_DAYS[time_range]
        )
    filters = IntelFilters(
        subject=subject,
        event_type=event_type,
        tag=tag,
        admiralty=admiralty,
        source_id=source_id,
        process_status=process_status,
        event_status=event_status,
        since=effective_since,
        until=until,
        before=before,
        limit=limit,
    )
    result = _svc(request).list(filters)
    log_query("web", filters.nonempty(), len(result.items))
    filter_subjects, filter_event_types, filter_tags = load_filter_vocab()
    return _render(
        request,
        "list.html",
        {
            "items": result.items,
            "filters": filters,
            "next_url": _build_next_url(filters, result.next_before),
            "status_labels": STATUS_LABELS,
            "status_options": STATUS_ORDER,
            "filter_subjects": filter_subjects,
            "filter_event_types": filter_event_types,
            "filter_tags": filter_tags,
            "time_range": time_range or "",
        },
    )


@app.get("/intel/{intel_id}", response_class=HTMLResponse)
def detail_page(
    intel_id: int, request: Request, fb: bool = Query(False)
) -> HTMLResponse:
    """详情页——schema 全字段 + 事实/推断分区 + 快照 presigned 入口
    + 反馈区 + 事件状态与跃迁历史。"""
    rec = _svc(request).get(intel_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"intel_item {intel_id} not found")
    log_query("web", {"id": intel_id}, 1)
    # 快照 presigned URL——MinIO 不可达时降级为 None，模板展示快照 ID 文本
    snapshot_url = None
    client = make_snapshot_client()
    if client is not None:
        snapshot_url = presigned_snapshot_url(client, rec.source_id, rec.content_sha1)
    pack_subjects, pack_event_types = _load_pack_vocab()
    # 事件状态与跃迁历史实查（已随 event 表上线激活）
    event_with_log = _event_svc(request).get_event_with_log(rec.event_id)
    return _render(
        request,
        "detail.html",
        {
            "rec": rec,
            "snapshot_url": snapshot_url,
            "event_with_log": event_with_log,
            "status_labels": STATUS_LABELS,
            "feedbacked": fb,
            "pack_subjects": pack_subjects,
            "pack_event_types": pack_event_types,
        },
    )


@app.get("/verify", response_class=HTMLResponse)
def verify_page(request: Request) -> HTMLResponse:
    """核实页（TASK-2.02.02）：积压提醒置顶 + 三类队列 + 确认/证伪操作。
    Web 验收轮 R2（2026-09-04）收件箱归位：pending 滞留入积压区、
    needs_manual 带重放动作、filtered_out/dead 为底部折叠审计区——
    本页成为全站唯一人工工作台（情报页回归纯检索消费面）。

    排序 AC1「置信度升序 + 采集时间升序」——条目队列以 map(admiralty)（ranking
    权重短板）升序=低置信优先，fetched_at 升序破同分；事件队列无置信度维度，
    按 first_seen_at 升序（滞留最久优先，与积压区口径一致）。队列小（单用户
    系统），路由层 Python 排序（设计 D8）。
    """
    pool = request.app.state.pool
    intel_repo = IntelRepository(pool)
    event_svc = _event_svc(request)
    ranking = _pack_ranking() or {}
    rel_w = ranking.get("reliability_weights", {})
    cred_w = ranking.get("credibility_weights", {})

    def _score(code: str | None) -> float:
        # 无码/畸形码视为最低置信（排最前，进人工视野）
        if not code or len(code) != 2:
            return -1.0
        return min(float(rel_w.get(code[0], 0.0)), float(cred_w.get(code[1], 0.0)))

    def _sort_items(items: list) -> list:
        return sorted(items, key=lambda r: (_score(r.admiralty_code), r.fetched_at))

    # 滞留天数在路由侧算（DB 时间戳带 tz，模板侧 naive/aware 相减会炸；
    # naive 输入按本地时区处理——单测 fake 与 DB 两种来源都可算）
    def _days_ago(t: datetime) -> int:
        now = datetime.now().astimezone()
        if t.tzinfo is None:
            t = t.astimezone()
        return max(0, (now - t).days)

    stale_cards = [
        {"event": ev, "days": _days_ago(ev.first_seen_at)}
        for ev in event_svc.list_stale()
    ]
    # 收件箱归位（R2）：pending 滞留并入积压区；filtered_out/dead 为折叠审计区
    pending_items = sorted(
        intel_repo.list_inbox(process_status=STATUS_PENDING),
        key=lambda r: r.fetched_at,
    )
    audit_items = sorted(
        intel_repo.list_inbox(process_status=STATUS_FILTERED_OUT)
        + intel_repo.list_inbox(process_status=STATUS_DEAD),
        key=lambda r: r.fetched_at,
        reverse=True,
    )
    context = {
        "ready_events": event_svc.list_ready_for_manual(),
        "stale_cards": stale_cards,
        "low_conf_items": _sort_items(intel_repo.list_low_confidence()),
        "needs_manual_items": _sort_items(
            intel_repo.list_inbox(process_status=STATUS_NEEDS_MANUAL)
        ),
        "pending_items": pending_items,
        "audit_items": audit_items,
        "status_labels": STATUS_LABELS,
    }
    return _render(request, "verify.html", context)


@app.post("/verify/{event_id}/confirm")
def verify_confirm(event_id: int, request: Request) -> RedirectResponse:
    """人工终态：单源确认 → 多源确认（写 verification_log，AC2）。"""
    event_svc = _event_svc(request)
    if event_svc.get_event_with_log(event_id).event is None:
        raise HTTPException(status_code=404, detail=f"event {event_id} not found")
    if not event_svc.confirm(event_id):
        raise HTTPException(
            status_code=400, detail="当前事件状态不允许确认（须为单源确认）"
        )
    return RedirectResponse("/verify", status_code=303)


@app.post("/verify/{event_id}/refute")
def verify_refute(
    event_id: int, request: Request, reason: str = Form("")
) -> RedirectResponse:
    """人工终态：证伪（必填理由入日志，AC3；该事件下情报检索默认隐藏 D7）。"""
    reason_s = (reason or "").strip()
    if not reason_s:
        raise HTTPException(status_code=400, detail="证伪必须填写理由")
    event_svc = _event_svc(request)
    if event_svc.get_event_with_log(event_id).event is None:
        raise HTTPException(status_code=404, detail=f"event {event_id} not found")
    if not event_svc.refute(event_id, reason_s):
        raise HTTPException(
            status_code=400, detail="当前事件状态不允许证伪（终态无出边）"
        )
    return RedirectResponse("/verify", status_code=303)


@app.get("/notifications", response_class=HTMLResponse)
def notifications_page(request: Request) -> HTMLResponse:
    """站内信历史页（TASK-4.02.01 AC2）——仅经铃铛「查看全部」可达（原型 IA）。"""
    repo = NotificationRepository(request.app.state.pool)
    recent = repo.list_recent(50)
    unread = [n for n in recent if n["read_at"] is None]
    return _render(
        request,
        "notifications.html",
        {"unread": unread, "history": recent},
    )


@app.post("/notifications/{notification_id}/read")
def notification_mark_read(notification_id: int, request: Request) -> RedirectResponse:
    """标记已读（AC2）——303 回通知页（与 /inbox replay 同模式，内网信任域）。"""
    NotificationRepository(request.app.state.pool).mark_read(notification_id)
    return RedirectResponse("/notifications", status_code=303)


@app.get("/inbox", response_class=HTMLResponse)
def inbox_page() -> RedirectResponse:
    """收件箱已并入核实页工作台（Web 验收轮 R2，2026-09-04）。

    ADR-011 两视图是数据口径（检索=extracted / 收件箱=非 extracted），
    不随 UI 归位变化；本路由保留 303 引路，避免旧书签/口令 404。
    """
    return RedirectResponse("/verify", status_code=303)


@app.post("/verify/{intel_id}/replay")
def verify_replay(intel_id: int, request: Request) -> RedirectResponse:
    """AC4 重放上 Web：dead/filtered_out/needs_manual → 重置 pending 重入处理链。

    与 CLI `pih replay` 同语义（mark_status pending）。POST 与 Web 同信任域
    （ADR-006 内网默认开放，同 /feedback 口径）；重放后 303 回核实页待人工区。
    """
    repo = IntelRepository(request.app.state.pool)
    if repo.get(intel_id) is None:
        raise HTTPException(status_code=404, detail=f"intel_item {intel_id} not found")
    repo.mark_status(intel_id, STATUS_PENDING)
    log_query("web", {"replay": intel_id}, 1)
    return RedirectResponse("/verify#manual", status_code=303)


@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request) -> HTMLResponse:
    """信源页（TASK-1.01.01 AC2）——信源清单可视 + 配置错误诊断面（错误态不半截）。

    健康列（TASK-4.02.01 D20）读 DB source 健康行：≥3 异常 / 1–2 失败 N 次 /
    0 且采过 正常 / 0 且从未采 —。DB 不可达降级为空 map（列显 —）。
    """
    sources, issues, error = load_sources_view()
    adapter_ready_ids = {
        s["id"] for s in sources or [] if has_adapter(SourceConfig.from_dict(s))
    }
    try:
        health_by_id = SourceHealthRepository(
            request.app.state.pool
        ).list_health()
    except Exception:  # noqa: BLE001 健康列降级不阻塞清单
        health_by_id = {}
    return _render(
        request,
        "sources.html",
        {
            "sources": sources,
            "issues": issues,
            "error": error,
            "adapter_ready_ids": adapter_ready_ids,
            "health_by_id": health_by_id,
        },
    )


@dataclasses.dataclass
class ProbeOutcome:
    """试抓编排结果——report 为 None 时 note 给出未执行原因。"""

    report: ProbeReport | None
    note: str | None


def run_probe(source_id: str) -> ProbeOutcome:
    """信源页试抓编排（AC3）——pack dict → SourceConfig → probe_source。

    边界降级不 500：无适配器（KeyError）与 MinIO 不可达都归为 note。
    深依赖按模块命名空间引用（web.get_adapter 等），单测在 web 层替换。
    """
    sources, _, _ = load_sources_view()
    d = next((s for s in sources or [] if s["id"] == source_id), None)
    if d is None:
        return ProbeOutcome(None, f"信源 {source_id} 不在领域包中")
    src = SourceConfig.from_dict(d)
    # 纯查表（不实例化）：适配器缺失须先于 MinIO 判定，避免误导性「快照不可用」
    if not has_adapter(src):
        return ProbeOutcome(
            None, f"适配器未接入：无适配器（source.id={src.id}, type={src.type}）"
        )
    client = make_snapshot_client()
    if client is None:
        return ProbeOutcome(None, "快照不可用：MinIO 不可达（docker compose up -d 后重试）")
    return ProbeOutcome(probe_source(src, HttpClient(), SnapshotStore(client)), None)


def _probe_view(report: ProbeReport) -> tuple[list[dict], bool]:
    """ProbeReport → 四段三态视图（robots/列表页/详情/快照）。

    三态语义（设计文档 §3）：成功=执行且通过；失败=执行且未通过；未达=前置失败未执行。
    note 是用户视角文案（R4）：说清发生了什么、下一步看哪——实现细节（软 200
    排查 dump 等）留 pih.probe 日志，不上页面。
    """
    state_label = {"ok": "成功", "fail": "失败", "skip": "未达"}
    cls_map = {"ok": "ok", "fail": "warn", "skip": "muted"}

    def seg(label: str, state: str, note: str) -> dict:
        return {
            "label": label,
            "state": state,
            "state_label": state_label[state],
            "cls": cls_map[state],
            "note": note,
        }

    if report.robots_invalid:
        robots_note = "站点未提供有效 robots 声明（返回的是网页而非规则文件），按无限制处理"
    elif report.robots_allowed:
        robots_note = "允许抓取"
    else:
        robots_note = report.robots_note
    segs = [seg("robots 合规检查", "ok" if report.robots_allowed else "fail", robots_note)]
    if not report.robots_allowed:
        segs += [seg("列表页", "skip", ""), seg("详情", "skip", ""), seg("快照", "skip", "")]
    elif not report.list_ok:
        segs += [
            seg("列表页", "fail", report.list_note),
            seg("详情", "skip", ""),
            seg("快照", "skip", ""),
        ]
    else:
        segs.append(seg("列表页", "ok", f"列表页可达，找到 {report.list_count} 条待抓内容"))
        details = report.detail_results
        if not details:
            segs += [seg("详情", "skip", ""), seg("快照", "skip", "")]
        else:
            ok_n = sum(1 for d in details if d.ok)
            snap_n = sum(1 for d in details if d.snapshot_id)
            note = f"已抓取 {ok_n}/{len(details)} 条正文"
            sample = next((d.title for d in details if d.ok and d.title), None)
            if sample:
                note += f"；示例：『{sample}』"
            segs.append(seg("详情", "ok" if ok_n else "fail", note))
            segs.append(
                seg("快照", "ok" if snap_n else "fail", f"{snap_n} 份原文快照已存档")
            )
    return segs, report.success


def _probe_warns(report: ProbeReport) -> list[str]:
    """结论行聚合的告警（与三态正交）——决策点必须可见的复核提示。

    验收反馈修复：通过+告警（如 robots 软 200）时结论须呈现「含 N 项告警」，
    否则复核责任只活在 note 小字里，决策点信息不足。
    """
    warns = []
    if report.robots_invalid:
        warns.append("该站点未提供有效 robots 声明，已按无限制处理——请确认可接受")
    return warns


_probe_logger = logging.getLogger("pih.probe")


def _log_probe(source_id: str, outcome: ProbeOutcome, duration_ms: float) -> None:
    """试抓结构化日志（doc-2 §8）——JSON lines，channel=web，与 pih.metrics 同构。"""
    rep = outcome.report
    _probe_logger.info(
        json.dumps(
            {
                "event": "probe",
                "channel": "web",
                "source_id": source_id,
                "success": rep.success if rep else False,
                "robots_allowed": rep.robots_allowed if rep else None,
                "robots_detail": rep.robots_detail if rep else "",
                "list_ok": rep.list_ok if rep else None,
                "details_ok": sum(1 for d in rep.detail_results if d.ok) if rep else 0,
                "warns": len(_probe_warns(rep)) if rep else 0,
                "note": outcome.note,
                "duration_ms": round(duration_ms, 1),
            },
            ensure_ascii=False,
        )
    )


@app.post("/sources/{source_id}/probe", response_class=HTMLResponse)
def sources_probe(source_id: str, request: Request) -> HTMLResponse:
    """信源页试抓（AC3）——同步执行 probe_source，直渲染带报告的信源页（POST 可重放）。"""
    sources, issues, error = load_sources_view()
    src = next((s for s in sources or [] if s["id"] == source_id), None)
    if src is None:
        raise HTTPException(status_code=404, detail=f"信源 {source_id} 不在领域包中")
    started = time.perf_counter()
    outcome = run_probe(source_id)
    _log_probe(source_id, outcome, (time.perf_counter() - started) * 1000)
    probe_view, probe_success = (
        _probe_view(outcome.report) if outcome.report else (None, None)
    )
    probe_warns = _probe_warns(outcome.report) if outcome.report else []
    snapshot_links = _probe_snapshot_links(outcome.report)
    probe_summary = (
        _probe_summary(outcome.report) if outcome.report and outcome.report.success else None
    )
    return _render(
        request,
        "sources.html",
        {
            "sources": sources,
            "issues": issues,
            "error": error,
            "probe_src": src,
            "probe_outcome": outcome,
            "probe_view": probe_view,
            "probe_success": probe_success,
            "probe_warns": probe_warns,
            "probe_snapshot_links": snapshot_links,
            "probe_summary": probe_summary,
        },
    )


def _probe_summary(report: ProbeReport) -> str:
    """R7：成功路径的产出摘要——一句「试抓产出了什么」。

    成功时用户只需要知道产出与证据（含示例标题）；管线四段是失败归因用的
    诊断信息，不在成功路径呈现（渐进披露：正常给结论，异常给诊断）。
    """
    ok_n = sum(1 for d in report.detail_results if d.ok)
    snap_n = sum(1 for d in report.detail_results if d.snapshot_id)
    text = f"抓到 {ok_n} 条正文，{snap_n} 份原文已存档"
    sample = next((d.title for d in report.detail_results if d.ok and d.title), None)
    if sample:
        text += f"，示例：『{sample}』"
    return text


def _probe_snapshot_links(report: ProbeReport | None) -> list[dict]:
    """R5：报告的原文查看入口——快照真存档了就让用户点得开。

    试抓时已写入 MinIO；这里 presign 现取（1 小时有效）。MinIO 不可达
    或 presign 失败降级为空列表——报告主体与「已存档」事实不受影响。
    """
    if report is None:
        return []
    client = make_snapshot_client()
    if client is None:
        return []
    links = []
    for d in report.detail_results:
        if not (d.ok and d.snapshot_id):
            continue
        url = presigned_snapshot_url(client, report.source_id, d.snapshot_id)
        if url:
            links.append({"title": d.title or d.url, "url": url})
    return links


# 反馈类型展示名（模板与导出共用口径）
FEEDBACK_TYPE_LABELS = {
    "subject_wrong": "主体错了",
    "event_type_wrong": "事件类型错",
    "fact_wrong": "事实不准",
    "should_filter": "不该入库",
}


@app.post("/feedback")
def submit_feedback(
    request: Request,
    intel_id: int = Form(...),
    feedback_type: str = Form(...),
    fact_index: int | None = Form(None),
    wrong_value: str | None = Form(None),
    correct_value: str | None = Form(None),
    note: str | None = Form(None),
    user_id: str = Form("operator"),
) -> RedirectResponse:
    """消费页反馈写入（TASK-4.03.01）——303 回详情页，?fb=1 显示已记录。

    无鉴权：与 Web 页面同信任域（ADR-006「内网默认开放」口径）；
    feedback_type 合法性在此校验（store 层信任调用方）。
    """
    if feedback_type not in FEEDBACK_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"feedback_type 必须是 {'/'.join(FEEDBACK_TYPES)} 之一",
        )
    pool = request.app.state.pool
    if IntelRepository(pool).get(intel_id) is None:
        raise HTTPException(status_code=404, detail=f"intel_item {intel_id} not found")
    FeedbackRepository(pool).save(
        intel_id=intel_id,
        feedback_type=feedback_type,
        fact_index=fact_index,
        wrong_value=wrong_value or None,
        correct_value=correct_value or None,
        note=note or None,
        user_id=user_id or "operator",
    )
    log_query("web", {"feedback": feedback_type, "intel_id": intel_id}, 1)
    return RedirectResponse(f"/intel/{intel_id}?fb=1", status_code=303)


@app.get("/feedback", response_class=HTMLResponse)
def feedback_page(request: Request) -> HTMLResponse:
    """反馈聚合视图（TASK-4.03.02）——按信源×类型计数 + 明细 + 导出入口。"""
    repo = FeedbackRepository(request.app.state.pool)
    return _render(
        request,
        "feedback.html",
        {
            "agg_rows": repo.aggregate(),
            "recent": repo.list_recent(100),
            "type_labels": FEEDBACK_TYPE_LABELS,
            "highlight_threshold": 0.30,
        },
    )


@app.get("/feedback/export")
def feedback_export(request: Request) -> Response:
    """反馈明细 JSONL 导出——process 层 prompt 迭代的 few-shot 素材（TASK-4.03.02 AC2）。"""
    rows = FeedbackRepository(request.app.state.pool).list_recent(1000)
    lines = []
    for r in rows:
        d = dataclasses.asdict(r)
        d["created_at"] = r.created_at.isoformat()
        d["feedback_type_label"] = FEEDBACK_TYPE_LABELS.get(r.feedback_type, r.feedback_type)
        lines.append(json.dumps(d, ensure_ascii=False))
    return Response(
        "\n".join(lines) + ("\n" if lines else ""),
        media_type="application/x-ndjson",
    )
