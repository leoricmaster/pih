"""integration 层公共样板（2026-08-31 去重收敛）。

原先 8 个测试文件逐字重复的三件套上移至此：
- PG_DSN：分层 env 加载 + 剥 +psycopg driver 前缀（psycopg.connect 需裸 DSN）
- _clean_db：每个测试前置 downgrade base + upgrade head，保证干净库
- _q：裸 psycopg 直查（断言用，绕过 store 层）

fixtures 以 autouse 生效，测试文件无需再手写。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psycopg
import pytest

from pih.envs import load_env

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC = ["uv", "run", "alembic"]

# 分层 env 先行：.env/.env.defaults 的覆盖在此生效（模块级取值在其后）
load_env()
PG_DSN = os.environ.get(
    "PG_DSN", "postgresql://pih:pih@localhost:5432/pih"
).replace("+psycopg", "")


@pytest.fixture(autouse=True)
def _clean_db():
    """每个测试前置 downgrade base + upgrade head，保证干净库。"""
    subprocess.run(ALEMBIC + ["downgrade", "base"], cwd=REPO_ROOT, check=True, capture_output=True)
    subprocess.run(ALEMBIC + ["upgrade", "head"], cwd=REPO_ROOT, check=True, capture_output=True)
    yield


def q(sql: str, params: tuple = ()) -> list[tuple]:
    """裸 psycopg 直查（断言用）。"""
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()
