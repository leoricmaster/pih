"""notification 站内信仓储（TASK-4.02.01，doc-2 §7 运营层）。

告警与消费同一入口（§8）：create 由调度器告警钩子调用（恰达连续失败阈值
一次，设计 D10/D17）；未读= read_at IS NULL；标记已读走 mark_read。
"""
from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class NotificationRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def create(
        self, *, type: str, source_id: str | None, title: str, body: str = ""
    ) -> None:
        """写入一条站内信（type 枚举开放：source_health 先行）。"""
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notification (type, source_id, title, body)
                VALUES (%s, %s, %s, %s)
                """,
                (type, source_id, title, body),
            )

    def unread_count(self) -> int:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM notification WHERE read_at IS NULL"
            )
            return cur.fetchone()[0]

    def list_unread(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._pool.connection() as conn, conn.cursor(
            row_factory=dict_row
        ) as cur:
            cur.execute(
                """
                SELECT id, type, source_id, title, body, created_at
                FROM notification
                WHERE read_at IS NULL
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """历史（含已读，AC2）——按时间倒序。"""
        with self._pool.connection() as conn, conn.cursor(
            row_factory=dict_row
        ) as cur:
            cur.execute(
                """
                SELECT id, type, source_id, title, body, read_at, created_at
                FROM notification
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())

    def mark_read(self, notification_id: int) -> None:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE notification SET read_at = now() WHERE id = %s",
                (notification_id,),
            )
