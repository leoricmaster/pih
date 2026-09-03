"""/notifications 站内信页路由测试（TASK-4.02.01）。

monkeypatch web.NotificationRepository 注入 fake，验未读/历史渲染与标记已读。
不依赖真实 DB（集成层验端到端）。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import pih.consume.web as web


class _FakeNotificationRepo:
    def __init__(self, pool=None):
        self.rows: list[dict] = []
        self.read_ids: list[int] = []

    def unread_count(self):
        return sum(1 for r in self.rows if r["read_at"] is None)

    def list_unread(self, limit=50):
        return [r for r in self.rows if r["read_at"] is None][:limit]

    def list_recent(self, limit=50):
        return self.rows[:limit]

    def mark_read(self, nid):
        self.read_ids.append(nid)


@pytest.fixture
def fake(monkeypatch):
    f = _FakeNotificationRepo()
    monkeypatch.setattr(web, "NotificationRepository", lambda pool: f)
    web.app.state.pool = None
    return f


def _n(id=1, title="信源异常：路面机械网 连续失败 3 次", read=False):
    return {
        "id": id, "type": "source_health", "source_id": "lmjx",
        "title": title, "body": "ConnectError: WAF 拦截",
        "read_at": datetime(2026, 9, 3, 10, 0) if read else None,
        "created_at": datetime(2026, 9, 3, 9, 0),
    }


class TestNotificationsPage:
    def test_unread_and_history_render(self, fake):
        fake.rows = [_n(id=1), _n(id=2, read=True)]
        with TestClient(web.app) as client:
            r = client.get("/notifications")
        assert r.status_code == 200
        assert "路面机械网" in r.text  # 未读组标题（含信源名 AC1）
        assert "WAF 拦截" in r.text  # 失败原因（AC1）
        assert "标记已读" in r.text
        assert "已读" in r.text  # 历史组

    def test_mark_read_redirects(self, fake):
        fake.rows = [_n(id=5)]
        with TestClient(web.app) as client:
            r = client.post("/notifications/5/read", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/notifications"
        assert fake.read_ids == [5]

    def test_bell_injected_on_other_pages(self, fake):
        """顶栏铃铛：每页注入未读数与最近未读（_render 收口 D19）。"""
        fake.rows = [_n(id=9)]
        with TestClient(web.app) as client:
            # /sources 需要 pack + health；用 /notifications 之外的轻页面——
            # 根路径需 repo，打桩 IntelRepository 返回空列表
            class _EmptyRepo:
                def __init__(self, pool=None):
                    pass

                def list_by_filter(self, **kw):
                    return []

            import unittest.mock as mc

            with mc.patch.object(web, "IntelRepository", _EmptyRepo):
                html = client.get("/").text
        assert "🔔" in html
        assert 'class="dot">1</span>' in html  # 未读角标
        assert "路面机械网" in html  # 下拉最近未读
