"""source_sync 单元测试——mock pool 验 SQL 与参数。

不依赖真实 DB；用 MagicMock 包装 cursor，捕获 execute 调用。
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from pih.collect.base import SourceConfig
from pih.store.source_sync import SyncStats, sync_sources


def _src(id_: str, enabled: bool = True) -> SourceConfig:
    return SourceConfig(
        id=id_, name=f"源-{id_}", type="html", url=f"http://{id_}.example/",
        list_url=f"http://{id_}.example/list", reliability="B", level="L2",
        fetch_frequency="daily", enabled=enabled,
    )


def _mock_pool():
    """建 mock pool，返回 (pool, cursor, calls)。calls 是 execute 调用列表。"""
    cursor = MagicMock()
    cursor.execute = MagicMock(side_effect=lambda sql, params: None)
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = False
    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = conn
    pool.connection.return_value.__exit__.return_value = False
    return pool, cursor


class TestSyncSources:
    def test_empty_sources_returns_zero(self):
        pool, _ = _mock_pool()
        stats = sync_sources([], "dom", pool)
        assert stats == SyncStats(upserted=0)

    def test_upserts_each_source_with_correct_params(self):
        pool, cursor = _mock_pool()
        sources = [_src("a"), _src("b"), _src("c", enabled=False)]
        stats = sync_sources(sources, "construction_machinery", pool)

        assert stats.upserted == 3
        assert cursor.execute.call_count == 3

        # 验第一条调用：SQL 含 ON CONFLICT DO UPDATE
        first_call = cursor.execute.call_args_list[0]
        sql, params = first_call.args
        assert "ON CONFLICT (id) DO UPDATE" in sql
        assert params[0] == "a"           # id
        assert params[1] == "源-a"         # name
        assert params[2] == "construction_machinery"  # domain_id
        assert params[5] == "L2"           # level
        assert params[6] == "B"            # reliability
        assert params[7] == "daily"        # fetch_frequency
        assert params[8] is True           # enabled
        assert isinstance(params[9], datetime)  # synced_at

        # 第三条 enabled=False
        third_params = cursor.execute.call_args_list[2].args[1]
        assert third_params[8] is False

    def test_sql_is_idempotent_upsert(self):
        """重复调用同 sources 不冲突（ON CONFLICT DO UPDATE）。"""
        pool, cursor = _mock_pool()
        sync_sources([_src("a")], "dom", pool)
        sync_sources([_src("a")], "dom", pool)
        assert cursor.execute.call_count == 2  # 两次各 1 条
