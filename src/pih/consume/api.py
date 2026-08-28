"""JSON API router（Sprint 5a，ADR-006 同源出口之二）。

路由：
  GET /api/intel/list       列表（依赖 Bearer token）
  GET /api/intel/{intel_id} 详情（依赖 Bearer token）
  GET /healthz              健康检查（不鉴权）

与 Web 出口共用 QueryService——同条件返回同集合同序（S1.1.4 AC1）。
"""
from __future__ import annotations

import dataclasses

from fastapi import APIRouter, Depends, HTTPException, Request

from pih.consume.auth import verify_api_token
from pih.consume.metrics import log_query
from pih.consume.query_service import IntelFilters, QueryService
from pih.consume.snapshot_url import make_snapshot_client, presigned_snapshot_url
from pih.store.repository import IntelRepository

router = APIRouter(prefix="/api")


def get_query_service(request: Request) -> QueryService:
    """从 app.state.pool 构造 QueryService（lifespan 已建 pool）。"""
    pool = request.app.state.pool
    return QueryService(IntelRepository(pool))


def _record_to_dict(rec) -> dict:
    """IntelRecord → JSON 友好 dict（datetime 保留对象，FastAPI 序列化为 ISO）。"""
    d = dataclasses.asdict(rec)
    # 不暴露 raw_html（大字段，API 消费者用不上下文；详情页 Web 渲染才用）
    d.pop("raw_html", None)
    # 事件核实状态占位（待事件模型上线后自动激活）
    d["event_verification_status"] = None
    d["event_verification_note"] = "待事件模型上线后自动激活"
    # 来源引用（S1.1.4 AC2 要求字段）——快照 presigned URL，MinIO 不可达时为 None
    snapshot_url = None
    client = make_snapshot_client()
    if client is not None:
        snapshot_url = presigned_snapshot_url(client, rec.source_id, rec.content_sha1)
    d["references"] = {
        "url": rec.url,
        "snapshot_id": rec.snapshot_id,
        "snapshot_url": snapshot_url,
    }
    return d


@router.get("/intel/list", dependencies=[Depends(verify_api_token)])
def list_intel(
    filters: IntelFilters = Depends(),
    svc: QueryService = Depends(get_query_service),
) -> dict:
    """组合查询——主体/事件类型/标签/置信度/信源/处理状态/时间范围/游标。"""
    result = svc.list(filters)
    log_query("api", filters.nonempty(), len(result.items))
    return {
        "items": [_record_to_dict(r) for r in result.items],
        "count": len(result.items),
        "next_before": result.next_before,
    }


@router.get("/intel/{intel_id}", dependencies=[Depends(verify_api_token)])
def get_intel(
    intel_id: int,
    svc: QueryService = Depends(get_query_service),
) -> dict:
    """单条详情——404 if not found。"""
    rec = svc.get(intel_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"intel_item {intel_id} not found")
    log_query("api", {"id": intel_id}, 1)
    return _record_to_dict(rec)


@router.get("/healthz")
def healthz(request: Request) -> dict:
    """健康检查——PG 连通性（本 Sprint web service 不连 MinIO，略）。"""
    pg_ok = True
    try:
        pool = request.app.state.pool
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception:  # noqa: BLE001 healthz 不可因任何异常崩
        pg_ok = False
    return {"status": "ok" if pg_ok else "degraded", "pg": pg_ok}
