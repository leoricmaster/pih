"""Alembic 迁移环境（Sprint 3 store 层）。

DSN 解析优先级（高 → 低）：
  1. 命令行 -x sqlalchemy.url=...
  2. 环境变量 PG_DSN（python-dotenv 从 cwd .env 加载）
  3. alembic.ini [alembic] sqlalchemy.url（占位，不应被命中）

仅用 alembic 跑 DDL，不用 ORM/autogenerate——target_metadata 保持 None，
迁移手写（schema 跟着已实现能力走，不预置字段）。
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_dsn = os.environ.get("PG_DSN")
if _dsn:
    config.set_main_option("sqlalchemy.url", _dsn)

target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
