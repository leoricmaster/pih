"""InboxRepository 单元测试——mock pool 验 SQL/分支（TASK-1.01.02 D1）。

采集先落盘 inbox_item（不再直写 intel_item）。mock 策略同 test_repository：
cursor.fetchone/fetchall 控制返回；验 execute SQL 与参数。不依赖真实 DB。
"""
from __future__ import annotations

from unittest.mock import MagicMock

from pih.collect.rawitem import RawItem
from pih.store.inbox import (
    STATUS_DEAD,
    STATUS_PENDING,
    InboxRecord,
    InboxRepository,
    SaveOutcome,
)


def _item(sha: str = "sha1-1", source_id: str = "ccma") -> RawItem:
    return RawItem(
        source_id=source_id, url=f"http://x/{sha}", title=f"标题-{sha}",
        list_url="http://x/list", fetched_at="2026-08-26T10:00:00+00:00",
        http_status=200, content_type="text/html", encoding="utf-8",
        raw_html="<html></html>", snapshot_id=sha, content_sha1=sha,
    )


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


class TestSave:
    def test_saved_when_new(self):
        """新内容入库 → SAVED，写 inbox_item 表（非 intel_item）。"""
        m = _MockConn()
        m.cursor_obj.fetchone.return_value = (42,)
        repo = InboxRepository(m.pool)
        outcome = repo.save(_item())
        assert outcome.status == SaveOutcome.SAVED
        assert outcome.inbox_id == 42
        sql = m.cursor_obj.execute.call_args[0][0]
        assert "INSERT INTO inbox_item" in sql
        assert "intel_item" not in sql

    def test_skipped_when_sha1_conflict(self):
        """幂等：content_sha1 冲突（无行返回）→ SKIPPED。"""
        m = _MockConn()
        m.cursor_obj.fetchone.return_value = None  # ON CONFLICT DO NOTHING 无行
        repo = InboxRepository(m.pool)
        outcome = repo.save(_item())
        assert outcome.status == SaveOutcome.SKIPPED

    def test_failed_on_other_exception(self):
        """其他异常 → FAILED，单条不阻塞（容错 D8）。"""
        m = _MockConn()
        m.cursor_obj.execute.side_effect = RuntimeError("boom")
        repo = InboxRepository(m.pool)
        outcome = repo.save(_item())
        assert outcome.status == SaveOutcome.FAILED
        assert "boom" in (outcome.reason or "")


class TestSaveBatch:
    def test_batch_aggregates_outcomes(self):
        """批量：混合 saved/skipped/failed 各计入，单条失败不阻塞。"""
        m = _MockConn()
        repo = InboxRepository(m.pool)
        # save 内部逐条调用 fetchone；用 side_effect 序列控制
        m.cursor_obj.fetchone.side_effect = [(1,), None, RuntimeError("x")]
        outcomes = repo.save_batch([_item("a"), _item("b"), _item("c")])
        statuses = [o.status for o in outcomes]
        assert SaveOutcome.SAVED in statuses
        assert SaveOutcome.SKIPPED in statuses
        assert SaveOutcome.FAILED in statuses


class TestFetchFailureRow:
    def test_record_failure_writes_dead_with_reason(self):
        """AC4：fetch 失败落一行——状态 dead，process_error 记失败原因。"""
        m = _MockConn()
        repo = InboxRepository(m.pool)
        repo.record_failure(
            source_id="ccma",
            url="http://x/failed",
            list_url="http://x/list",
            reason="ConnectionError: timeout",
            fetched_at="2026-08-26T10:00:00+00:00",
        )
        sql, params = m.cursor_obj.execute.call_args[0]
        assert "INSERT INTO inbox_item" in sql
        assert "process_status" in sql
        # 参数含 dead 状态与失败原因
        assert STATUS_DEAD in params
        assert "ConnectionError: timeout" in params


class TestGetAndList:
    def test_get_returns_inbox_record(self):
        """单条详情从 inbox 读（原文快照+原始链接在 inbox 即有，AC1）。"""
        m = _MockConn()
        m.cursor_obj.fetchone.return_value = {
            "id": 7, "source_id": "ccma", "source_type": "auto",
            "url": "http://x/7", "title": "t7", "list_url": "http://x/l",
            "fetched_at": "2026-08-26T10:00:00+00:00", "http_status": 200,
            "content_type": "text/html", "encoding": "utf-8",
            "snapshot_id": "s7", "content_sha1": "s7", "raw_html": "<html/>",
            "process_status": STATUS_PENDING, "process_error": None,
            "process_meta": None, "processed_at": None,
            "created_at": "2026-08-26T10:00:00+00:00",
        }
        repo = InboxRepository(m.pool)
        rec = repo.get(7)
        assert isinstance(rec, InboxRecord)
        assert rec.id == 7
        assert rec.process_status == STATUS_PENDING

    def test_list_pending_orders_old_first(self):
        """list_pending 取 pending 条目，先老后新（处理链消费入口）。"""
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = InboxRepository(m.pool)
        repo.list_pending(source_id="ccma", limit=10)
        sql = m.cursor_obj.execute.call_args[0][0]
        assert "inbox_item" in sql
        assert "process_status" in sql
        assert "ORDER BY" in sql and "fetched_at ASC" in sql
