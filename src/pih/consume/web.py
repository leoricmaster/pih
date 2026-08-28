"""FastAPI 应用——Web 出口 + JSON API 同源（Sprint 5a，ADR-006）。

lifespan 起 PG pool；Jinja2 渲染列表/详情；include api router。
本地启动：uv run uvicorn pih.consume.web:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pih.consume.api import router as api_router
from pih.consume.metrics import log_query
from pih.consume.query_service import IntelFilters, QueryService
from pih.consume.snapshot_url import make_snapshot_client, presigned_snapshot_url
from pih.store.db import close_pool, get_pool
from pih.store.repository import IntelRepository

_BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))

# facts/inferences 按 '；' 拆成事实清单（提示词规定多事实用全角分号分隔）
templates.env.filters["split_facts"] = lambda s: (
    [f.strip(" ；;。") for f in s.split("；") if f.strip(" ；;。")] if s else []
)

load_dotenv()


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
    return QueryService(IntelRepository(request.app.state.pool))


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
            "event_placeholder": "待事件模型上线后自动激活",
        },
    )


@app.get("/intel/{intel_id}", response_class=HTMLResponse)
def detail_page(intel_id: int, request: Request) -> HTMLResponse:
    """详情页——schema 全字段 + 事实/推断分区 + 快照 presigned 入口。"""
    rec = _svc(request).get(intel_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"intel_item {intel_id} not found")
    log_query("web", {"id": intel_id}, 1)
    # 快照 presigned URL——MinIO 不可达时降级为 None，模板展示快照 ID 文本
    snapshot_url = None
    client = make_snapshot_client()
    if client is not None:
        snapshot_url = presigned_snapshot_url(client, rec.source_id, rec.content_sha1)
    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "rec": rec,
            "snapshot_url": snapshot_url,
            "event_placeholder": "待事件模型上线后自动激活",
        },
    )
