"""EventService：事件聚类与核实状态机的业务层（Sprint 6 S4.2.2）。

聚类规则（架构 §6.1 / Backlog S4.2.2 AC2-AC3，详见 plan D1/D5）：
1. 主体归一化（领域包 competitors.aliases → display_name）
2. event_type 精确匹配
3. fetched_at 时间窗 ±7 天
命中已有事件 → 挂入；若是第二独立信源，事件 pending → single_source 自动跃迁；
未命中 → 新建 pending 事件。

人工终态（架构 §6.1，运营者 CLI 入口）：
  confirm: single_source → confirmed
  refute:   pending/single_source → refuted（必填 reason）

中文展示映射 STATUS_LABELS 供模板与 CLI 共用。
"""
from __future__ import annotations

from dataclasses import dataclass

from pih.store.event_repository import (
    STATUS_CONFIRMED,
    STATUS_EXPIRED,
    STATUS_PENDING,
    STATUS_REFUTED,
    STATUS_SINGLE_SOURCE,
    EventRecord,
    EventRepository,
    VerificationLogRecord,
)
from pih.store.repository import IntelRepository

# 中文展示映射——模板与 CLI 共用（DB 存英文 key，展示层映射）
STATUS_LABELS: dict[str, str] = {
    STATUS_PENDING: "待核实",
    STATUS_SINGLE_SOURCE: "单源确认",
    STATUS_CONFIRMED: "多源确认",
    STATUS_REFUTED: "已证伪",
    STATUS_EXPIRED: "已过期",
}

# 状态枚举集合供 CLI verify / 模板下拉复用
STATUS_ORDER = (
    STATUS_PENDING,
    STATUS_SINGLE_SOURCE,
    STATUS_CONFIRMED,
    STATUS_REFUTED,
    STATUS_EXPIRED,
)


def normalize_subject(subject: str, pack: dict) -> str:
    """主体归一化：领域包 competitors.aliases → display_name 映射；未命中返回 strip 后原值。

    例：领域包 competitors 含 {display_name: "三一", aliases: ["三一重工", "SANY", "三一集团"]}
        normalize_subject("三一重工", pack) → "三一"
        normalize_subject("某小厂", pack)    → "某小厂"

    匹配规则：strip + 大小写不敏感（中文不受 lower 影响，英文别名如 SANY/sany 归一）。
    与 extraction.is_placeholder_subject 同款 strip+lower 比对模式。
    """
    s = subject.strip()
    if not s:
        return s
    alias_map: dict[str, str] = {}
    for c in pack.get("competitors", []):
        display = c["display_name"]
        alias_map[display.strip().lower()] = display
        for alias in c.get("aliases", []):
            alias_map[alias.strip().lower()] = display
    return alias_map.get(s.lower(), s)


@dataclass(frozen=True)
class EventWithLog:
    """详情页事件区数据——event 主信息 + 跃迁历史时间线。"""

    event: EventRecord | None
    logs: list[VerificationLogRecord]


class EventService:
    """事件聚类与核实状态机的业务编排层。"""

    def __init__(
        self,
        repo: EventRepository,
        intel_repo: IntelRepository,
        pack: dict,
    ) -> None:
        self._repo = repo
        self._intel = intel_repo
        self._pack = pack

    def cluster(self, intel_id: int) -> int | None:
        """对单条 extracted 情报执行聚类，返回挂入的 event_id（失败返回 None）。

        流程：
        1. 取 intel_item（含 subject/event_type/fetched_at/source_id）
        2. 主体归一化
        3. 查匹配事件（±7 天窗）；命中则挂入并判异源跃迁；未命中则新建
        4. 失败不抛——调用方（ProcessRunner）容错主流程不阻塞

        非 extracted 条目调用方不应传入；本方法不强校验（容错）。
        """
        rec = self._intel.get(intel_id)
        if rec is None or not rec.subject or not rec.event_type:
            return None

        subject_norm = normalize_subject(rec.subject, self._pack)
        event_id = self._repo.find_matching_event(
            subject_norm, rec.event_type, rec.fetched_at
        )
        if event_id is None:
            event_id = self._repo.create_event(
                subject_norm, rec.event_type, rec.fetched_at
            )

        self._repo.attach_and_advance(
            intel_id=intel_id,
            event_id=event_id,
            source_id=rec.source_id,
            fetched_at=rec.fetched_at,
        )
        return event_id

    # ---- 人工终态 ----

    def list_ready_for_manual(self, limit: int = 50) -> list[EventRecord]:
        return self._repo.list_ready_for_manual(limit=limit)

    def confirm(self, event_id: int, operator: str = "operator") -> bool:
        return self._repo.confirm(event_id, operator=operator)

    def refute(self, event_id: int, reason: str, operator: str = "operator") -> bool:
        if not reason or not reason.strip():
            raise ValueError("证伪必须填写理由（架构 §6.1 终态必填 reason）")
        return self._repo.refute(event_id, reason.strip(), operator=operator)

    def get_event_with_log(self, event_id: int | None) -> EventWithLog:
        """详情页用——event_id 为 None 时返回空态（情报未挂事件）。"""
        if event_id is None:
            return EventWithLog(event=None, logs=[])
        event = self._repo.get_event(event_id)
        if event is None:
            return EventWithLog(event=None, logs=[])
        logs = self._repo.list_verification_log(event_id)
        return EventWithLog(event=event, logs=logs)


def event_state_weight(status: str | None, pack: dict) -> float:
    """从领域包 ranking.event_state_weights 读 W_c；缺省回退默认 0.5。

    SQL ORDER BY 拼接用——不上 SQL 函数，Python 侧读领域包后用 CASE WHEN 注入。
    """
    if status is None:
        return 0.0  # 未挂事件（pending 条目或非 extracted）排在最后
    weights = pack.get("ranking", {}).get("event_state_weights", {})
    return float(weights.get(status, 0.5))


def admiralty_weight(admiralty_code: str | None, pack: dict) -> float:
    """Admiralty 码 → 数值权重（架构 §6.2 简化：取 reliability×credibility 较小值线性组合）。

    admiralty_code 形如 "B2"——首字符 reliability（A-F），次字符 credibility（1-6）。
    两者分别查领域包权重表，取较小值（短板决定，架构 §6.2 原文）。
    """
    if not admiralty_code or len(admiralty_code) < 2:
        return 0.0
    ranking = pack.get("ranking", {})
    rel_w = ranking.get("reliability_weights", {})
    cred_w = ranking.get("credibility_weights", {})
    rel = rel_w.get(admiralty_code[0], 0.0)
    cred = cred_w.get(admiralty_code[1], 0.0)
    return min(float(rel), float(cred))
