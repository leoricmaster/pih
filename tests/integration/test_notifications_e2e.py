"""站内信告警端到端测试（TASK-4.02.01）——job 失败→告警→Web 呈现→已读。

需 docker compose up（postgres）。collect 注入 fake（真网络留 live）；
AC1：连续 3 轮失败恰产 1 条未读通知（含信源名与原因）+ 他源不受影响；
AC2：/notifications 渲染 + 标记已读后未读归零。
"""
from __future__ import annotations

import pytest
from conftest import q as _q
from fastapi.testclient import TestClient

from pih.collect.base import SourceConfig
from pih.collect.scheduler import run_source_job
from pih.consume.web import app
from pih.envs import load_env
from pih.store.db import close_pool, get_pool
from pih.store.notification import NotificationRepository
from pih.store.pipeline_run import PipelineRunRepository
from pih.store.source_health import SourceHealthRepository
from pih.store.source_sync import sync_sources

load_env()

pytestmark = pytest.mark.integration


def _src(sid: str, name: str) -> SourceConfig:
    return SourceConfig(
        id=sid, name=name, type="html", url=f"http://{sid}.example/",
        list_url=f"http://{sid}.example/list", reliability="B", level="L2",
        fetch_frequency="daily", enabled=True,
    )


@pytest.fixture
def wired():
    pool = get_pool()
    sources = [_src("bad_src", "坏源示例"), _src("good_src", "好源示例")]
    sync_sources(sources, "construction_machinery", pool)
    notifications = NotificationRepository(pool)
    yield (
        sources,
        SourceHealthRepository(pool),
        PipelineRunRepository(pool),
        notifications,
    )
    close_pool()


def _job_failing(src, health, runs, notifications):
    alerts: list[str] = []

    def notify(title, body):
        alerts.append(title)
        notifications.create(
            type="source_health", source_id=src.id, title=title, body=body
        )

    run_source_job(
        src,
        collect=lambda s, max_items: (_ for _ in ()).throw(
            ConnectionError("模拟 WAF 拦截")
        ),
        health=health, runs=runs, sleep=lambda s: None,
        backoff=(0, 0, 0), notify=notify,
    )
    return alerts


class TestAlertE2E:
    def test_three_failures_one_notification_isolation(self, wired):
        sources, health, runs, notifications = wired
        bad, good = sources
        for _ in range(4):  # 4 轮失败——恰第 3 轮触发，第 4 轮不重复
            _job_failing(bad, health, runs, notifications)
        rows = _q(
            "SELECT title, body FROM notification WHERE type='source_health'"
        )
        assert len(rows) == 1
        assert "坏源示例" in rows[0][0]  # 信源名（AC1）
        assert "连续失败 3 次" in rows[0][0]
        assert "模拟 WAF 拦截" in rows[0][1]  # 失败原因（AC1）
        # 他源不受影响（AC1 后半）：好源正常采集成功
        run_source_job(
            good,
            collect=lambda s, max_items: ([], []),
            health=health, runs=runs, sleep=lambda s: None,
        )
        assert _q(
            "SELECT consecutive_failures FROM source WHERE id='bad_src'"
        ) == [(4,)]
        assert _q(
            "SELECT consecutive_failures FROM source WHERE id='good_src'"
        ) == [(0,)]

    def test_web_render_and_mark_read(self, wired):
        sources, health, runs, notifications = wired
        for _ in range(3):
            _job_failing(sources[0], health, runs, notifications)
        with TestClient(app) as client:
            page = client.get("/notifications")
            assert page.status_code == 200
            assert "坏源示例" in page.text
            assert "未读" in page.text
            nid = _q(
                "SELECT id FROM notification ORDER BY id DESC LIMIT 1"
            )[0][0]
            r = client.post(f"/notifications/{nid}/read", follow_redirects=False)
            assert r.status_code == 303
        assert _q(
            "SELECT count(*) FROM notification WHERE read_at IS NULL"
        ) == [(0,)]
