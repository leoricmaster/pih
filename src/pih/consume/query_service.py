"""QueryService：消费层同源查询服务（Sprint 5a，ADR-006 + Sprint 6 事件）。

Web 页面与 JSON API 出口共用此服务——同条件调用必返同集合同序。
内部委托 IntelRepository.list_by_filter / get，统一 IntelFilters 入参。
Sprint 6：注入领域包 ranking 节用于排序权重（W_c × map(admiralty)）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pih.store.repository import IntelRecord, IntelRepository


@dataclass(frozen=True)
class IntelFilters:
    """情报列表筛选条件（Web 与 API 同源入参，ADR-006）。"""

    subject: str | None = None
    event_type: str | None = None
    tag: str | None = None
    admiralty: str | None = None
    source_id: str | None = None
    process_status: str | None = None
    event_status: str | None = None  # Sprint 6：按事件核实状态筛选
    since: datetime | None = None
    until: datetime | None = None
    before: datetime | None = None
    limit: int = 50

    def nonempty(self) -> dict[str, Any]:
        """返回非空字段——供北极星指标日志与 next_before 拼装复用。"""
        return {
            k: v
            for k, v in (
                ("subject", self.subject),
                ("event_type", self.event_type),
                ("tag", self.tag),
                ("admiralty", self.admiralty),
                ("source_id", self.source_id),
                ("process_status", self.process_status),
                ("event_status", self.event_status),
                ("since", self.since.isoformat() if self.since else None),
                ("until", self.until.isoformat() if self.until else None),
                ("before", self.before.isoformat() if self.before else None),
            )
            if v is not None
        }


@dataclass
class ListResult:
    """QueryService.list 返回——items + 下一页游标（next_before）。"""

    items: list[IntelRecord]
    next_before: str | None = None


class QueryService:
    """消费层查询服务（Web 与 JSON API 同源，ADR-006）。"""

    def __init__(self, repo: IntelRepository, ranking: dict | None = None) -> None:
        self._repo = repo
        # ranking 节从领域包 pack['ranking'] 读取（event_state_weights /
        # reliability_weights / credibility_weights）；None 时回退简版排序
        self._ranking = ranking

    def list(self, filters: IntelFilters) -> ListResult:
        """按 filters 检索情报列表，返回 items + next_before 游标。

        next_before 仅在结果数等于 limit 时给出（即可能还有下一页）；
        小于 limit 时不提供，避免渲染无意义「下一页」链接（S1.1.1 AC2）。
        """
        records = self._repo.list_by_filter(
            subject=filters.subject,
            event_type=filters.event_type,
            tag=filters.tag,
            admiralty=filters.admiralty,
            source_id=filters.source_id,
            process_status=filters.process_status,
            event_status=filters.event_status,
            since=filters.since,
            until=filters.until,
            before=filters.before,
            limit=filters.limit,
            ranking=self._ranking,
        )
        next_before = None
        if len(records) == filters.limit and records:
            last = records[-1]
            next_before = last.fetched_at.isoformat()
        return ListResult(items=records, next_before=next_before)

    def get(self, intel_id: int) -> IntelRecord | None:
        """单条详情——委托 IntelRepository.get。"""
        return self._repo.get(intel_id)
