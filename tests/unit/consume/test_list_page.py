"""/ 检索视图路由参数测试（TASK-2.01.01 D2：time_range 预设映射）。

monkeypatch web.IntelRepository 注入 fake，验 since 映射与显式直参优先。
不依赖真实 DB（集成层验端到端）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import pih.consume.web as web


class _FakeRepo:
    def __init__(self, pool=None):
        self.calls: list[dict] = []

    def list_by_filter(self, **kw):
        self.calls.append(kw)
        return []


@pytest.fixture
def fake(monkeypatch):
    f = _FakeRepo()
    monkeypatch.setattr(web, "IntelRepository", lambda pool: f)
    web.app.state.pool = None
    return f


class TestTimeRangePreset:
    def test_time_range_maps_to_since(self, fake):
        with TestClient(web.app) as client:
            r = client.get("/", params={"time_range": "30d"})
        assert r.status_code == 200
        kw = fake.calls[-1]
        assert kw["since"] is not None
        delta = datetime.now() - kw["since"]
        assert timedelta(days=29, hours=12) < delta < timedelta(days=30, minutes=10)

    def test_explicit_since_wins_over_preset(self, fake):
        explicit = datetime(2026, 1, 1, 8, 0)
        with TestClient(web.app) as client:
            r = client.get(
                "/",
                params={"time_range": "30d", "since": explicit.isoformat()},
            )
        assert r.status_code == 200
        assert fake.calls[-1]["since"] == explicit

    def test_unknown_preset_ignored(self, fake):
        with TestClient(web.app) as client:
            r = client.get("/", params={"time_range": "999d"})
        assert r.status_code == 200
        assert fake.calls[-1]["since"] is None


class TestAdmiraltyTierPassThrough:
    def test_admiralty_single_char_forwarded(self, fake):
        """>= 档参数原样透传（语义在 repository SQL，D1）。"""
        with TestClient(web.app) as client:
            r = client.get("/", params={"admiralty": "B"})
        assert r.status_code == 200
        assert fake.calls[-1]["admiralty"] == "B"
