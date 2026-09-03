"""source 健康统计仓储（TASK-4.01.01 D9）。

健康是「每源一行」的标量状态，挂 source 表不加表：
- record_success：连续失败清零 + last_success_at
- record_failure：连续失败 +1 + last_failure_at/reason（连续 3 次触发站内信
  告警的判定底座，TASK-4.02.01 消费）
语义（设计 D9'）：job 级异常=信源失败；条目级 dead 行不算（算 pipeline_run
的 items_failed）。
"""
from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class SourceHealthRepository:
    """source 健康列的唯一写手（调度器 job 回调）。"""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def record_success(self, source_id: str) -> None:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE source
                SET consecutive_failures = 0, last_success_at = now()
                WHERE id = %s
                """,
                (source_id,),
            )

    def record_failure(self, source_id: str, reason: str) -> None:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE source
                SET consecutive_failures = consecutive_failures + 1,
                    last_failure_at = now(),
                    last_failure_reason = %s
                WHERE id = %s
                """,
                (reason, source_id),
            )

    def get_health(self, source_id: str) -> dict[str, Any] | None:
        with self._pool.connection() as conn, conn.cursor(
            row_factory=dict_row
        ) as cur:
            cur.execute(
                """
                SELECT id AS source_id, consecutive_failures, last_failure_at,
                       last_failure_reason, last_success_at
                FROM source WHERE id = %s
                """,
                (source_id,),
            )
            row = cur.fetchone()
        return dict(row) if row else None
