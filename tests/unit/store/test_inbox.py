"""IntelRepository 采集入库相关单元测试（ADR-011 单表两视图，TASK-1.01.02）。

采集落 intel_item(pending) + source_type；record_failure 落死信行；
list_inbox 收件箱视图读非 extracted；mark_status 写回处理状态。
mock 策略同 test_repository：cursor.fetchone/fetchall 控制返回。
"""
from __future__ import annotations

from unittest.mock import MagicMock

from pih.collect.rawitem import RawItem
from pih.store.repository import (
    STATUS_DEAD,
    STATUS_EXTRACTED,
    STATUS_FILTERED_OUT,
    STATUS_PENDING,
    IntelRepository,
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


class TestSaveSourceType:
    def test_save_writes_source_type_auto(self):
        """采集入库写 intel_item，source_type=auto（ADR-011 物理载体）。"""
        m = _MockConn()
        m.cursor_obj.fetchone.return_value = (42,)
        repo = IntelRepository(m.pool)
        outcome = repo.save(_item())
        assert outcome.status == SaveOutcome.SAVED
        params = m.cursor_obj.execute.call_args[0][1]
        assert params[1] == "auto"  # source_type 位

    def test_save_manual_source_type(self):
        """人工录入 source_type=manual（ADR-009 汇聚，TASK-1.03 预留）。"""
        m = _MockConn()
        m.cursor_obj.fetchone.return_value = (42,)
        repo = IntelRepository(m.pool)
        repo.save(_item(), source_type="manual")
        params = m.cursor_obj.execute.call_args[0][1]
        assert params[1] == "manual"


class TestRecordFailure:
    def test_failure_writes_dead_with_reason(self):
        """AC4：fetch 失败落一行——状态 dead，process_error 记失败原因。"""
        m = _MockConn()
        repo = IntelRepository(m.pool)
        repo.record_failure(
            source_id="ccma", url="http://x/failed", list_url="http://x/list",
            reason="ConnectionError: timeout", fetched_at="2026-08-26T10:00:00+00:00",
        )
        sql, params = m.cursor_obj.execute.call_args[0]
        assert "INSERT INTO intel_item" in sql
        assert STATUS_DEAD in params
        assert "ConnectionError: timeout" in params
        assert "auto" in params  # source_type 默认


class TestListInbox:
    def test_inbox_excludes_extracted(self):
        """收件箱视图读非 extracted（pending/needs_manual/filtered_out/dead）。"""
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = IntelRepository(m.pool)
        repo.list_inbox()
        sql, params = m.cursor_obj.execute.call_args[0]
        assert "process_status != %s" in sql
        assert STATUS_EXTRACTED in params

    def test_inbox_filter_single_status(self):
        """process_status 给定筛单态（漏报审计筛 filtered_out，AC3）。"""
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = IntelRepository(m.pool)
        repo.list_inbox(process_status=STATUS_FILTERED_OUT)
        sql, params = m.cursor_obj.execute.call_args[0]
        assert "process_status = %s" in sql
        assert STATUS_FILTERED_OUT in params

    def test_inbox_source_id_filter(self):
        """source_id 透传限定信源。"""
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = IntelRepository(m.pool)
        repo.list_inbox(source_id="ccma", limit=10)
        sql, params = m.cursor_obj.execute.call_args[0]
        assert "source_id = %s" in sql
        assert "ccma" in params


class TestMarkStatus:
    def test_mark_filtered_out(self):
        """粗筛判不相关 → mark_status(filtered_out)（AC3 行级标记）。"""
        m = _MockConn()
        repo = IntelRepository(m.pool)
        repo.mark_status(7, STATUS_FILTERED_OUT, error="粗筛不相关")
        sql, params = m.cursor_obj.execute.call_args[0]
        assert "UPDATE intel_item" in sql
        assert STATUS_FILTERED_OUT in params
        assert 7 in params

    def test_mark_replay_resets_pending(self):
        """AC4 可重放：mark_status(id, pending) 重入处理链。"""
        m = _MockConn()
        repo = IntelRepository(m.pool)
        repo.mark_status(7, STATUS_PENDING)
        params = m.cursor_obj.execute.call_args[0][1]
        assert STATUS_PENDING in params
