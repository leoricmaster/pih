"""契约测试：alembic 迁移可正反向干净跑通（单基线 0001 全量 schema）。

需 docker compose up（postgres）。@pytest.mark.integration。
- upgrade head → current 指向最新版本
- downgrade base → current 为空（base）
- 重复 upgrade head 幂等（不报错）
- AC6：intel_item.content_sha1 有 UNIQUE；source_id 有 FK；event_id 有 FK → event
- AC7：downgrade base 后全部表消失
- intel_item 结构化/治理列齐全，process_status 默认 pending，三索引在
- feedback 表列/FK 级联/索引
- event + verification_log 两表 + intel_item.event_id FK ON DELETE SET NULL
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
    """AC6：UNIQUE content_sha1 + FK source_id + FK event_id → event。"""
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

    # event_id 字段存在 + FK → event
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
    """AC7：downgrade base 后全部 5 表消失（迁移整体可逆）。"""
    _run(["downgrade", "base"])
    rows = _q(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name IN "
        "('source', 'intel_item', 'event', 'verification_log', 'feedback')"
    )
    assert rows == [], f"downgrade 后仍存在表：{rows}"


PROCESS_COLUMNS = [
    "subject", "event_type", "facts", "inferences", "tags", "quant_params",
    "admiralty_code", "process_status", "process_error", "process_meta",
    "processed_at",
]


def test_process_columns_exist():
    """结构化与治理列齐全，process_status 非空默认 pending。"""
    rows = _q(
        "SELECT column_name, column_default, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'intel_item'"
    )
    cols = {r[0]: (r[1], r[2]) for r in rows}
    for c in PROCESS_COLUMNS:
        assert c in cols, f"缺列 {c}"
    assert "'pending'" in (cols["process_status"][0] or "")
    assert cols["process_status"][1] == "NO"


def test_process_indexes_exist():
    """process_status / event_type B-tree + tags GIN 三索引。"""
    rows = _q(
        "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'intel_item'"
    )
    defs = {r[0]: r[1] for r in rows}
    assert "idx_intel_item_process_status" in defs
    assert "idx_intel_item_event_type" in defs
    assert "idx_intel_item_tags" in defs
    assert "using gin" in defs["idx_intel_item_tags"].lower()


def test_existing_rows_get_pending_default():
    """存量行入库即 pending 默认值（process_status 默认 pending）。"""
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


FEEDBACK_COLUMNS = [
    "id", "intel_id", "feedback_type", "fact_index",
    "wrong_value", "correct_value", "note", "user_id", "created_at",
]


def test_feedback_table_columns_exist():
    """feedback 列齐全，user_id 非空默认 operator。"""
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


def test_feedback_fk_cascades_and_indexes():
    """FK → intel_item ON DELETE CASCADE；intel_id/type 两索引在。"""
    rows = _q(
        "SELECT confrelid::regclass::text, confdeltype FROM pg_constraint "
        "WHERE conrelid = 'feedback'::regclass AND contype = 'f'"
    )
    assert any(r[0] == "intel_item" and r[1] == "c" for r in rows), rows

    idx = _q("SELECT indexname FROM pg_indexes WHERE tablename = 'feedback'")
    names = {r[0] for r in idx}
    assert "idx_feedback_intel" in names
    assert "idx_feedback_type" in names


def test_feedback_cascade_actually_deletes():
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


EVENT_COLUMNS = [
    "id", "subject", "event_type", "status", "source_count",
    "ready_for_manual", "first_seen_at", "last_seen_at",
]

VLOG_COLUMNS = [
    "id", "event_id", "from_status", "to_status", "operator", "reason", "created_at",
]


def test_event_table_columns_exist():
    """event 列齐全，status 非空默认 pending，source_count 默认 0（attach 时累加）。"""
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


def test_event_indexes_exist():
    """event 表三索引——status / (subject,event_type) / ready 部分索引。"""
    rows = _q("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'event'")
    defs = {r[0]: r[1] for r in rows}
    assert "idx_event_status" in defs
    assert "idx_event_subject_type" in defs
    assert "idx_event_ready" in defs
    assert "where ready_for_manual" in defs["idx_event_ready"].lower()


def test_verification_log_table_and_fk():
    """verification_log 列齐全 + FK → event ON DELETE CASCADE + 索引。"""
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


def test_source_health_columns_exist():
    """TASK-4.01.01 D9：source 健康统计列（连续失败计数/最近成败时间与原因）。"""
    rows = {
        r[0]: (r[1], r[2])
        for r in _q(
            "SELECT column_name, column_default, is_nullable "
            "FROM information_schema.columns WHERE table_name = 'source'"
        )
    }
    assert "consecutive_failures" in rows, "consecutive_failures 列不存在"
    assert (rows["consecutive_failures"][0] or "").strip("'") == "0"
    assert rows["consecutive_failures"][1] == "NO"
    for col in ("last_failure_at", "last_failure_reason", "last_success_at"):
        assert col in rows, f"{col} 列不存在"
        assert rows[col][1] == "YES"


def test_pipeline_run_table_exists_with_columns():
    """TASK-4.01.01 D16：pipeline_run 每次调度运行留痕（吞吐/失败/时长/token 预留）。"""
    rows = {
        r[0]
        for r in _q(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'pipeline_run'"
        )
    }
    expected = {
        "id", "source_id", "run_type", "started_at", "duration_ms", "ok",
        "items_new", "items_skipped", "items_failed", "error",
        "prompt_tokens", "completion_tokens", "created_at",
    }
    missing = expected - rows
    assert not missing, f"pipeline_run 缺列：{missing}"
    idx = _q("SELECT indexname FROM pg_indexes WHERE tablename = 'pipeline_run'")
    assert "idx_pipeline_run_source_time" in {r[0] for r in idx}


def test_source_health_downgrade_reversible():
    """downgrade 0002：健康列与 pipeline_run 表可逆移除（source 既有列不动）。"""
    _run(["downgrade", "0002"])
    rows = _q(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'source' AND column_name = 'consecutive_failures'"
    )
    assert rows == [], "downgrade 后 consecutive_failures 应消失"
    tables = _q(
        "SELECT tablename FROM pg_tables WHERE tablename = 'pipeline_run'"
    )
    assert tables == [], "downgrade 后 pipeline_run 表应消失"
    keep = _q(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'source' AND column_name = 'reliability'"
    )
    assert keep, "source.reliability 应仍在"


def test_notification_table_exists():
    """TASK-4.02.01：站内信表（未读/已读，type 枚举开放）。"""
    rows = {
        r[0]
        for r in _q(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'notification'"
        )
    }
    expected = {"id", "type", "source_id", "title", "body", "read_at", "created_at"}
    assert expected <= rows, f"notification 缺列：{expected - rows}"
    # read_at NULL=未读
    nullable = {
        r[0]: r[1]
        for r in _q(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'notification'"
        )
    }
    assert nullable["read_at"] == "YES"
    assert nullable["title"] == "NO"
    idx = _q("SELECT indexname FROM pg_indexes WHERE tablename = 'notification'")
    assert "idx_notification_unread" in {r[0] for r in idx}


def test_notification_downgrade_reversible():
    """downgrade 0003：notification 表可逆移除（source 健康列仍在）。"""
    _run(["downgrade", "0003"])
    tables = _q("SELECT tablename FROM pg_tables WHERE tablename = 'notification'")
    assert tables == []
    keep = _q(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'source' AND column_name = 'consecutive_failures'"
    )
    assert keep


def test_intel_item_source_type_column():
    """ADR-011：intel_item 加 source_type 列（inbox 逻辑汇聚的物理载体）。"""
    rows = _q(
        "SELECT column_default, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'intel_item' AND column_name = 'source_type'"
    )
    assert rows, "source_type 列不存在"
    assert "'auto'" in (rows[0][0] or "")
    assert rows[0][1] == "NO"


def test_intel_item_source_type_index():
    """source_type 索引在（按来源类型区分采集/人工）。"""
    idx = _q("SELECT indexname FROM pg_indexes WHERE tablename = 'intel_item'")
    assert "idx_intel_item_source_type" in {r[0] for r in idx}


def test_source_type_downgrade_drops_column():
    """downgrade 0001：source_type 列可逆移除（回滚不伤既有 intel 数据）。"""
    _run(["downgrade", "0001"])
    rows = _q(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'intel_item' AND column_name = 'source_type'"
    )
    assert rows == [], f"downgrade 0001 后 source_type 应消失：{rows}"
    # intel_item 仍在且结构化列未伤
    keep = _q(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'intel_item' AND column_name = 'subject'"
    )
    assert keep, "intel_item.subject 应仍在"


def test_intel_item_event_id_index():
    """intel_item.event_id 索引在（按 event 反查情报）。"""
    idx = _q("SELECT indexname FROM pg_indexes WHERE tablename = 'intel_item'")
    assert "idx_intel_item_event_id" in {r[0] for r in idx}


def test_event_fk_set_null_on_delete():
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

