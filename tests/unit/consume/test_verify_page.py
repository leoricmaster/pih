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


def _it(id=1, title="低置信条目", admiralty="C5", fetched=None, error=None,
        status="extracted", source_id="ccma"):
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
    i.process_status = status
    i.source_id = source_id
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
        self.by_status: dict[str, list] = {}
        self.replayed: list[tuple] = []

    def list_low_confidence(self, limit=50):
        return self.low_conf

    def list_inbox(self, *, source_id=None, process_status=None, limit=100):
        return self.by_status.get(process_status, [])

    def list_by_event(self, event_id, limit=20):
        return []

    def get(self, intel_id):
        for rows in self.by_status.values():
            if any(r.id == intel_id for r in rows):
                return next(r for r in rows if r.id == intel_id)
        return None

    def mark_status(self, intel_id, status, error=None):
        self.replayed.append((intel_id, status))


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
        ir.by_status["needs_manual"] = [
            _it(id=22, admiralty="B4", error="后验质量门：主体为占位值「未知」")
        ]
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


class TestWorkbenchInbox:
    """Web 验收轮 R2：收件箱并入核实页工作台（原 TASK-1.01.02 AC 语义不变）。

    - pending 滞留入积压区（AC1 验收面）
    - filtered_out/dead 折叠审计区（AC3 漏报审计 / AC4 失败原因）
    - 重放动作归位 /verify/{id}/replay（AC4 重放上 Web）
    """

    def test_pending_items_in_stale_zone(self, fakes):
        _, ir = fakes
        ir.by_status["pending"] = [
            _it(id=31, title="新采集条目", status="pending", source_id="ccma")
        ]
        with TestClient(web.app) as client:
            html = client.get("/verify").text
        assert "待处理条目" in html
        assert "新采集条目" in html and "ccma" in html

    def test_no_pending_shows_hint(self, fakes):
        with TestClient(web.app) as client:
            html = client.get("/verify").text
        assert "无待处理条目" in html

    def test_audit_zone_filtered_out_and_dead(self, fakes):
        _, ir = fakes
        ir.by_status["filtered_out"] = [
            _it(id=32, title="无关政策文", status="filtered_out")
        ]
        ir.by_status["dead"] = [
            _it(id=33, title="(抓取失败)", status="dead",
                error="ConnectionError: timeout")
        ]
        with TestClient(web.app) as client:
            html = client.get("/verify").text
        assert "审计" in html
        assert "无关政策文" in html
        assert "(抓取失败)" in html and "timeout" in html

    def test_replay_button_on_needs_manual_rows(self, fakes):
        _, ir = fakes
        ir.by_status["needs_manual"] = [_it(id=22, status="needs_manual")]
        ir.by_status["pending"] = [_it(id=31, status="pending")]
        with TestClient(web.app) as client:
            html = client.get("/verify").text
        assert 'action="/verify/22/replay"' in html
        assert 'action="/verify/31/replay"' not in html  # pending 已在链上不放

    def test_replay_resets_to_pending(self, fakes):
        _, ir = fakes
        ir.by_status["needs_manual"] = [_it(id=22, status="needs_manual")]
        with TestClient(web.app) as client:
            r = client.post("/verify/22/replay", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/verify#manual"
        assert ir.replayed == [(22, "pending")]

    def test_replay_unknown_id_404(self, fakes):
        _, ir = fakes
        with TestClient(web.app) as client:
            r = client.post("/verify/99/replay")
        assert r.status_code == 404
        assert ir.replayed == []

    def test_inbox_url_redirects_to_verify(self, fakes):
        with TestClient(web.app) as client:
            r = client.get("/inbox", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/verify"
