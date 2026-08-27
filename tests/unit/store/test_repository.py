"""IntelRepository 单元测试——mock pool 验 SQL/分支（Sprint 3 T4）。

mock 策略：cursor.fetchone / fetchall 控制返回；验 execute SQL 与参数。
不依赖真实 DB（集成测试在 T6 test_end_to_end.py）。
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from pih.collect.rawitem import RawItem
from pih.store.repository import IntelRepository, SaveOutcome


def _item(sha: str = "sha1-1", source_id: str = "ccma") -> RawItem:
    return RawItem(
        source_id=source_id, url=f"http://x/{sha}", title=f"标题-{sha}",
        list_url="http://x/list", fetched_at="2026-08-26T10:00:00+00:00",
        http_status=200, content_type="text/html", encoding="utf-8",
        raw_html="<html></html>", snapshot_id=sha, content_sha1=sha,
    )


class _MockConn:
    """建 mock pool 与 cursor，可预设 fetchone/fetchall 返回。"""

    def __init__(self) -> None:
        self.cursor_obj = MagicMock()
        self.cursor_obj.execute = MagicMock()
        self.cursor_obj.fetchone = MagicMock(return_value=None)
        self.cursor_obj.fetchall = MagicMock(return_value=[])
        # row_factory 需支持 with
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
        m = _MockConn()
        m.cursor_obj.fetchone.return_value = (42,)
        repo = IntelRepository(m.pool)
        outcome = repo.save(_item())
        assert outcome.status == SaveOutcome.SAVED
        assert outcome.intel_id == 42
        assert outcome.content_sha1 == "sha1-1"

    def test_skipped_when_conflict(self):
        """ON CONFLICT DO NOTHING → RETURNING 无行 → SKIPPED。"""
        m = _MockConn()
        m.cursor_obj.fetchone.return_value = None
        repo = IntelRepository(m.pool)
        outcome = repo.save(_item())
        assert outcome.status == SaveOutcome.SKIPPED
        assert outcome.intel_id is None

    def test_sql_uses_on_conflict_do_nothing(self):
        """AC4：幂等冲突靠 SQL ON CONFLICT，非应用层 try/except。"""
        m = _MockConn()
        m.cursor_obj.fetchone.return_value = (1,)
        repo = IntelRepository(m.pool)
        repo.save(_item())
        sql = m.cursor_obj.execute.call_args.args[0]
        assert "ON CONFLICT (content_sha1) DO NOTHING" in sql
        assert "RETURNING id" in sql

    def test_params_match_rawitem_fields(self):
        m = _MockConn()
        m.cursor_obj.fetchone.return_value = (1,)
        repo = IntelRepository(m.pool)
        item = _item()
        repo.save(item)
        params = m.cursor_obj.execute.call_args.args[1]
        # INSERT 顺序：source_id, url, title, list_url, fetched_at, http_status,
        #             content_type, encoding, snapshot_id, content_sha1, raw_html
        assert params[0] == item.source_id
        assert params[1] == item.url
        assert params[2] == item.title
        assert params[3] == item.list_url
        assert params[4] == item.fetched_at
        assert params[5] == item.http_status
        assert params[6] == item.content_type
        assert params[7] == item.encoding
        assert params[8] == item.snapshot_id
        assert params[9] == item.content_sha1
        assert params[10] == item.raw_html


class TestSaveBatch:
    def test_batch_continues_on_failure(self):
        """D8 容错：单条失败不阻塞其他条目。"""
        m = _MockConn()
        # 第一条抛异常，第二条成功，第三条冲突
        m.cursor_obj.fetchone.side_effect = [
            RuntimeError("db error"),
            (2,),
            None,
        ]
        repo = IntelRepository(m.pool)
        outcomes = repo.save_batch([_item("a"), _item("b"), _item("c")])
        assert len(outcomes) == 3
        assert outcomes[0].status == SaveOutcome.FAILED
        assert "db error" in outcomes[0].reason
        assert outcomes[1].status == SaveOutcome.SAVED
        assert outcomes[1].intel_id == 2
        assert outcomes[2].status == SaveOutcome.SKIPPED

    def test_batch_empty_returns_empty(self):
        m = _MockConn()
        repo = IntelRepository(m.pool)
        assert repo.save_batch([]) == []


class TestListBySource:
    def test_no_before_clause(self):
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = IntelRepository(m.pool)
        repo.list_by_source("ccma", limit=10)
        sql = m.cursor_obj.execute.call_args.args[0]
        params = m.cursor_obj.execute.call_args.args[1]
        assert "WHERE source_id = %s" in sql
        assert "ORDER BY fetched_at DESC" in sql
        assert "LIMIT %s" in sql
        assert "fetched_at < %s" not in sql
        assert params == ("ccma", 10)

    def test_with_before_cursor(self):
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = IntelRepository(m.pool)
        before = datetime(2026, 8, 25, tzinfo=UTC)
        repo.list_by_source("ccma", limit=5, before=before)
        sql = m.cursor_obj.execute.call_args.args[0]
        params = m.cursor_obj.execute.call_args.args[1]
        assert "fetched_at < %s" in sql
        assert params == ("ccma", before, 5)

    def test_returns_intel_records(self):
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = [
            {
                "id": 1, "source_id": "ccma", "url": "http://x/1",
                "title": "标题", "list_url": "http://x/list",
                "fetched_at": datetime(2026, 8, 26, tzinfo=UTC),
                "http_status": 200, "content_type": "text/html",
                "encoding": "utf-8", "snapshot_id": "sha1", "content_sha1": "sha1",
                "raw_html": "<html></html>", "event_id": None,
                "created_at": datetime(2026, 8, 26, tzinfo=UTC),
            }
        ]
        repo = IntelRepository(m.pool)
        records = repo.list_by_source("ccma", limit=10)
        assert len(records) == 1
        assert records[0].id == 1
        assert records[0].title == "标题"


class TestGet:
    def test_found(self):
        m = _MockConn()
        m.cursor_obj.fetchone.return_value = {
            "id": 7, "source_id": "ccma", "url": "http://x/7",
            "title": "T7", "list_url": "http://x/list",
            "fetched_at": datetime(2026, 8, 26, tzinfo=UTC),
            "http_status": 200, "content_type": "text/html",
            "encoding": "utf-8", "snapshot_id": "sha7", "content_sha1": "sha7",
            "raw_html": "<html></html>", "event_id": None,
            "created_at": datetime(2026, 8, 26, tzinfo=UTC),
        }
        repo = IntelRepository(m.pool)
        rec = repo.get(7)
        assert rec is not None
        assert rec.id == 7
        assert rec.title == "T7"

    def test_not_found_returns_none(self):
        m = _MockConn()
        m.cursor_obj.fetchone.return_value = None
        repo = IntelRepository(m.pool)
        assert repo.get(999) is None
