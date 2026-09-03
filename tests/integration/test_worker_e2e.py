"""worker 采集 job 端到端测试（TASK-4.01.01）——编排缝→真库往返。

需 docker compose up（postgres）。collect 注入 fake（真网络采集留 live）；
验 source 健康列回写与 pipeline_run 留痕行落库（跨接线缝：单测 mock 掩盖）。
"""
from __future__ import annotations

import psycopg
import pytest
from conftest import PG_DSN
from conftest import q as _q

from pih.collect.base import SourceConfig
from pih.collect.scheduler import run_source_job
from pih.envs import load_env
from pih.store.db import close_pool, get_pool
from pih.store.pipeline_run import PipelineRunRepository
from pih.store.source_health import SourceHealthRepository
from pih.store.source_sync import sync_sources


def _exec(sql: str, params: tuple = ()) -> None:
    """裸写（q 只做 SELECT fetchall）。"""
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, params)

load_env()

pytestmark = pytest.mark.integration


def _src() -> SourceConfig:
    return SourceConfig(
        id="ccma", name="中国工程机械工业协会", type="html", url="http://www.cncma.org/",
        list_url="http://www.cncma.org/col/hangyxw", reliability="B", level="L2",
        fetch_frequency="daily", enabled=True,
    )


class _Raw:
    snapshot_id = "sha-x"
    title = "t"


class _Outcome:
    def __init__(self, status: str) -> None:
        self.status = status


@pytest.fixture
def repos():
    pool = get_pool()
    sync_sources([_src()], "construction_machinery", pool)
    yield SourceHealthRepository(pool), PipelineRunRepository(pool)
    close_pool()


class TestWorkerJobE2E:
    def test_success_path_writes_health_and_run(self, repos):
        health, runs = repos

        def fake_collect(source, max_items):
            return ([_Raw()], [_Outcome("saved"), _Outcome("skipped")])

        res = run_source_job(
            _src(), collect=fake_collect, health=health, runs=runs,
            sleep=lambda s: None, run_type="startup",
        )
        assert res.ok and res.items_new == 1
        row = _q(
            "SELECT consecutive_failures, last_success_at IS NOT NULL "
            "FROM source WHERE id='ccma'"
        )
        assert row == [(0, True)]
        run = _q(
            "SELECT run_type, ok, items_new, items_skipped FROM pipeline_run "
            "WHERE source_id='ccma' ORDER BY id DESC LIMIT 1"
        )
        assert run == [("startup", True, 1, 1)]

    def test_failure_path_increments_health(self, repos):
        health, runs = repos

        def dead_collect(source, max_items):
            raise ConnectionError("模拟断网")

        res = run_source_job(
            _src(), collect=dead_collect, health=health, runs=runs,
            sleep=lambda s: None, backoff=(0, 0, 0),  # 测试不真等
        )
        assert not res.ok and res.attempts == 4
        row = _q(
            "SELECT consecutive_failures, last_failure_reason FROM source "
            "WHERE id='ccma'"
        )
        assert row[0][0] >= 1
        assert "模拟断网" in row[0][1]
        run = _q(
            "SELECT ok, error FROM pipeline_run WHERE source_id='ccma' "
            "ORDER BY id DESC LIMIT 1"
        )
        assert run[0][0] is False
        assert "模拟断网" in run[0][1]

    def test_success_resets_prior_failures(self, repos):
        health, runs = repos
        _exec("UPDATE source SET consecutive_failures=2 WHERE id='ccma'")

        def fake_collect(source, max_items):
            return ([], [])

        run_source_job(
            _src(), collect=fake_collect, health=health, runs=runs,
            sleep=lambda s: None,
        )
        row = _q("SELECT consecutive_failures FROM source WHERE id='ccma'")
        assert row == [(0,)]
