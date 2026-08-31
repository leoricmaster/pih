"""端到端集成测试：collect → 落库 → query（Sprint 3 T6，AC1–AC5）。

需 docker compose up（postgres + minio）+ 外网。@pytest.mark.integration。

验收路径：
  AC1  collect ccma → 落库 + source 表同步 + stdout 统计
  AC2  二次 collect ccma → 幂等跳过（content_sha1 UNIQUE）
  AC3  query --source-id=ccma → 列表含 title/url/snapshot_id/fetched_at
  AC4  幂等冲突靠 SQL ON CONFLICT（已由单元测试验 SQL，这里验端到端行为）
  AC5  sync_sources → source 表含 ccma/sany/cehome，enabled 与 YAML 一致

密闭性：每个测试前置 alembic downgrade base + upgrade head，保证干净库。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psycopg
import pytest

from pih.cli import main
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


@pytest.fixture(autouse=True)
def _clean_db():
    """每个测试前置 downgrade base + upgrade head，保证干净库。"""
    subprocess.run(ALEMBIC + ["downgrade", "base"], cwd=REPO_ROOT, check=True, capture_output=True)
    subprocess.run(ALEMBIC + ["upgrade", "head"], cwd=REPO_ROOT, check=True, capture_output=True)
    yield


def _q(sql: str, params: tuple = ()) -> list[tuple]:
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def test_ac1_collect_ingests_and_syncs_source(capsys):
    """AC1：collect ccma → RawItem 落库 + source 表含 ccma 行。"""
    code = main(["collect", "ccma", "--max-items", "2"])
    out = capsys.readouterr().out
    assert code == 0, f"采集失败：\n{out}"
    assert "入库" in out
    assert "新增" in out

    # source 表已同步
    rows = _q("SELECT id, enabled, level FROM source WHERE id = 'ccma'")
    assert rows == [("ccma", True, "L2")]

    # intel_item 有行
    rows = _q("SELECT COUNT(*) FROM intel_item WHERE source_id = 'ccma'")
    assert rows[0][0] >= 1


def test_ac2_second_collect_skips_duplicates(capsys):
    """AC2：二次 collect 同源 → 幂等跳过，intel_item 行数不变。"""
    main(["collect", "ccma", "--max-items", "2"])
    rows_before = _q("SELECT COUNT(*) FROM intel_item WHERE source_id = 'ccma'")[0][0]

    code = main(["collect", "ccma", "--max-items", "2"])
    out = capsys.readouterr().out
    assert code == 0
    assert "幂等跳过" in out
    assert "新增" in out  # 统计行含新增字段
    # 提取新增数应为 0
    # （不断言精确文本，因 max_items 与列表条数交互可能导致首次未抓全）

    rows_after = _q("SELECT COUNT(*) FROM intel_item WHERE source_id = 'ccma'")[0][0]
    assert rows_after == rows_before, f"二次 collect 后行数变了：{rows_before} → {rows_after}"


def test_ac3_query_lists_intel(capsys):
    """AC3：query --source-id=ccma → 列表含 title/url/snapshot_id/fetched_at。"""
    main(["collect", "ccma", "--max-items", "1"])

    code = main(["query", "--source-id=ccma", "--limit=10"])
    out = capsys.readouterr().out
    assert code == 0
    assert "查询：source_id=ccma" in out
    assert "共" in out
    # 列表行格式（Sprint 4 起）：[id] 时间 [process_status/event_type/admiralty] 标题
    lines = [line for line in out.splitlines() if line.startswith("  [")]
    assert len(lines) >= 1
    # 时间格式 YYYY-MM-DD HH:MM 在行中
    assert "2026-" in lines[0]
    # process_status 标记在行中（pending 或 extracted 等）
    assert "[" in lines[0] and "]" in lines[0]


def test_ac3b_query_by_id_shows_detail(capsys):
    """query --id=N → 单条详情字段完整。"""
    main(["collect", "ccma", "--max-items", "1"])
    ids = _q("SELECT id FROM intel_item WHERE source_id = 'ccma' ORDER BY id LIMIT 1")
    assert ids, "库中无 ccma 情报"
    intel_id = ids[0][0]

    code = main(["query", "--id", str(intel_id)])
    out = capsys.readouterr().out
    assert code == 0
    assert f"情报 #{intel_id}" in out
    for field in ["标题", "信源", "URL", "快照 ID", "内容指纹", "入库时间"]:
        assert field in out


def test_ac5_sync_sources_inserts_all_enabled(capsys):
    """AC5：collect 触发 sync_sources → source 表含 ccma/sany/cehome 三行。"""
    main(["collect", "ccma", "--max-items", "1"])
    rows = _q(
        "SELECT id, enabled FROM source "
        "WHERE id IN ('ccma', 'sany', 'cehome') ORDER BY id"
    )
    assert rows == [("ccma", True), ("cehome", True), ("sany", True)]


def test_ac5b_disabled_sources_synced_as_false(capsys):
    """AC5b：xcmg 等未启用源也同步进 source 表，enabled=false。"""
    main(["collect", "ccma", "--max-items", "1"])
    rows = _q("SELECT enabled FROM source WHERE id = 'xcmg'")
    assert rows == [(False,)]
