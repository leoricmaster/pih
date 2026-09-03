"""/inbox 收件箱视图路由测试（ADR-011 两视图，TASK-1.01.02）。

monkeypatch web.IntelRepository 注入 fake，验路由渲染与 list_inbox 调用。
不依赖真实 DB（集成层验端到端）。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import pih.consume.web as web


class _FakeRecord:
    """最小 inbox 行（模板字段）。"""

    def __init__(self, **kw):
        self.id = kw.get("id", 1)
        self.title = kw.get("title", "新采集条目")
        self.source_id = kw.get("source_id", "ccma")
        self.source_type = kw.get("source_type", "auto")
        self.process_status = kw.get("process_status", "pending")
        self.process_error = kw.get("process_error", None)
        self.fetched_at = kw.get("fetched_at", datetime(2026, 9, 3, 8, 0))


class _FakeRepo:
    def __init__(self, pool=None):
        self.calls = []
        self.items: list[_FakeRecord] = []
        self.status_calls: list[tuple] = []

    def list_inbox(self, *, source_id=None, process_status=None, limit=100):
        self.calls.append(
            {"source_id": source_id, "process_status": process_status, "limit": limit}
        )
        return self.items

    def get(self, intel_id):
        return next((r for r in self.items if r.id == intel_id), None)

    def mark_status(self, intel_id, status, error=None):
        self.status_calls.append((intel_id, status))


@pytest.fixture
def fake(monkeypatch):
    f = _FakeRepo()
    monkeypatch.setattr(web, "IntelRepository", lambda pool: f)
    # 路由取 request.app.state.pool 构造 repo（已被 patch 忽略），确保属性存在
    web.app.state.pool = None
    return f


@pytest.fixture
def client(fake):
    return TestClient(web.app)


def test_inbox_renders_pending_items(client, fake):
    """AC1：采集入库的 pending 条目出现在收件箱列表（标题/信源/采集时间）。"""
    fake.items = [_FakeRecord(id=7, title="三一发布新品", source_id="ccma")]
    r = client.get("/inbox")
    assert r.status_code == 200
    assert "三一发布新品" in r.text
    assert "ccma" in r.text
    assert "pending" in r.text


def test_inbox_passes_status_filter(client, fake):
    """process_status 筛选透传 list_inbox（漏报审计筛 filtered_out，AC3）。"""
    client.get("/inbox", params={"process_status": "filtered_out"})
    assert fake.calls[-1]["process_status"] == "filtered_out"


def test_inbox_filtered_out_visible_for_audit(client, fake):
    """AC3：filtered_out 条目在收件箱可见（漏报审计）。"""
    fake.items = [_FakeRecord(id=8, title="无关条目", process_status="filtered_out")]
    r = client.get("/inbox")
    assert "filtered_out" in r.text


def test_inbox_dead_visible_with_reason(client, fake):
    """AC4：dead 失败终态条目在收件箱可见，失败原因可查。"""
    fake.items = [
        _FakeRecord(
            id=9, title="(抓取失败)", process_status="dead",
            process_error="ConnectionError: timeout",
        )
    ]
    r = client.get("/inbox")
    assert "dead" in r.text
    assert "ConnectionError: timeout" in r.text


def test_inbox_empty_shows_hint(client, fake):
    """空收件箱显示提示，不 500。"""
    fake.items = []
    r = client.get("/inbox")
    assert r.status_code == 200
    assert "收件箱为空" in r.text


def test_inbox_tab_bar_present(client, fake):
    """IA 对齐原型 tab 模式：情报页内 [检索]/[收件箱] tab 栏，收件箱页本 tab 高亮。"""
    fake.items = []
    r = client.get("/inbox")
    assert 'class="tab active" href="/inbox"' in r.text
    assert 'class="tab" href="/"' in r.text
    assert "检索" in r.text


def test_inbox_no_source_type_column(client, fake):
    """「来源」列已删——恒 auto（manual 录入未实现）无信息量。"""
    fake.items = [_FakeRecord(id=7)]
    r = client.get("/inbox")
    assert "<th>来源</th>" not in r.text
    assert ">auto<" not in r.text


def test_inbox_replay_button_only_for_non_pending(client, fake):
    """重放按钮只出现在非 pending 行（pending 已在处理链上，无需重放）。"""
    fake.items = [
        _FakeRecord(id=7, process_status="pending"),
        _FakeRecord(id=9, process_status="dead"),
    ]
    r = client.get("/inbox")
    assert "/inbox/9/replay" in r.text
    assert "/inbox/7/replay" not in r.text


def test_inbox_replay_resets_to_pending(client, fake):
    """AC4 重放上 Web：POST /inbox/{id}/replay → mark_status(id, pending)，303 回收件箱。"""
    fake.items = [_FakeRecord(id=9, process_status="dead")]
    r = client.post("/inbox/9/replay", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/inbox"
    assert fake.status_calls == [(9, "pending")]


def test_inbox_replay_unknown_id_404(client, fake):
    """重放不存在的条目 → 404，不误写状态。"""
    fake.items = []
    r = client.post("/inbox/99/replay")
    assert r.status_code == 404
    assert fake.status_calls == []
