"""EventRepository：事件聚类与核实状态机的 SQL 层（Backlog S1.3.1）。

接口：
  find_matching_event(...)   ±7 天窗查询命中已有事件
  create_event(...)          新建 pending 事件 + 首条 verification_log
  attach_and_advance(...)    挂 intel_item.event_id + 判第二独立信源 + 必要时自动跃迁（事务）
  list_ready_for_manual()    已具备升级条件的人工队列
  confirm(...) / refute(...) 终态人工跃迁 + 写 log
  get_event(...)             单条 event 详情
  list_verification_log(...) 事件状态跃迁历史（详情页时间线用）
  list_intel_ids_without_event(...)  backfill 入口

状态枚举（架构 §6.1，英文 key 与领域包 ranking 对齐）：
  pending / single_source / confirmed / refuted / expired
自动跃迁 operator=system；终态人工 operator 由调用方传入。

不引入 ORM；SQL 原生，模型用 dataclass（与 repository.py/feedback.py 同风格）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from pih.store.repository import STATUS_EXTRACTED

# 状态枚举（与领域包 ranking.event_state_weights key 对齐，详见 event.py）
STATUS_PENDING = "pending"
STATUS_SINGLE_SOURCE = "single_source"
STATUS_CONFIRMED = "confirmed"
STATUS_REFUTED = "refuted"
STATUS_EXPIRED = "expired"

# 自动跃迁：第二独立信源命中时 pending → single_source
AUTO_ADVANCE_REASON = "第二独立信源命中"

# 时间窗 ±7 天（架构 §6.1 / S1.3.1 AC2）
TIME_WINDOW = timedelta(days=7)


@dataclass(frozen=True)
class EventRecord:
    """event 表一行。"""

    id: int
    subject: str
    event_type: str
    status: str
    source_count: int
    ready_for_manual: bool
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True)
class VerificationLogRecord:
    """verification_log 表一行（详情页时间线一行）。"""

    id: int
    event_id: int
    from_status: str | None
    to_status: str
    operator: str
    reason: str | None
    created_at: datetime


@dataclass(frozen=True)
class AttachOutcome:
    """attach_and_advance 的返回——供 EventService 上层判断日志输出。"""

    event_id: int
    is_new_source: bool           # 本次挂入是否带来新独立信源
    status_advanced: bool         # 是否触发了 pending → single_source 自动跃迁
    new_status: str               # 跃迁后状态（未跃迁则为原状态）


class EventRepository:
    """事件聚类 + 状态机的 SQL 层。"""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    # ---- 查询 ----

    def find_matching_event(
        self, subject: str, event_type: str, fetched_at: datetime
    ) -> int | None:
        """查找主体+事件类型相同、时间窗 ±7 天内的最近事件。

        匹配规则（架构 §6.1）：subject/event_type 精确匹配（subject 已归一化），
        fetched_at 与 event.last_seen_at 差值绝对值 ≤ 7 天。
        多条命中取 last_seen_at 最近的一个。
        """
        sql = """
            SELECT id FROM event
            WHERE subject = %s AND event_type = %s
              AND last_seen_at BETWEEN %s AND %s
            ORDER BY last_seen_at DESC, id DESC
            LIMIT 1
        """
        lower = fetched_at - TIME_WINDOW
        upper = fetched_at + TIME_WINDOW
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (subject, event_type, lower, upper))
            row = cur.fetchone()
        return row[0] if row else None

    def get_event(self, event_id: int) -> EventRecord | None:
        sql = """
            SELECT id, subject, event_type, status, source_count,
                   ready_for_manual, first_seen_at, last_seen_at
            FROM event WHERE id = %s
        """
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (event_id,))
            row = cur.fetchone()
        return EventRecord(**row) if row else None

    def list_verification_log(self, event_id: int) -> list[VerificationLogRecord]:
        """事件状态跃迁历史——详情页时间线（created_at DESC）。"""
        sql = """
            SELECT id, event_id, from_status, to_status, operator, reason, created_at
            FROM verification_log
            WHERE event_id = %s
            ORDER BY created_at DESC, id DESC
        """
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (event_id,))
            rows = cur.fetchall()
        return [VerificationLogRecord(**r) for r in rows]

    def list_ready_for_manual(self, limit: int = 50) -> list[EventRecord]:
        """已具备升级条件的事件（人工队列，first_seen_at ASC）。"""
        sql = """
            SELECT id, subject, event_type, status, source_count,
                   ready_for_manual, first_seen_at, last_seen_at
            FROM event
            WHERE ready_for_manual = TRUE AND status IN (%s, %s)
            ORDER BY first_seen_at ASC, id ASC
            LIMIT %s
        """
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (STATUS_PENDING, STATUS_SINGLE_SOURCE, limit))
            rows = cur.fetchall()
        return [EventRecord(**r) for r in rows]

    def list_intel_ids_without_event(
        self, source_id: str | None = None, limit: int = 200
    ) -> list[int]:
        """backfill 入口：已 extracted 但 event_id IS NULL 的条目（fetched_at ASC）。"""
        if source_id is None:
            sql = """
                SELECT id FROM intel_item
                WHERE process_status = %s AND event_id IS NULL
                ORDER BY fetched_at ASC LIMIT %s
            """
            params: tuple = (STATUS_EXTRACTED, limit)
        else:
            sql = """
                SELECT id FROM intel_item
                WHERE process_status = %s AND event_id IS NULL AND source_id = %s
                ORDER BY fetched_at ASC LIMIT %s
            """
            params = (STATUS_EXTRACTED, source_id, limit)
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [r[0] for r in rows]

    # ---- 写入 ----

    def create_event(self, subject: str, event_type: str, fetched_at: datetime) -> int:
        """新建 pending 事件 + 首条 verification_log（to_status=pending, from_status=NULL）。

        first_seen_at / last_seen_at 显式设为 fetched_at——保证时间窗判定跟随
        情报 fetched_at 而非 NOW()（避免 NOW() 漂移导致 ±7 天窗误判）。
        """
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO event (subject, event_type, status, first_seen_at, last_seen_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (subject, event_type, STATUS_PENDING, fetched_at, fetched_at),
            )
            event_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO verification_log (event_id, from_status, to_status, operator, reason)
                VALUES (%s, NULL, %s, 'system', '事件创建')
                """,
                (event_id, STATUS_PENDING),
            )
            conn.commit()
        return event_id

    def attach_and_advance(
        self,
        *,
        intel_id: int,
        event_id: int,
        source_id: str,
        fetched_at: datetime,
    ) -> AttachOutcome:
        """挂 intel_item 到 event + 判第二独立信源 + 必要时自动跃迁（单事务原子）。

        步骤：
        1. UPDATE intel_item SET event_id = %s（已挂则幂等）
        2. 查该 event 下 DISTINCT source_id（不含当前 intel）
        3. 若新 source_id 不在集合 → source_count += 1
        4. 若 source_count 现到 2 且 status=pending → 跃迁 single_source + 写 log + ready=true
        5. last_seen_at = GREATEST(last_seen_at, fetched_at)
        """
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE intel_item SET event_id = %s WHERE id = %s",
                (event_id, intel_id),
            )
            cur.execute(
                """
                SELECT DISTINCT source_id FROM intel_item
                WHERE event_id = %s AND id != %s
                """,
                (event_id, intel_id),
            )
            existing_sources = {r[0] for r in cur.fetchall()}

            is_new_source = source_id not in existing_sources
            status_advanced = False
            new_status = STATUS_PENDING  # 默认假设；下面查真实状态

            cur.execute("SELECT status FROM event WHERE id = %s", (event_id,))
            current_status_row = cur.fetchone()
            current_status = current_status_row[0] if current_status_row else STATUS_PENDING

            if is_new_source:
                cur.execute(
                    """
                    UPDATE event
                    SET source_count = source_count + 1,
                        last_seen_at = GREATEST(last_seen_at, %s)
                    WHERE id = %s
                    """,
                    (fetched_at, event_id),
                )
                if current_status == STATUS_PENDING and len(existing_sources) + 1 >= 2:
                    cur.execute(
                        """
                        UPDATE event
                        SET status = %s, ready_for_manual = TRUE
                        WHERE id = %s
                        """,
                        (STATUS_SINGLE_SOURCE, event_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO verification_log
                            (event_id, from_status, to_status, operator, reason)
                        VALUES (%s, %s, %s, 'system', %s)
                        """,
                        (event_id, STATUS_PENDING, STATUS_SINGLE_SOURCE, AUTO_ADVANCE_REASON),
                    )
                    status_advanced = True
                    new_status = STATUS_SINGLE_SOURCE
                else:
                    new_status = current_status
            else:
                cur.execute(
                    "UPDATE event SET last_seen_at = GREATEST(last_seen_at, %s) WHERE id = %s",
                    (fetched_at, event_id),
                )
                new_status = current_status

            conn.commit()
        return AttachOutcome(
            event_id=event_id,
            is_new_source=is_new_source,
            status_advanced=status_advanced,
            new_status=new_status,
        )

    # ---- 人工终态跃迁 ----

    def confirm(self, event_id: int, operator: str = "operator") -> bool:
        """单源确认 → 多源确认（人工终态）。仅 single_source 状态可确认。

        Returns: True 跃迁成功；False 状态不匹配（调用方报错）。
        """
        return self._manual_transition(
            event_id,
            expected_from=STATUS_SINGLE_SOURCE,
            to_status=STATUS_CONFIRMED,
            operator=operator,
            reason=None,
        )

    def refute(self, event_id: int, reason: str, operator: str = "operator") -> bool:
        """证伪（人工终态，必填 reason）。pending 或 single_source 均可证伪。

        Returns: True 跃迁成功；False 状态不匹配。
        """
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT status FROM event WHERE id = %s", (event_id,))
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                return False
            current = row[0]
            if current not in (STATUS_PENDING, STATUS_SINGLE_SOURCE):
                conn.rollback()
                return False
            cur.execute(
                """
                UPDATE event
                SET status = %s, ready_for_manual = FALSE
                WHERE id = %s
                """,
                (STATUS_REFUTED, event_id),
            )
            cur.execute(
                """
                INSERT INTO verification_log (event_id, from_status, to_status, operator, reason)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (event_id, current, STATUS_REFUTED, operator, reason),
            )
            conn.commit()
        return True

    def _manual_transition(
        self,
        event_id: int,
        *,
        expected_from: str,
        to_status: str,
        operator: str,
        reason: str | None,
    ) -> bool:
        """单状态条件跃迁——失败回滚（用于 confirm）。"""
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT status FROM event WHERE id = %s", (event_id,))
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                return False
            current = row[0]
            if current != expected_from:
                conn.rollback()
                return False
            cur.execute(
                """
                UPDATE event
                SET status = %s, ready_for_manual = FALSE
                WHERE id = %s
                """,
                (to_status, event_id),
            )
            cur.execute(
                """
                INSERT INTO verification_log (event_id, from_status, to_status, operator, reason)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (event_id, current, to_status, operator, reason),
            )
            conn.commit()
        return True
