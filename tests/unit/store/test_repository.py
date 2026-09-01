"""IntelRepository 单元测试——mock pool 验 SQL/分支。

mock 策略：cursor.fetchone / fetchall 控制返回；验 execute SQL 与参数。
不依赖真实 DB（集成测试在 test_end_to_end / test_process_e2e）。
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from pih.collect.rawitem import RawItem
from pih.store.repository import (
    STATUS_EXTRACTED,
    STATUS_NEEDS_MANUAL,
    STATUS_PENDING,
    IntelRepository,
    ProcessResult,
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


class TestListPending:
    def test_sql_filters_pending_orders_asc(self):
        """仅取 pending，fetched_at ASC（先老后新）。"""
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = IntelRepository(m.pool)
        repo.list_pending(limit=10)
        sql = m.cursor_obj.execute.call_args.args[0]
        params = m.cursor_obj.execute.call_args.args[1]
        assert "i.process_status = %s" in sql
        assert "ORDER BY i.fetched_at ASC" in sql
        assert "JOIN source s" in sql
        assert params == (STATUS_PENDING, 10)

    def test_with_source_id_clause(self):
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = IntelRepository(m.pool)
        repo.list_pending(source_id="ccma", limit=5)
        sql = m.cursor_obj.execute.call_args.args[0]
        params = m.cursor_obj.execute.call_args.args[1]
        assert "i.source_id = %s" in sql
        assert params == (STATUS_PENDING, "ccma", 5)

    def test_columns_qualified_for_join(self):
        """JOIN 查询列名须带 i. 前缀（防与 source 表列歧义）。"""
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = IntelRepository(m.pool)
        repo.list_pending()
        sql = m.cursor_obj.execute.call_args.args[0]
        assert " i.id," in sql
        assert " i.source_id," in sql
        assert "s.reliability AS source_reliability" in sql

    def test_returns_reliability(self):
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
                "subject": None, "event_type": None, "facts": None,
                "inferences": None, "tags": None, "quant_params": None,
                "admiralty_code": None, "process_status": STATUS_PENDING,
                "process_error": None, "process_meta": None, "processed_at": None,
                "source_reliability": "B",
            }
        ]
        repo = IntelRepository(m.pool)
        records = repo.list_pending()
        assert records[0].source_reliability == "B"


class TestWriteProcessResult:
    def test_extracted_writes_all_fields(self):
        m = _MockConn()
        repo = IntelRepository(m.pool)
        result = ProcessResult(
            status=STATUS_EXTRACTED,
            subject="三一", event_type="新品发布", facts="销量 1000 台",
            inferences="依据：正文", tags=["电动化"], quant_params={"销量": "1000台"},
            admiralty_code="B2", meta={"api_retries": 1},
        )
        repo.write_process_result(42, result)
        sql = m.cursor_obj.execute.call_args.args[0]
        params = m.cursor_obj.execute.call_args.args[1]
        assert "UPDATE intel_item" in sql
        assert "processed_at = NOW()" in sql
        assert params[0] == "三一"
        assert params[4].obj == ["电动化"]       # tags Json 包装
        assert params[5].obj == {"销量": "1000台"}  # quant_params Json 包装
        assert params[6] == "B2"
        assert params[7] == STATUS_EXTRACTED
        assert params[10] == 42

    def test_needs_manual_writes_schema_defaults_for_not_null_columns(self):
        """未抽取路径：tags/quant_params 列 NOT NULL → 写空集合而非 NULL。"""
        m = _MockConn()
        repo = IntelRepository(m.pool)
        result = ProcessResult(status=STATUS_NEEDS_MANUAL, error="schema 校验 3 次未过")
        repo.write_process_result(7, result)
        params = m.cursor_obj.execute.call_args.args[1]
        assert params[0] is None  # subject（可空列保持 NULL）
        assert params[4].obj == []   # tags → 空数组
        assert params[5].obj == {}   # quant_params → 空对象
        assert params[7] == STATUS_NEEDS_MANUAL
        assert params[8] == "schema 校验 3 次未过"


class TestListByFilter:
    def test_no_filters_no_where(self):
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = IntelRepository(m.pool)
        repo.list_by_filter(limit=10)
        sql = m.cursor_obj.execute.call_args.args[0]
        assert "WHERE" not in sql
        assert m.cursor_obj.execute.call_args.args[1] == (10,)

    def test_combined_filters_build_clauses(self):
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = IntelRepository(m.pool)
        repo.list_by_filter(subject="三一", event_type="新品发布", tag="电动化", limit=5)
        sql = m.cursor_obj.execute.call_args.args[0]
        params = m.cursor_obj.execute.call_args.args[1]
        assert "subject = %s" in sql
        assert "event_type = %s" in sql
        assert "tags @> %s" in sql
        assert params[0] == "三一"
        assert params[1] == "新品发布"
        assert params[2].obj == ["电动化"]  # Json 包装的 containment 数组
        assert params[3] == 5

    def test_admiralty_since_until_before_build_clauses(self):
        """后增参数：admiralty 精确 / since-until fetched_at 闭区间 / before 游标。"""
        from datetime import datetime

        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = IntelRepository(m.pool)
        since = datetime(2026, 5, 1)
        until = datetime(2026, 8, 27)
        before = datetime(2026, 8, 26)
        repo.list_by_filter(
            admiralty="B2",
            source_id="sany_news",
            since=since,
            until=until,
            before=before,
            limit=10,
        )
        sql = m.cursor_obj.execute.call_args.args[0]
        params = m.cursor_obj.execute.call_args.args[1]
        assert "admiralty_code = %s" in sql
        assert "source_id = %s" in sql
        assert "fetched_at >= %s" in sql
        assert "fetched_at <= %s" in sql
        assert "fetched_at < %s" in sql
        assert params[0] == "B2"
        assert params[1] == "sany_news"
        assert params[2] == since
        assert params[3] == until
        assert params[4] == before
        assert params[5] == 10

    def test_orders_admiralty_then_fetched(self):
        """排序简版回退（ranking=None）：admiralty_code ASC NULLS LAST, fetched_at DESC, id DESC。

        事件维度引入后 SQL 列名加 i. 前缀（LEFT JOIN event 防歧义）。
        """
        m = _MockConn()
        m.cursor_obj.fetchall.return_value = []
        repo = IntelRepository(m.pool)
        repo.list_by_filter()
        sql = m.cursor_obj.execute.call_args.args[0]
        assert (
            "ORDER BY i.admiralty_code ASC NULLS LAST, i.fetched_at DESC, i.id DESC"
            in sql
        )
