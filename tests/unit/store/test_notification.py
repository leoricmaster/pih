"""notification 仓储单测（TASK-4.02.01）——SQL 契约（_MockConn 捕获）。"""
from __future__ import annotations

from unittest.mock import MagicMock


class _MockConn:
    def __init__(self) -> None:
        self.cursor_obj = MagicMock()
        self.cursor_obj.execute = MagicMock()
        self.cursor_obj.fetchone = MagicMock(return_value=None)
        self.cursor_obj.fetchall = MagicMock(return_value=[])
        self.cursor_obj.__enter__ = MagicMock(return_value=self.cursor_obj)
        self.cursor_obj.__exit__ = MagicMock(return_value=False)
        self.conn = MagicMock()
        self.conn.cursor.return_value = self.cursor_obj
        self.conn.__enter__ = MagicMock(return_value=self.conn)
        self.conn.__exit__ = MagicMock(return_value=False)
        self.pool = MagicMock()
        self.pool.connection.return_value = self.conn


class TestNotificationRepository:
    def test_create_inserts_row(self):
        from pih.store.notification import NotificationRepository

        m = _MockConn()
        NotificationRepository(m.pool).create(
            type="source_health", source_id="ccma",
            title="信源异常：中国工程机械工业协会 连续失败 3 次",
            body="ConnectError: timeout",
        )
        sql = m.cursor_obj.execute.call_args.args[0]
        assert "INSERT INTO notification" in sql
        params = m.cursor_obj.execute.call_args.args[1]
        assert params[0] == "source_health" and params[1] == "ccma"
        assert "连续失败 3 次" in params[2]

    def test_unread_count(self):
        from pih.store.notification import NotificationRepository

        m = _MockConn()
        m.cursor_obj.fetchone.return_value = (2,)
        assert NotificationRepository(m.pool).unread_count() == 2
        sql = m.cursor_obj.execute.call_args.args[0]
        assert "read_at IS NULL" in sql

    def test_list_unread_orders_recent_first(self):
        from pih.store.notification import NotificationRepository

        m = _MockConn()
        NotificationRepository(m.pool).list_unread(limit=5)
        sql = m.cursor_obj.execute.call_args.args[0]
        assert "ORDER BY created_at DESC" in sql

    def test_list_recent_includes_read(self):
        from pih.store.notification import NotificationRepository

        m = _MockConn()
        NotificationRepository(m.pool).list_recent(limit=50)
        sql = m.cursor_obj.execute.call_args.args[0]
        assert "read_at IS NOT NULL" not in sql  # 不滤已读（历史可查 AC2）

    def test_mark_read_sets_read_at(self):
        from pih.store.notification import NotificationRepository

        m = _MockConn()
        NotificationRepository(m.pool).mark_read(7)
        sql = m.cursor_obj.execute.call_args.args[0]
        assert "UPDATE notification" in sql
        assert "read_at = now()" in sql
        assert m.cursor_obj.execute.call_args.args[1] == (7,)
