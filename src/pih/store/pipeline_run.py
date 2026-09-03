"""pipeline_run 运行留痕仓储（TASK-4.01.01，D6 遗留落地）。

doc-2 §7/§8：每次调度运行的吞吐/失败/时长（token 列预留，处理接力
TASK-4.01.2 启用）——1 人运营的巡检底座。
"""
from __future__ import annotations

from psycopg_pool import ConnectionPool


class PipelineRunRepository:
    """pipeline_run 表的唯一写手（调度器 job 回调）。"""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def record_run(
        self,
        *,
        source_id: str,
        run_type: str,
        duration_ms: int,
        ok: bool,
        items_new: int = 0,
        items_skipped: int = 0,
        items_failed: int = 0,
        error: str | None = None,
    ) -> None:
        """记一次运行。run_type：startup（启动扫）/ scheduled（频率触发）/ manual。"""
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline_run
                (source_id, run_type, duration_ms, ok, items_new,
                 items_skipped, items_failed, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source_id, run_type, duration_ms, ok, items_new,
                    items_skipped, items_failed, error,
                ),
            )
