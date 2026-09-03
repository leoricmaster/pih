"""source 健康统计与 pipeline_run 留痕仓储单测（TASK-4.01.01 D9/D16）。

_MockConn 捕获 SQL 与参数（与 test_repository 同款），真库往返在 integration。
"""
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


class TestSourceHealthRepository:
    def test_record_success_resets_counter(self):
        from pih.store.source_health import SourceHealthRepository

        m = _MockConn()
        SourceHealthRepository(m.pool).record_success("ccma")
        sql = m.cursor_obj.execute.call_args.args[0]
        assert "consecutive_failures = 0" in sql
        assert "last_success_at = now()" in sql
        assert m.cursor_obj.execute.call_args.args[1] == ("ccma",)

    def test_record_failure_increments(self):
        from pih.store.source_health import SourceHealthRepository

        m = _MockConn()
        SourceHealthRepository(m.pool).record_failure("ccma", "ConnectError: x")
        sql = m.cursor_obj.execute.call_args.args[0]
        assert "consecutive_failures = consecutive_failures + 1" in sql
        assert "last_failure_reason = %s" in sql
        # 占位符顺序：reason 在前（SET），id 在后（WHERE）
        assert m.cursor_obj.execute.call_args.args[1] == ("ConnectError: x", "ccma")

    def test_get_health_reads_row(self):
        from pih.store.source_health import SourceHealthRepository

        m = _MockConn()
        m.cursor_obj.fetchone.return_value = {
            "source_id": "ccma",
            "consecutive_failures": 3,
            "last_failure_at": None,
            "last_failure_reason": "x",
            "last_success_at": None,
        }
        h = SourceHealthRepository(m.pool).get_health("ccma")
        assert h is not None and h["consecutive_failures"] == 3


class TestPipelineRunRepository:
    def test_record_run_inserts_row(self):
        from pih.store.pipeline_run import PipelineRunRepository

        m = _MockConn()
        PipelineRunRepository(m.pool).record_run(
            source_id="ccma", run_type="startup", duration_ms=1234, ok=True,
            items_new=3, items_skipped=1, items_failed=0,
        )
        sql = m.cursor_obj.execute.call_args.args[0]
        assert "INSERT INTO pipeline_run" in sql
        params = m.cursor_obj.execute.call_args.args[1]
        assert params[0] == "ccma" and params[1] == "startup"
        assert params[2] == 1234 and params[3] is True
        assert params[4:7] == (3, 1, 0)

    def test_record_run_failed_with_error(self):
        from pih.store.pipeline_run import PipelineRunRepository

        m = _MockConn()
        PipelineRunRepository(m.pool).record_run(
            source_id="ccma", run_type="scheduled", duration_ms=99, ok=False,
            items_new=0, items_skipped=0, items_failed=0,
            error="ConnectError: timeout",
        )
        params = m.cursor_obj.execute.call_args.args[1]
        assert params[3] is False
        assert params[-1] == "ConnectError: timeout"
