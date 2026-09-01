"""PG 连接池（store 层）。

psycopg3 + psycopg_pool，最小 pool（1–3）。DSN 从环境变量 PG_DSN 读取
（python-dotenv 在 cli.py 入口已 load_dotenv）。

CLI 单次运行场景：close_pool 在 finally 显式调用，避免连接泄漏。
调度器（Backlog TASK-4.01.01，待实现）落地后再调优 pool 大小。
"""
from __future__ import annotations

import os

from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """取/建进程级单例连接池。多次调用返回同一实例。"""
    global _pool
    if _pool is not None:
        return _pool
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise RuntimeError(
            "PG_DSN 未设置（请在 .env 中配置，参考 .env.example）"
        )
    _pool = ConnectionPool(
        conninfo=_ensure_psycopg_driver(dsn),
        min_size=1,
        max_size=3,
        open=True,
    )
    return _pool


def _ensure_psycopg_driver(dsn: str) -> str:
    """若 DSN 写成 postgresql://... 而 sqlalchemy/alembic 需要 +psycopg，
    这里 store 层用裸 psycopg，无需 driver 后缀；剥掉 +psycopg 兼容 .env 模板。"""
    return dsn.replace("postgresql+psycopg://", "postgresql://")


def close_pool() -> None:
    """显式关闭池（CLI 退出时调用）。"""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
