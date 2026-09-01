"""db.py 单元测试——DSN 处理逻辑。

不建真实连接池（避免依赖 DB），只验 _ensure_psycopg_driver 与缺 DSN 抛错。
"""
from __future__ import annotations

import pytest

from pih.store.db import _ensure_psycopg_driver, close_pool, get_pool


class TestEnsureDriver:
    def test_strips_plus_psycopg(self):
        assert _ensure_psycopg_driver("postgresql+psycopg://u:p@h/db") == "postgresql://u:p@h/db"

    def test_keeps_plain_postgresql(self):
        assert _ensure_psycopg_driver("postgresql://u:p@h/db") == "postgresql://u:p@h/db"

    def test_idempotent(self):
        dsn = "postgresql+psycopg://u:p@h/db"
        assert _ensure_psycopg_driver(_ensure_psycopg_driver(dsn)) == "postgresql://u:p@h/db"


class TestGetPoolMissingDsn:
    def test_raises_when_dsn_unset(self, monkeypatch):
        monkeypatch.delenv("PG_DSN", raising=False)
        # 重置模块级单例
        import pih.store.db as dbmod
        dbmod._pool = None
        with pytest.raises(RuntimeError, match="PG_DSN"):
            get_pool()

    def test_close_pool_is_noop_when_none(self):
        # 确保不抛异常（初始态）
        import pih.store.db as dbmod
        dbmod._pool = None
        close_pool()  # 不抛即通过
