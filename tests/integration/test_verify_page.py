"""人工核实页 Web 端到端测试（TASK-2.02.02）。

需 docker compose up（postgres）。验 route→service→repo 跨接线缝：
  - /verify 四区渲染（积压提醒按滞留排序 / ready 队列 / 低置信度 / 待人工）
  - POST confirm → confirmed + verification_log（操作人/原态/新态）
  - POST refute 必填理由 → refuted + 理由入库 + 检索默认隐藏（D7）+ 显式可查
  - 空白理由 400 / 未知事件 404
"""
from __future__ import annotations

from datetime import datetime

import psycopg
import pytest
from _factory import seed_event, seed_intel
from conftest import PG_DSN
from conftest import q as _q
from fastapi.testclient import TestClient

from pih.consume.web import app
from pih.envs import load_env

load_env()

pytestmark = pytest.mark.integration


def _exec(sql: str, params: tuple = ()) -> None:
    """裸写（UPDATE 断言辅助——q 只做 SELECT fetchall）。"""
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, params)


def _attach(intel_id: int, event_id: int) -> None:
    _exec("UPDATE intel_item SET event_id = %s WHERE id = %s", (event_id, intel_id))


class TestVerifyPageSections:
    def test_stale_backlog_rendered_with_retention_days(self):
        seed_event(subject="徐工", event_type="中标落地", status="pending",
                   ready_for_manual=False, days_ago=10)
        seed_event(subject="山推", event_type="财报", status="pending",
                   ready_for_manual=False, days_ago=3)  # 未超期，不进积压区
        with TestClient(app) as client:
            r = client.get("/verify")
        assert r.status_code == 200
        assert "积压提醒" in r.text
        assert "徐工" in r.text and "滞留" in r.text
        assert "山推" not in r.text

    def test_ready_queue_and_needs_manual_rendered(self):
        seed_event(subject="三一", event_type="新品发布")
        iid = seed_intel("ccma", "某主体", "行业统计", datetime.now())
        _exec(
            "UPDATE intel_item SET process_status='needs_manual', "
            "process_error='后验质量门：主体为占位值「未知」' WHERE id=%s",
            (iid,),
        )
        with TestClient(app) as client:
            r = client.get("/verify")
        assert r.status_code == 200
        assert "已具备升级条件" in r.text and "三一" in r.text
        assert "待人工条目" in r.text and "占位值" in r.text


class TestConfirmFlow:
    def test_confirm_writes_terminal_log(self):
        eid = seed_event(subject="柳工", event_type="专利公开")
        with TestClient(app) as client:
            r = client.post(f"/verify/{eid}/confirm", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/verify"
        assert _q("SELECT status FROM event WHERE id=%s", (eid,)) == [("confirmed",)]
        row = _q(
            "SELECT from_status, to_status, operator FROM verification_log "
            "WHERE event_id=%s ORDER BY id DESC LIMIT 1",
            (eid,),
        )
        assert row == [("single_source", "confirmed", "operator")]

    def test_confirm_confirmed_event_conflict(self):
        """终态无出边：confirmed 事件再确认 → 400。"""
        eid = seed_event(subject="中联", event_type="财报", status="confirmed",
                         ready_for_manual=False)
        with TestClient(app) as client:
            r = client.post(f"/verify/{eid}/confirm")
        assert r.status_code == 400


class TestRefuteFlow:
    def test_refute_reason_logged_and_items_hidden_by_default(self):
        eid = seed_event(subject="三一", event_type="新品发布")
        iid = seed_intel("ccma", "三一", "新品发布", datetime.now())
        _attach(iid, eid)
        with TestClient(app) as client:
            r = client.post(
                f"/verify/{eid}/refute",
                data={"reason": "主体误读，系旧闻重发"},
                follow_redirects=False,
            )
            assert r.status_code == 303
            # D7：默认检索隐藏
            home = client.get("/").text
            assert "测试情报" not in home
            # 显式可查（审计可达）
            explicit = client.get("/", params={"event_status": "refuted"}).text
            assert "测试情报" in explicit
        assert _q("SELECT status FROM event WHERE id=%s", (eid,)) == [("refuted",)]
        row = _q(
            "SELECT to_status, operator, reason FROM verification_log "
            "WHERE event_id=%s ORDER BY id DESC LIMIT 1",
            (eid,),
        )
        assert row == [("refuted", "operator", "主体误读，系旧闻重发")]

    def test_blank_reason_400(self):
        eid = seed_event(subject="徐工", event_type="财报")
        with TestClient(app) as client:
            r = client.post(f"/verify/{eid}/refute", data={"reason": "  "})
        assert r.status_code == 400
        assert _q("SELECT status FROM event WHERE id=%s", (eid,)) == [("single_source",)]

    def test_unknown_event_404(self):
        with TestClient(app) as client:
            assert client.post("/verify/9999/confirm").status_code == 404
            assert client.post(
                "/verify/9999/refute", data={"reason": "x"}
            ).status_code == 404
