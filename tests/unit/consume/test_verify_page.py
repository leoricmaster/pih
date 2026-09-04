"""/verify 核实页路由测试（TASK-2.02.02）。

monkeypatch web.IntelRepository / web.EventRepository 注入 fake，
验四区渲染、低置信排序（score 升序）、confirm/refute 操作语义。
不依赖真实 DB（集成层验端到端）。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import pih.consume.web as web


def _ev(id=1, subject="三一", event_type="新品发布", days_ago=0):
    class E:
        pass

    e = E()
    e.id = id
    e.subject = subject
    e.event_type = event_type
    e.status = "single_source"
    e.source_count = 2
    e.ready_for_manual = True
    t = datetime.now() - _d(days_ago)
    e.first_seen_at = t
    e.last_seen_at = t
    return e


def _d(days: int):
    from datetime import timedelta

    return timedelta(days=days)


def _it(id=1, title="低置信条目", admiralty="C5", fetched=None, error=None):
    class Item:
        pass

    i = Item()
    i.id = id
    i.title = title
    i.admiralty_code = admiralty
    i.subject = "某主体"
    i.event_type = "行业统计"
    i.fetched_at = fetched or datetime(2026, 9, 1, 8, 0)
    i.process_error = error
    i.process_status = "extracted"
    return i


class _FakeEventRepo:
    def __init__(self, pool=None):
        self.events: list = []
        self.stale: list = []
        self.confirmed: list = []
        self.refuted: list = []

    def list_ready_for_manual(self, limit=50):
        return self.events

    def list_stale_pending(self, days=7, limit=50):
        return self.stale

    def get_event(self, event_id):
        return next((e for e in self.events if e.id == event_id), None)

    def list_verification_log(self, event_id):
        return []

    def confirm(self, event_id, operator="operator"):
        self.confirmed.append((event_id, operator))
        return True

    def refute(self, event_id, reason, operator="operator"):
        self.refuted.append((event_id, reason, operator))
        return True


class _FakeIntelRepo:
    def __init__(self, pool=None):
        self.low_conf: list = []
        self.inbox: list = []

    def list_low_confidence(self, limit=50):
        return self.low_conf

    def list_inbox(self, *, source_id=None, process_status=None, limit=100):
        return self.inbox if process_status == "needs_manual" else []


@pytest.fixture
def fakes(monkeypatch):
    er, ir = _FakeEventRepo(), _FakeIntelRepo()
    monkeypatch.setattr(web, "IntelRepository", lambda pool: ir)
    monkeypatch.setattr(web, "EventRepository", lambda pool: er)
    web.app.state.pool = None
    return er, ir


class TestVerifyPageRender:
    def test_four_sections_render(self, fakes):
        er, ir = fakes
        er.events = [_ev(id=7, subject="三一")]
        er.stale = [_ev(id=8, subject="徐工", days_ago=10)]
        # stale 经路由折算为 {event, days} 卡片
        ir.low_conf = [_it(id=21, admiralty="C5")]
        ir.inbox = [_it(id=22, admiralty="B4", error="后验质量门：主体为占位值「未知」")]
        with TestClient(web.app) as client:
            r = client.get("/verify")
        assert r.status_code == 200
        html = r.text
        for section in ("积压提醒", "已具备升级条件", "低置信度情报", "待人工条目"):
            assert section in html
        assert "三一" in html and "徐工" in html
        # 滞留天数可见（AC4 按滞留时长呈现）
        assert "10" in html
        # 待人工条目带失败原因
        assert "占位值" in html

    def test_low_confidence_sorted_worst_first(self, fakes):
        er, ir = fakes
        ir.low_conf = [
            _it(id=1, title="较好档 B4", admiralty="B4"),
            _it(id=2, title="最差档 E5", admiralty="E5"),
        ]
        with TestClient(web.app) as client:
            html = client.get("/verify").text
        assert html.index("最差档 E5") < html.index("较好档 B4")

    def test_empty_queues_show_hints(self, fakes):
        with TestClient(web.app) as client:
            html = client.get("/verify").text
        assert "无积压" in html


class TestVerifyActions:
    def test_confirm_redirects_and_logs_operator(self, fakes):
        er, _ = fakes
        er.events = [_ev(id=5)]
        with TestClient(web.app) as client:
            r = client.post("/verify/5/confirm", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/verify"
        assert er.confirmed == [(5, "operator")]

    def test_refute_with_reason_redirects(self, fakes):
        er, _ = fakes
        er.events = [_ev(id=5)]
        with TestClient(web.app) as client:
            r = client.post(
                "/verify/5/refute", data={"reason": "主体误读"}, follow_redirects=False
            )
        assert r.status_code == 303
        assert er.refuted == [(5, "主体误读", "operator")]

    def test_refute_blank_reason_rejected(self, fakes):
        er, _ = fakes
        er.events = [_ev(id=5)]
        with TestClient(web.app) as client:
            r = client.post("/verify/5/refute", data={"reason": "   "})
        assert r.status_code == 400
        assert er.refuted == []

    def test_unknown_event_404(self, fakes):
        with TestClient(web.app) as client:
            r1 = client.post("/verify/99/confirm")
            r2 = client.post("/verify/99/refute", data={"reason": "x"})
        assert r1.status_code == 404
        assert r2.status_code == 404
