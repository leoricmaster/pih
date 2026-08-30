"""IntelRepository：情报条目落库与基础检索（Sprint 3 T4 + Sprint 4 T3）。

接口：
  save(item)          单条入库，幂等冲突 → SKIPPED
  save_batch(items)   批量入库（逐条 save，单条失败不阻塞）
  list_by_source(...)  按信源列出最近入库
  get(id)             单条详情
  list_pending(...)   待处理条目（Sprint 4：pih process 批处理入口）
  write_process_result(...)  写回抽取结果与处理状态（Sprint 4）
  list_by_filter(...)  结构化筛选（Sprint 4：S1.1.1 CLI 子集）

不引入 ORM；SQL 原生，模型用 dataclass。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import ConnectionPool

from pih.collect.rawitem import RawItem
from pih.store.errors import IntegrityConflict

INSERT_SQL = """
    INSERT INTO intel_item
        (source_id, url, title, list_url, fetched_at, http_status,
         content_type, encoding, snapshot_id, content_sha1, raw_html)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (content_sha1) DO NOTHING
    RETURNING id
"""

# process_status 枚举（应用层约束，迁移 0002 落列）
STATUS_PENDING = "pending"
STATUS_EXTRACTED = "extracted"
STATUS_FILTERED_OUT = "filtered_out"
STATUS_NEEDS_MANUAL = "needs_manual"

_COLUMNS = """
    id, source_id, url, title, list_url, fetched_at,
    http_status, content_type, encoding, snapshot_id,
    content_sha1, raw_html, event_id, created_at,
    subject, event_type, facts, inferences, tags, quant_params,
    admiralty_code, process_status, process_error, process_meta, processed_at
"""

# Sprint 6 LEFT JOIN event 后需 i. 前缀防 id 字段歧义；带回 event_status
_COLUMNS_WITH_EVENT = ", ".join(
    f"i.{c.strip()}" for c in _COLUMNS.split(",") if c.strip()
) + ", e.status AS event_status"

# JOIN 查询用的 i. 限定版（list_pending 与 source 表联结防歧义）
_COLUMNS_I = ", ".join(f"i.{c.strip()}" for c in _COLUMNS.split(","))


@dataclass(frozen=True)
class SaveOutcome:
    """save 单条结果。"""

    SAVED = "saved"
    SKIPPED = "skipped"
    FAILED = "failed"

    status: str
    intel_id: int | None = None
    reason: str | None = None
    content_sha1: str | None = None


@dataclass(frozen=True)
class ProcessResult:
    """process 层单条处理结果（write_process_result 的写回载荷，Sprint 4）。

    status=extracted 时结构化字段全填；filtered_out/needs_manual 时
    结构化字段留 None，error 记录原因（条目保留不丢弃）。
    """

    status: str
    subject: str | None = None
    event_type: str | None = None
    facts: str | None = None
    inferences: str | None = None
    tags: list[str] | None = None
    quant_params: dict | None = None
    admiralty_code: str | None = None
    error: str | None = None
    meta: dict | None = None


@dataclass(frozen=True)
class IntelRecord:
    """从 DB 读出的情报条目。

    基础字段同 RawItem + id/created_at；Sprint 4 结构化字段与治理字段
    带默认值（迁移 0002 之前的语义/旧行均为空）。source_reliability 非表列，
    仅 list_pending 的 JOIN source 填充（Admiralty 拼装用）。
    Sprint 6 增 event_status 字段（LEFT JOIN event 填充，未挂事件为 None）。
    """

    id: int
    source_id: str
    url: str
    title: str
    list_url: str
    fetched_at: datetime
    http_status: int
    content_type: str | None
    encoding: str | None
    snapshot_id: str
    content_sha1: str
    raw_html: str
    event_id: int | None
    created_at: datetime
    subject: str | None = None
    event_type: str | None = None
    facts: str | None = None
    inferences: str | None = None
    tags: list | None = None
    quant_params: dict | None = None
    admiralty_code: str | None = None
    process_status: str | None = None
    process_error: str | None = None
    process_meta: dict | None = None
    processed_at: datetime | None = None
    source_reliability: str | None = None
    event_status: str | None = None  # Sprint 6: LEFT JOIN event 填充，未挂事件为 None


class IntelRepository:
    """情报库基础检索（最小切片，规格 D5）。"""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def save(self, item: RawItem) -> SaveOutcome:
        """单条入库。content_sha1 冲突 → SKIPPED；其他异常 → FAILED。

        ON CONFLICT DO NOTHING + RETURNING id：插入成功返回 id，
        冲突时无行返回 → SKIPPED。
        """
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                INSERT_SQL,
                (
                    item.source_id, item.url, item.title, item.list_url,
                    item.fetched_at, item.http_status, item.content_type,
                    item.encoding, item.snapshot_id, item.content_sha1,
                    item.raw_html,
                ),
            )
            row = cur.fetchone()
        if row is not None:
            return SaveOutcome(
                status=SaveOutcome.SAVED, intel_id=row[0], content_sha1=item.content_sha1
            )
        return SaveOutcome(status=SaveOutcome.SKIPPED, content_sha1=item.content_sha1)

    def save_batch(self, items: list[RawItem]) -> list[SaveOutcome]:
        """批量入库，逐条 save；单条异常不阻塞其他条目（D8 容错）。"""
        outcomes: list[SaveOutcome] = []
        for item in items:
            try:
                outcomes.append(self.save(item))
            except IntegrityConflict:
                outcomes.append(
                    SaveOutcome(status=SaveOutcome.SKIPPED, content_sha1=item.content_sha1)
                )
            except Exception as exc:  # noqa: BLE001 容错策略 D8：单条失败不阻塞
                outcomes.append(
                    SaveOutcome(
                        status=SaveOutcome.FAILED,
                        reason=str(exc),
                        content_sha1=item.content_sha1,
                    )
                )
        return outcomes

    def list_by_source(
        self, source_id: str, limit: int = 50, before: datetime | None = None
    ) -> list[IntelRecord]:
        """按信源列出最近入库（fetched_at DESC）。

        Args:
            before: 若给定，只返回 fetched_at < before 的条目（分页游标）
        """
        if before is None:
            sql = f"""
                SELECT {_COLUMNS}
                FROM intel_item
                WHERE source_id = %s
                ORDER BY fetched_at DESC
                LIMIT %s
            """
            params: tuple = (source_id, limit)
        else:
            sql = f"""
                SELECT {_COLUMNS}
                FROM intel_item
                WHERE source_id = %s AND fetched_at < %s
                ORDER BY fetched_at DESC
                LIMIT %s
            """
            params = (source_id, before, limit)

        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [IntelRecord(**r) for r in rows]

    def get(self, intel_id: int) -> IntelRecord | None:
        sql = f"""
            SELECT {_COLUMNS_WITH_EVENT}
            FROM intel_item i
            LEFT JOIN event e ON e.id = i.event_id
            WHERE i.id = %s
        """
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (intel_id,))
            row = cur.fetchone()
        return IntelRecord(**row) if row else None

    def list_pending(
        self, source_id: str | None = None, limit: int = 20
    ) -> list[IntelRecord]:
        """取待处理条目（process_status='pending'），先老后新（fetched_at ASC）。

        JOIN source 带回 reliability（Admiralty 拼装输入，Sprint 4 规格 §3.6）。
        """
        if source_id is None:
            sql = f"""
                SELECT {_COLUMNS_I}, s.reliability AS source_reliability
                FROM intel_item i
                JOIN source s ON s.id = i.source_id
                WHERE i.process_status = %s
                ORDER BY i.fetched_at ASC
                LIMIT %s
            """
            params: tuple = (STATUS_PENDING, limit)
        else:
            sql = f"""
                SELECT {_COLUMNS_I}, s.reliability AS source_reliability
                FROM intel_item i
                JOIN source s ON s.id = i.source_id
                WHERE i.process_status = %s AND i.source_id = %s
                ORDER BY i.fetched_at ASC
                LIMIT %s
            """
            params = (STATUS_PENDING, source_id, limit)
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [IntelRecord(**r) for r in rows]

    def write_process_result(self, intel_id: int, result: ProcessResult) -> None:
        """写回单条处理结果：结构化字段 + 状态 + 时间戳 + meta。

        仅 pending 条目会被处理（list_pending 选择），无并发写冲突场景；
        extracted 全字段写入，filtered_out/needs_manual 仅状态与原因。
        """
        sql = """
            UPDATE intel_item SET
                subject = %s,
                event_type = %s,
                facts = %s,
                inferences = %s,
                tags = %s,
                quant_params = %s,
                admiralty_code = %s,
                process_status = %s,
                process_error = %s,
                process_meta = %s,
                processed_at = NOW()
            WHERE id = %s
        """
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    result.subject, result.event_type, result.facts, result.inferences,
                    # tags/quant_params 列 NOT NULL：未抽取（filtered_out/needs_manual）
                    # 时写 schema 默认空值而非 NULL
                    Json(result.tags or []),
                    Json(result.quant_params or {}),
                    result.admiralty_code, result.status, result.error,
                    Json(result.meta) if result.meta is not None else None,
                    intel_id,
                ),
            )

    def list_by_filter(
        self,
        *,
        subject: str | None = None,
        event_type: str | None = None,
        tag: str | None = None,
        admiralty: str | None = None,
        source_id: str | None = None,
        process_status: str | None = None,
        event_status: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        before: datetime | None = None,
        limit: int = 50,
        ranking: dict | None = None,
    ) -> list[IntelRecord]:
        """结构化筛选（S1.1.1，Sprint 4 CLI 子集 + Sprint 5a Web/API 同源扩展 + Sprint 6 事件）。

        subject/event_type/admiralty/process_status/event_status 精确匹配；tag 用 JSONB
        containment（tags @> [tag]）；since/until 走 fetched_at 闭区间；
        before 为游标（fetched_at < before，分页用）。

        排序（Sprint 6 切换）：
        - ranking=None（默认回退简版）：admiralty_code ASC NULLS LAST, fetched_at DESC, id DESC
          （Sprint 5a 简版，CLI 与未注入 ranking 的调用方用）
        - ranking 给定：score = W_c(event.status) × map(admiralty) DESC, fetched_at DESC, id DESC
          （架构 §6.2；decay 留时效 Sprint，本 Sprint 兜底 1.0）
          ranking 形如 {event_state_weights: {...}, reliability_weights: {...}, credibility_weights: {...}}
          从领域包 pack.ranking 读取，由 QueryService 注入（store 层不依赖领域包）。

        process_status 筛选（Sprint 5b）：needs_manual 人工复核队列的可达路径。
        event_status 筛选（Sprint 6）：按事件核实状态筛选（LEFT JOIN event）。
        """
        clauses: list[str] = []
        params: list = []
        if subject is not None:
            clauses.append("i.subject = %s")
            params.append(subject)
        if event_type is not None:
            clauses.append("i.event_type = %s")
            params.append(event_type)
        if tag is not None:
            clauses.append("i.tags @> %s")
            params.append(Json([tag]))
        if admiralty is not None:
            clauses.append("i.admiralty_code = %s")
            params.append(admiralty)
        if source_id is not None:
            clauses.append("i.source_id = %s")
            params.append(source_id)
        if process_status is not None:
            clauses.append("i.process_status = %s")
            params.append(process_status)
        if event_status is not None:
            clauses.append("e.status = %s")
            params.append(event_status)
        if since is not None:
            clauses.append("i.fetched_at >= %s")
            params.append(since)
        if until is not None:
            clauses.append("i.fetched_at <= %s")
            params.append(until)
        if before is not None:
            clauses.append("i.fetched_at < %s")
            params.append(before)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        if ranking is not None:
            order_sql = _build_ranked_order_sql(ranking)
        else:
            order_sql = (
                "i.admiralty_code ASC NULLS LAST, i.fetched_at DESC, i.id DESC"
            )

        sql = f"""
            SELECT {_COLUMNS_WITH_EVENT}
            FROM intel_item i
            LEFT JOIN event e ON e.id = i.event_id
            {where}
            ORDER BY {order_sql}
            LIMIT %s
        """
        params.append(limit)
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        return [IntelRecord(**r) for r in rows]


def _build_ranked_order_sql(ranking: dict) -> str:
    """从领域包 ranking 节拼 CASE WHEN 权重列到 ORDER BY（架构 §6.2 简化版）。

    score = W_c(event.status) × min(rel_weight(admiralty[0]), cred_weight(admiralty[1]))
    decay 留时效 Sprint，本 Sprint 兜底 1.0；未挂事件（event.status NULL）W_c=0 排末尾。

    SQL 不上 PG 函数——Python 侧读领域包后用 CASE WHEN 注入数值，避免迁移加函数。
    """
    event_w = ranking.get("event_state_weights", {})
    rel_w = ranking.get("reliability_weights", {})
    cred_w = ranking.get("credibility_weights", {})

    def case_str(mapping: dict, expr: str, default: str = "0.0") -> str:
        """生成 CASE expr WHEN k THEN v ... ELSE default END。"""
        if not mapping:
            return default
        branches = " ".join(
            f"WHEN {expr} = '{k}' THEN {float(v)}" for k, v in mapping.items()
        )
        return f"CASE {branches} ELSE {default} END"

    w_c = case_str(event_w, "e.status", "0.0")
    rel = case_str(rel_w, "LEFT(i.admiralty_code, 1)", "0.0")
    cred = case_str(cred_w, "SUBSTRING(i.admiralty_code FROM 2 FOR 1)", "0.0")
    # Admiralty 权重 = min(rel, cred)（架构 §6.2 短板决定）
    admiralty_w = f"LEAST({rel}, {cred})"
    score = f"({w_c} * {admiralty_w})"
    return f"{score} DESC NULLS LAST, i.fetched_at DESC, i.id DESC"
