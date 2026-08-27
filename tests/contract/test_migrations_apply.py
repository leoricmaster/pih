"""契约测试：alembic 迁移链可正反向干净跑通（Sprint 3 T1/T2 + Sprint 4 T3）。

需 docker compose up（postgres）。@pytest.mark.integration。
- upgrade head → current 指向最新版本
- downgrade base → current 为空（base）
- 重复 upgrade head 幂等（不报错）
- AC6：intel_item.content_sha1 有 UNIQUE；source_id 有 FK；event_id 字段存在但无 FK
- AC7：downgrade base 后两张表均消失
- Sprint 4 AC7：0002 加列齐全，process_status 默认 pending，GIN 索引在；
  downgrade 0001 后新列全部消失
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import psycopg
import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC = ["uv", "run", "alembic"]
PG_DSN = "postgresql://pih:pih@localhost:5432/pih"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ALEMBIC + args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _q(sql: str) -> list[tuple]:
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


@pytest.fixture(autouse=True)
def _clean_db():
    """每个测试前置 downgrade base + upgrade head，保证干净库。"""
    _run(["downgrade", "base"])
    _run(["upgrade", "head"])
    yield
    _run(["downgrade", "base"])


def test_upgrade_head_then_downgrade_base():
    """upgrade head 与 downgrade base 都干净退出（exit 0）。"""
    up = _run(["upgrade", "head"])
    assert up.returncode == 0, f"upgrade head 失败：\n{up.stderr}"

    cur_after_up = _run(["current"])
    assert cur_after_up.returncode == 0

    down = _run(["downgrade", "base"])
    assert down.returncode == 0, f"downgrade base 失败：\n{down.stderr}"


def test_upgrade_is_idempotent():
    """连续 upgrade head 不报错（已最新时静默退出 0）。"""
    _run(["upgrade", "head"])
    again = _run(["upgrade", "head"])
    assert again.returncode == 0, f"重复 upgrade head 失败：\n{again.stderr}"


def test_ac6_intel_item_constraints():
    """AC6：UNIQUE content_sha1 + FK source_id + event_id 占位无 FK。"""
    # UNIQUE 约束存在
    rows = _q(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'intel_item'::regclass AND contype = 'u'"
    )
    assert any(r[0] == "intel_item_content_sha1_key" for r in rows), rows

    # FK source_id → source
    rows = _q(
        "SELECT conname, confrelid::regclass::text FROM pg_constraint "
        "WHERE conrelid = 'intel_item'::regclass AND contype = 'f'"
    )
    assert any(r[0] == "intel_item_source_id_fkey" and r[1] == "source" for r in rows), rows

    # event_id 字段存在但无 FK
    cols = _q(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'intel_item' AND column_name = 'event_id'"
    )
    assert cols, "event_id 字段不存在"
    fks = _q(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'intel_item'::regclass AND contype = 'f' "
        "AND conname LIKE '%event_id%'"
    )
    assert not fks, f"event_id 不应有 FK，但存在：{fks}"


def test_ac7_downgrade_base_drops_tables():
    """AC7：downgrade base 后 source 与 intel_item 表均消失。"""
    _run(["downgrade", "base"])
    rows = _q(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name IN ('source', 'intel_item')"
    )
    assert rows == [], f"downgrade 后仍存在表：{rows}"


PROCESS_COLUMNS = [
    "subject", "event_type", "facts", "inferences", "tags", "quant_params",
    "admiralty_code", "process_status", "process_error", "process_meta",
    "processed_at",
]


def test_sprint4_ac7_process_columns_exist():
    """0002：结构化与治理列齐全，process_status 非空默认 pending。"""
    rows = _q(
        "SELECT column_name, column_default, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'intel_item'"
    )
    cols = {r[0]: (r[1], r[2]) for r in rows}
    for c in PROCESS_COLUMNS:
        assert c in cols, f"缺列 {c}"
    assert "'pending'" in (cols["process_status"][0] or "")
    assert cols["process_status"][1] == "NO"


def test_sprint4_process_indexes_exist():
    """0002：process_status / event_type B-tree + tags GIN 三索引。"""
    rows = _q(
        "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'intel_item'"
    )
    defs = {r[0]: r[1] for r in rows}
    assert "idx_intel_item_process_status" in defs
    assert "idx_intel_item_event_type" in defs
    assert "idx_intel_item_tags" in defs
    assert "using gin" in defs["idx_intel_item_tags"].lower()


def test_sprint4_existing_rows_get_pending_default():
    """存量行（0001 时代入库）upgrade 0002 后自动 pending，可被 pih process 处理。"""
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO source (id, name, domain_id, url, list_url, level, reliability, enabled) "
            "VALUES ('ccma', '测', 'd', 'http://x/', 'http://x/l', 'L2', 'B', true)"
        )
        cur.execute(
            "INSERT INTO intel_item (source_id, url, title, list_url, fetched_at, "
            "http_status, snapshot_id, content_sha1, raw_html) "
            "VALUES ('ccma', 'http://x/1', '旧标题', 'http://x/l', NOW(), 200, "
            "'sha-old-1', 'sha-old-1', '<html></html>')"
        )
    rows = _q("SELECT process_status FROM intel_item WHERE content_sha1 = 'sha-old-1'")
    assert rows == [("pending",)]


def test_sprint4_downgrade_0001_drops_process_columns():
    """downgrade 到 0001：新列全部消失（迁移可逆，逐级不依赖表删除）。"""
    _run(["downgrade", "0001"])
    rows = _q(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'intel_item'"
    )
    cols = {r[0] for r in rows}
    assert not (cols & set(PROCESS_COLUMNS)), f"downgrade 后仍存在列：{cols & set(PROCESS_COLUMNS)}"

