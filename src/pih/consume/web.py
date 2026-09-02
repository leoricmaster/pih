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
from datetime import datetime
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
from pih.consume.metrics import log_query
from pih.consume.pack_loader import (
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
from pih.store.repository import IntelRepository

_BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))

# facts/inferences 按 '；' 拆成事实清单（提示词规定多事实用全角分号分隔）
templates.env.filters["split_facts"] = lambda s: (
    [f.strip(" ；;。") for f in s.split("；") if f.strip(" ；;。")] if s else []
)

load_env()


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
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    before: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> HTMLResponse:
    """列表页——筛选 form + 表格 + 下一页游标。"""
    filters = IntelFilters(
        subject=subject,
        event_type=event_type,
        tag=tag,
        admiralty=admiralty,
        source_id=source_id,
        process_status=process_status,
        event_status=event_status,
        since=since,
        until=until,
        before=before,
        limit=limit,
    )
    result = _svc(request).list(filters)
    log_query("web", filters.nonempty(), len(result.items))
    return templates.TemplateResponse(
        request,
        "list.html",
        {
            "items": result.items,
            "filters": filters,
            "next_url": _build_next_url(filters, result.next_before),
            "status_labels": STATUS_LABELS,
            "status_options": STATUS_ORDER,
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
    return templates.TemplateResponse(
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


@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request) -> HTMLResponse:
    """信源页（TASK-1.01.01 AC2）——信源清单可视 + 配置错误诊断面（错误态不半截）。"""
    sources, issues, error = load_sources_view()
    return templates.TemplateResponse(
        request,
        "sources.html",
        {"sources": sources, "issues": issues, "error": error},
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

    segs = [seg("robots", "ok" if report.robots_allowed else "fail", report.robots_note)]
    if not report.robots_allowed:
        segs += [seg("列表页", "skip", ""), seg("详情", "skip", ""), seg("快照", "skip", "")]
    elif not report.list_ok:
        segs += [
            seg("列表页", "fail", report.list_note),
            seg("详情", "skip", ""),
            seg("快照", "skip", ""),
        ]
    else:
        segs.append(seg("列表页", "ok", report.list_note))
        details = report.detail_results
        if not details:
            segs += [seg("详情", "skip", ""), seg("快照", "skip", "")]
        else:
            ok_n = sum(1 for d in details if d.ok)
            snap_n = sum(1 for d in details if d.snapshot_id)
            segs.append(
                seg("详情", "ok" if ok_n else "fail", f"{ok_n}/{len(details)} 条详情解析成功")
            )
            segs.append(
                seg("快照", "ok" if snap_n else "fail", f"{snap_n}/{len(details)} 份快照已存档")
            )
    return segs, report.success


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
                "list_ok": rep.list_ok if rep else None,
                "details_ok": sum(1 for d in rep.detail_results if d.ok) if rep else 0,
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
    return templates.TemplateResponse(
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
        },
    )


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
    return templates.TemplateResponse(
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
