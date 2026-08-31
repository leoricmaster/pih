"""契约测试：alembic 迁移链可正反向干净跑通（Sprint 3 T1/T2 + Sprint 4 T3）。

需 docker compose up（postgres）。@pytest.mark.integration。
- upgrade head → current 指向最新版本
- downgrade base → current 为空（base）
- 重复 upgrade head 幂等（不报错）
- AC6：intel_item.content_sha1 有 UNIQUE；source_id 有 FK；event_id 有 FK → event（Sprint 6 起）
- AC7：downgrade base 后两张表均消失
- Sprint 4 AC7：0002 加列齐全，process_status 默认 pending，GIN 索引在；
  downgrade 0001 后新列全部消失
- Sprint 5b：0003 feedback 表列/FK 级联/索引；downgrade 0002 后表消失
- Sprint 6：0004 event + verification_log 两表 + intel_item.event_id FK ON DELETE SET NULL；
  downgrade 0003 后两表消失
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psycopg
import pytest

from pih.envs import load_env

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC = ["uv", "run", "alembic"]
# 尊重 .env/.env.defaults 覆盖（load_env 先行）；剥 +psycopg driver 前缀（psycopg.connect 需裸 DSN）
# 分层 env 先行：.env/.env.defaults 的覆盖在此生效（模块级取值在其后）
load_env()
PG_DSN = os.environ.get(
    "PG_DSN", "postgresql://pih:pih@localhost:5432/pih"
).replace("+psycopg", "")


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
    """AC6：UNIQUE content_sha1 + FK source_id + FK event_id → event（Sprint 6 起）。"""
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

    # event_id 字段存在 + FK → event（Sprint 6 加约束）
    cols = _q(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'intel_item' AND column_name = 'event_id'"
    )
    assert cols, "event_id 字段不存在"
    fks = _q(
        "SELECT conname, confrelid::regclass::text, confdeltype FROM pg_constraint "
        "WHERE conrelid = 'intel_item'::regclass AND contype = 'f' "
        "AND conname LIKE '%event_id%'"
    )
    assert any(
        r[0] == "intel_item_event_id_fkey" and r[1] == "event" and r[2] == "n"
        for r in fks
    ), f"event_id FK 应指向 event 且 ON DELETE SET NULL（confdeltype='n'），实际：{fks}"


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


FEEDBACK_COLUMNS = [
    "id", "intel_id", "feedback_type", "fact_index",
    "wrong_value", "correct_value", "note", "user_id", "created_at",
]


def test_sprint5b_feedback_table_columns_exist():
    """0003：feedback 列齐全，user_id 非空默认 operator。"""
    rows = _q(
        "SELECT column_name, column_default, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'feedback'"
    )
    cols = {r[0]: (r[1], r[2]) for r in rows}
    for c in FEEDBACK_COLUMNS:
        assert c in cols, f"缺列 {c}"
    assert "'operator'" in (cols["user_id"][0] or "")
    assert cols["user_id"][1] == "NO"
    assert cols["feedback_type"][1] == "NO"


def test_sprint5b_feedback_fk_cascades_and_indexes():
    """0003：FK → intel_item ON DELETE CASCADE；intel_id/type 两索引在。"""
    rows = _q(
        "SELECT confrelid::regclass::text, confdeltype FROM pg_constraint "
        "WHERE conrelid = 'feedback'::regclass AND contype = 'f'"
    )
    assert any(r[0] == "intel_item" and r[1] == "c" for r in rows), rows

    idx = _q("SELECT indexname FROM pg_indexes WHERE tablename = 'feedback'")
    names = {r[0] for r in idx}
    assert "idx_feedback_intel" in names
    assert "idx_feedback_type" in names


def test_sprint5b_feedback_cascade_actually_deletes():
    """级联真实生效：删情报行，其反馈随之消失。"""
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO source (id, name, domain_id, url, list_url, level, reliability, enabled) "
            "VALUES ('ccma', '测', 'd', 'http://x/', 'http://x/l', 'L2', 'B', true)"
        )
        cur.execute(
            "INSERT INTO intel_item (source_id, url, title, list_url, fetched_at, "
            "http_status, snapshot_id, content_sha1, raw_html) "
            "VALUES ('ccma', 'http://x/1', 't', 'http://x/l', NOW(), 200, 's1', 's1', '<html/>') "
            "RETURNING id"
        )
        intel_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO feedback (intel_id, feedback_type, wrong_value, correct_value) "
            "VALUES (%s, 'subject_wrong', '未知', '三一')", (intel_id,)
        )
        cur.execute("DELETE FROM intel_item WHERE id = %s", (intel_id,))
    rows = _q("SELECT COUNT(*) FROM feedback")
    assert rows == [(0,)]


def test_sprint5b_downgrade_0002_drops_feedback():
    """downgrade 到 0002：feedback 表消失。"""
    _run(["downgrade", "0002"])
    rows = _q(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = 'feedback'"
    )
    assert rows == []
    cur = _run(["current"])
    assert cur.returncode == 0


EVENT_COLUMNS = [
    "id", "subject", "event_type", "status", "source_count",
    "ready_for_manual", "first_seen_at", "last_seen_at",
]

VLOG_COLUMNS = [
    "id", "event_id", "from_status", "to_status", "operator", "reason", "created_at",
]


def test_sprint6_event_table_columns_exist():
    """0004：event 列齐全，status 非空默认 pending，source_count 默认 0（attach 时累加）。"""
    rows = _q(
        "SELECT column_name, column_default, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'event'"
    )
    cols = {r[0]: (r[1], r[2]) for r in rows}
    for c in EVENT_COLUMNS:
        assert c in cols, f"缺列 {c}"
    assert "'pending'" in (cols["status"][0] or "")
    assert cols["status"][1] == "NO"
    assert "0" in (cols["source_count"][0] or "")
    assert cols["source_count"][1] == "NO"
    assert cols["ready_for_manual"][1] == "NO"


def test_sprint6_event_indexes_exist():
    """0004：event 表三索引——status / (subject,event_type) / ready 部分索引。"""
    rows = _q("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'event'")
    defs = {r[0]: r[1] for r in rows}
    assert "idx_event_status" in defs
    assert "idx_event_subject_type" in defs
    assert "idx_event_ready" in defs
    assert "where ready_for_manual" in defs["idx_event_ready"].lower()


def test_sprint6_verification_log_table_and_fk():
    """0004：verification_log 列齐全 + FK → event ON DELETE CASCADE + 索引。"""
    rows = _q(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'verification_log'"
    )
    cols = {r[0] for r in rows}
    for c in VLOG_COLUMNS:
        assert c in cols, f"缺列 {c}"

    fks = _q(
        "SELECT confrelid::regclass::text, confdeltype FROM pg_constraint "
        "WHERE conrelid = 'verification_log'::regclass AND contype = 'f'"
    )
    assert any(r[0] == "event" and r[1] == "c" for r in fks), f"FK 应级联删除：{fks}"

    idx = _q("SELECT indexname FROM pg_indexes WHERE tablename = 'verification_log'")
    assert "idx_vlog_event" in {r[0] for r in idx}


def test_sprint6_intel_item_event_id_index():
    """0004：intel_item.event_id 索引在（按 event 反查情报）。"""
    idx = _q("SELECT indexname FROM pg_indexes WHERE tablename = 'intel_item'")
    assert "idx_intel_item_event_id" in {r[0] for r in idx}


def test_sprint6_event_fk_set_null_on_delete():
    """ON DELETE SET NULL 真实生效：删 event 行，挂在其下的 intel_item.event_id 变 NULL。"""
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO source (id, name, domain_id, url, list_url, level, reliability, enabled) "
            "VALUES ('ccma', '测', 'd', 'http://x/', 'http://x/l', 'L2', 'B', true)"
        )
        cur.execute(
            "INSERT INTO event (subject, event_type, status) "
            "VALUES ('三一', '新品发布', 'pending') RETURNING id"
        )
        event_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO intel_item (source_id, url, title, list_url, fetched_at, "
            "http_status, snapshot_id, content_sha1, raw_html, event_id) "
            "VALUES ('ccma', 'http://x/1', 't', 'http://x/l', NOW(), 200, 's1', 's1', "
            "'<html/>', %s)", (event_id,)
        )
        cur.execute("DELETE FROM event WHERE id = %s", (event_id,))
    rows = _q("SELECT event_id FROM intel_item WHERE content_sha1 = 's1'")
    assert rows == [(None,)], f"删事件后 intel_item.event_id 应为 NULL：{rows}"


def test_sprint6_downgrade_0003_drops_event_tables():
    """downgrade 到 0003：event 与 verification_log 表消失，intel_item.event_id 回到无 FK 占位。"""
    _run(["downgrade", "0003"])
    rows = _q(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name IN ('event', 'verification_log')"
    )
    assert rows == [], f"downgrade 后仍存在表：{rows}"
    # event_id 字段仍在（0001 创建时就是占位列），但 FK 已撤销
    cols = _q(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'intel_item' AND column_name = 'event_id'"
    )
    assert cols, "event_id 占位列应仍在"
    fks = _q(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'intel_item'::regclass AND contype = 'f' "
        "AND conname LIKE '%event_id%'"
    )
    assert not fks, f"FK 应已撤销：{fks}"
    cur = _run(["current"])
    assert cur.returncode == 0

