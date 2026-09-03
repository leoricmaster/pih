"""IntelRepository：情报条目落库与基础检索。

接口：
  save(item)          单条入库，幂等冲突 → SKIPPED
  save_batch(items)   批量入库（逐条 save，单条失败不阻塞）
  list_by_source(...)  按信源列出最近入库
  get(id)             单条详情
  list_pending(...)   待处理条目（pih process 批处理入口）
  write_process_result(...)  写回抽取结果与处理状态
  list_by_filter(...)  结构化筛选（TASK-2.01.01，CLI/Web/API 共用）

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
        (source_id, source_type, url, title, list_url, fetched_at, http_status,
         content_type, encoding, snapshot_id, content_sha1, raw_html)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (content_sha1) DO NOTHING
    RETURNING id
"""

# process_status 枚举（应用层约束，迁移 0001 落列默认 pending）
STATUS_PENDING = "pending"
STATUS_EXTRACTED = "extracted"
STATUS_FILTERED_OUT = "filtered_out"
STATUS_NEEDS_MANUAL = "needs_manual"
STATUS_DEAD = "dead"

_COLUMNS = """
    id, source_id, source_type, url, title, list_url, fetched_at,
    http_status, content_type, encoding, snapshot_id,
    content_sha1, raw_html, event_id, created_at,
    subject, event_type, facts, inferences, tags, quant_params,
    admiralty_code, process_status, process_error, process_meta, processed_at
"""

# LEFT JOIN event 后需 i. 前缀防 id 字段歧义；带回 event_status
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
    """process 层单条处理结果（write_process_result 的写回载荷）。

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

    基础字段同 RawItem + id/created_at；结构化字段与治理字段
    带默认值（迁移 0002 之前的语义/旧行均为空）。source_reliability 非表列，
    仅 list_pending 的 JOIN source 填充（Admiralty 拼装用）。
    另有 event_status 字段（LEFT JOIN event 填充，未挂事件为 None）。
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
    source_type: str = "auto"
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
    event_status: str | None = None  # LEFT JOIN event 填充，未挂事件为 None


class IntelRepository:
    """情报库基础检索（最小切片）。"""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def save(self, item: RawItem, source_type: str = "auto") -> SaveOutcome:
        """单条入库。content_sha1 冲突 → SKIPPED；其他异常 → FAILED。

        ON CONFLICT DO NOTHING + RETURNING id：插入成功返回 id，
        冲突时无行返回 → SKIPPED。source_type 区分采集(auto)/人工(manual)，
        ADR-009 汇聚语义的物理载体（ADR-011）。
        """
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                INSERT_SQL,
                (
                    item.source_id, source_type, item.url, item.title, item.list_url,
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

    def save_batch(
        self, items: list[RawItem], source_type: str = "auto"
    ) -> list[SaveOutcome]:
        """批量入库，逐条 save；单条异常不阻塞其他条目（D8 容错）。"""
        outcomes: list[SaveOutcome] = []
        for item in items:
            try:
                outcomes.append(self.save(item, source_type=source_type))
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

    def record_failure(
        self,
        *,
        source_id: str,
        url: str,
        list_url: str,
        reason: str,
        fetched_at: str,
        http_status: int = 0,
        source_type: str = "auto",
    ) -> None:
        """AC4：fetch 失败落一行——状态 dead，process_error 记失败原因（ADR-011）。

        抓取未完成无正文/快照；snapshot_id 以失败标识占位满足 NOT NULL 守卫，
        content_sha1 取 url+reason 指纹（失败行幂等）。process_status=dead 使其
        不进检索视图（收件箱视图可按状态筛出，漏报审计）。
        """
        import hashlib

        fail_sha = hashlib.sha1(f"{url}|{reason}".encode()).hexdigest()
        sql = """
            INSERT INTO intel_item
                (source_id, source_type, url, title, list_url, fetched_at, http_status,
                 snapshot_id, content_sha1, raw_html, process_status, process_error)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    source_id, source_type, url, "(抓取失败)", list_url, fetched_at,
                    http_status, "__no_snapshot_fetch_failed__", fail_sha, "",
                    STATUS_DEAD, reason,
                ),
            )

    def list_inbox(
        self,
        *,
        source_id: str | None = None,
        process_status: str | None = None,
        limit: int = 50,
    ) -> list[IntelRecord]:
        """收件箱视图：列出未抽取条目（pending/needs_manual/filtered_out/dead）。

        ADR-011 两视图之一——读 intel_item 非 extracted 状态子集。process_status
        给定时筛单态（漏报审计筛 filtered_out）；不给定则取全部非 extracted。
        排序 fetched_at DESC（最近采集在前）。
        """
        clauses = ["process_status != %s"]
        params: list = [STATUS_EXTRACTED]
        if process_status is not None:
            clauses.append("process_status = %s")
            params.append(process_status)
        if source_id is not None:
            clauses.append("source_id = %s")
            params.append(source_id)
        sql = (
            f"SELECT {_COLUMNS} FROM intel_item "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY fetched_at DESC LIMIT %s"
        )
        params.append(limit)
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        return [IntelRecord(**r) for r in rows]

    def mark_status(self, intel_id: int, status: str, error: str | None = None) -> None:
        """写回处理状态：filtered_out（粗筛）/ dead（失败终态）/ 重置 pending（重放）。

        轻量状态写——不触结构化字段（write_process_result 留抽取用）。AC4 可重放
        = mark_status(id, 'pending') 重入处理链；丢弃 = 留 dead 态留痕。
        """
        sql = (
            "UPDATE intel_item SET process_status = %s, "
            "process_error = COALESCE(%s, process_error), processed_at = NOW() "
            "WHERE id = %s"
        )
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (status, error, intel_id))

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

        JOIN source 带回 reliability（Admiralty 拼装输入，架构 §6.2）。
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
        """结构化筛选（Backlog TASK-2.01.01，CLI 与 Web/API 同源共用，含事件状态维度）。

        subject/event_type/process_status/event_status 精确匹配；admiralty 为
        来源可靠性 ≥ 档（left(code,1) <= 档位，TASK-2.01.01 D1）；tag 用 JSONB
        containment（tags @> [tag]）；since/until 走 fetched_at 闭区间；
        before 为游标（fetched_at < before，分页用）。

        排序：
        - ranking=None（默认回退简版回退）：admiralty_code ASC NULLS LAST, fetched_at DESC, id DESC
          （简版回退，CLI 与未注入 ranking 的调用方用）
        - ranking 给定：score = W_c(event.status) × map(admiralty) DESC, fetched_at DESC, id DESC
          （架构 §6.2；decay 留时效管理（未来需求，未分解），当前兜底 1.0）
          ranking 形如 {event_state_weights: {...}, reliability_weights: {...},
          credibility_weights: {...}}
          从领域包 pack.ranking 读取，由 QueryService 注入（store 层不依赖领域包）。

        process_status 筛选：needs_manual 人工复核队列的可达路径（TASK-1.02.01 AC3）。
        event_status 筛选：按事件核实状态筛选（LEFT JOIN event）。
        """
        clauses: list[str] = []
        params: list = []
        if event_status is None:
            # D7（TASK-2.02.02 AC3）：检索默认隐藏已证伪事件的条目
            # （doc-2 §6.3「已证伪 0 默认不出现在结果」）；无挂事件条目不受影响；
            # 显式 event_status=refuted 可查（审计可达，不进本分支）。
            clauses.append("(e.status IS NULL OR e.status <> 'refuted')")
        if subject is not None:
            clauses.append("i.subject = %s")
            params.append(subject)
        if event_type is not None:
            clauses.append("i.event_type = %s")
            params.append(event_type)
        if tag is not None:
            # Json 参数以 json 类型绑定，containment 需显式 cast jsonb
            # （真实 PG 无 jsonb @> json 操作符——integration 首跑抓到，单测 mock 掩盖）
            clauses.append("i.tags @> %s::jsonb")
            params.append(Json([tag]))
        if admiralty is not None:
            # TASK-2.01.01 D1：置信度筛选 = 来源可靠性 ≥ 所选档（A 最优，
            # A–F 字典序升序；单轴门槛，可信度维度由排序承载）
            clauses.append("left(i.admiralty_code, 1) <= %s")
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

    def list_low_confidence(self, limit: int = 50) -> list[IntelRecord]:
        """低置信度情报（TASK-2.02.02 AC1 队列②，D6 阈值）。

        Admiralty 任一维度进低档即入列：可信度 4–6（存疑起）或可靠性 D–F；
        仅 extracted 成品；已证伪事件条目不入列（D6/D7 一致口径）。
        取回 fetched_at DESC，由调用方（核实页路由）按 score 升序重排。
        """
        sql = f"""
            SELECT {_COLUMNS_WITH_EVENT}
            FROM intel_item i
            LEFT JOIN event e ON e.id = i.event_id
            WHERE process_status = 'extracted'
              AND (SUBSTRING(admiralty_code FROM 2 FOR 1) IN ('4','5','6')
                   OR LEFT(admiralty_code, 1) IN ('D','E','F'))
              AND (e.status IS NULL OR e.status <> 'refuted')
            ORDER BY fetched_at DESC, id DESC
            LIMIT %s
        """
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
        return [IntelRecord(**r) for r in rows]


def _build_ranked_order_sql(ranking: dict) -> str:
    """从领域包 ranking 节拼 CASE WHEN 权重列到 ORDER BY（架构 §6.2 简化版）。

    score = W_c(event.status) × min(rel_weight(admiralty[0]), cred_weight(admiralty[1]))
    decay 留时效管理（未分解的未来需求），当前兜底 1.0；未挂事件（event.status NULL）W_c=0 排末尾。

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
