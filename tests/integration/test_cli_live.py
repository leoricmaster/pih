"""集成测试：CLI 端到端真跑（运营者视角验收 TASK-1.01.01 AC2）。

需 `docker compose up`（MinIO + postgres）+ 外网访问。@pytest.mark.integration。
- probe-source ccma：真实试抓取，退出码 0，报告含快照 ID
- collect xcmg：enabled 门控拒绝（未启用源），退出码 1
- collect ccma：门控通过，真实采集 + 落库，退出码 0
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pih.cli import main

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC = ["uv", "run", "alembic"]


@pytest.fixture(autouse=True)
def _clean_db():
    """collect 默认落库，需前置建表。每个测试重置干净库。"""
    subprocess.run(ALEMBIC + ["downgrade", "base"], cwd=REPO_ROOT, check=True, capture_output=True)
    subprocess.run(ALEMBIC + ["upgrade", "head"], cwd=REPO_ROOT, check=True, capture_output=True)
    yield


def test_probe_source_live(capsys):
    """AC1 用户闭环：运营者命令行触发试抓取并得到成败报告。"""
    code = main(["probe-source", "ccma", "--details", "1"])
    out = capsys.readouterr().out
    assert code == 0, f"试抓取未通过：\n{out}"
    assert "试抓取：ccma" in out
    assert "快照" in out
    assert "试抓取通过" in out


def test_collect_gate_rejects_disabled_source(capsys):
    """门控：未启用源（xcmg，enabled: false）被拒绝并给出指引。"""
    code = main(["collect", "xcmg"])
    err = capsys.readouterr().err
    assert code == 1
    assert "门控拒绝" in err
    assert "pih probe-source xcmg" in err


def test_collect_live(capsys):
    """门控通过 + 真实采集 + 落库：产出 RawItem 摘要与入库统计。"""
    code = main(["collect", "ccma", "--max-items", "1"])
    out = capsys.readouterr().out
    assert code == 0, f"采集失败：\n{out}"
    assert "RawItem" in out
    assert "入库" in out
