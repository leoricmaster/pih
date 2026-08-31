"""消费层端到端集成测试（Sprint 5a，ADR-006 同源）。

覆盖 S1.1.1 AC1/AC2 + S1.1.2 AC1 + S1.1.4 AC1/AC2/AC3 共 6 条。
AC3「已过期标识」不交付（expires_at 未上线）。

需 docker compose up postgres。@pytest.mark.integration 自动打标。
"""
from __future__ import annotations

import re

import psycopg
import pytest
from _factory import PG_DSN, seed_intel_items
from starlette.testclient import TestClient

from pih.consume.web import app
from pih.envs import load_env

load_env()

pytestmark = pytest.mark.integration


@pytest.fixture
def api_token(monkeypatch):
    monkeypatch.setenv("PIH_API_TOKEN", "test-token")
    return "test-token"


def _seed(n: int = 60) -> list[int]:
    with psycopg.connect(PG_DSN) as conn:
        return seed_intel_items(conn, n)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestAC1ListFilters:
    """S1.1.1 AC1：多条件组合筛选 + 列表列展示 + 事件核实状态占位。"""

    def test_filter_subject_event_since_and_columns(self, api_token):
        _seed(60)
        with TestClient(app) as client:
            r = client.get("/", params={
                "subject": "三一",
                "event_type": "新品发布",
                "since": "2026-05-30T00:00:00",
            })
            assert r.status_code == 200
            html = r.text
            # 列表表头列齐全
            for col in ("标题", "主体", "事件类型", "置信度", "采集时间", "所属事件核实状态"):
                assert col in html
            # Sprint 6 事件占位激活：未挂事件行显示 —，挂事件显示中文标签；
            # seed 数据未挂事件，应见 —
            assert "—" in html
            # 筛选结果只含三一+新品发布（factory 循环：60 条里 12 条三一，其中 ~2 条新品发布）
            # 至少有 1 条命中
            assert "/intel/" in html


class TestAC2EmptyResult:
    """S1.1.1 AC2：空结果提示 + 不渲染下一页。"""

    def test_empty_shows_hint_and_no_next_page(self, api_token):
        _seed(60)
        with TestClient(app) as client:
            r = client.get("/", params={"subject": "不存在的主体"})
            assert r.status_code == 200
            html = r.text
            assert "无结果，建议放宽条件" in html
            assert "下一页" not in html


class TestAC3DetailPage:
    """S1.1.2 AC1：详情页 schema 全字段 + 事实/推断分区 + 双入口 + 事件占位。"""

    def test_detail_shows_all_sections(self, api_token):
        ids = _seed(60)
        target_id = ids[0]
        with TestClient(app) as client:
            r = client.get(f"/intel/{target_id}")
            assert r.status_code == 200
            html = r.text
            # 分区齐全
            for section in ("基础元信息", "结构化字段", "事实描述", "推断与判断",
                            "原文与快照", "处理状态", "事件核实状态与跃迁历史"):
                assert section in html
            # 事实/推断内容
            assert "事实描述 #" in html
            assert "推断与判断 #" in html
            # 原文 URL + 快照入口（MinIO 起着→presigned URL；否则降级 ID 文本）
            assert f"http://sany_news.example/item-{0}" in html
            assert "原文快照" in html
            # Sprint 6 事件占位激活：seed 数据未挂事件，详情页显示「未挂事件」提示
            assert "未挂事件" in html

    def test_detail_404_for_missing(self, api_token):
        with TestClient(app) as client:
            r = client.get("/intel/99999")
            assert r.status_code == 404


class TestAC4SameSource:
    """S1.1.4 AC1：Web 与 API 同参数返回同 id 集合与排序。"""

    def test_web_and_api_return_same_ids(self, api_token):
        _seed(60)
        with TestClient(app) as client:
            params = {"event_type": "新品发布", "limit": 10}
            web_r = client.get("/", params=params)
            api_r = client.get("/api/intel/list", params=params, headers=_auth(api_token))

            assert web_r.status_code == 200
            assert api_r.status_code == 200

            # 从 Web HTML 提取标题链接的 /intel/{id} 序列（反馈列 href 带 #feedback 锚点，不匹配）
            web_ids = re.findall(r'href="/intel/(\d+)"', web_r.text)
            # API JSON 提取 id 序列
            api_ids = [str(item["id"]) for item in api_r.json()["items"]]

            assert web_ids == api_ids, f"Web 与 API id 序列不一致：{web_ids} vs {api_ids}"


class TestSprint5bProcessStatusFilter:
    """Sprint 5b：process_status 筛选（needs_manual 复核队列可达）+ Web/API 同源。"""

    def test_status_filter_same_source_web_and_api(self, api_token):
        ids = _seed(20)
        # 前 5 条改 needs_manual（后验质量门拦下的形态）
        with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE intel_item SET process_status='needs_manual', "
                "process_error='后验质量门：主体为占位值「未知」' "
                "WHERE id = ANY(%s)", ([ids[0], ids[1], ids[2], ids[3], ids[4]],)
            )
        with TestClient(app) as client:
            params = {"process_status": "needs_manual"}
            web_r = client.get("/", params=params)
            api_r = client.get("/api/intel/list", params=params, headers=_auth(api_token))
            assert web_r.status_code == 200
            assert api_r.status_code == 200

            web_ids = re.findall(r'href="/intel/(\d+)"', web_r.text)
            api_ids = [str(item["id"]) for item in api_r.json()["items"]]
            assert sorted(web_ids) == sorted(str(i) for i in ids[:5])
            assert web_ids == api_ids
            for item in api_r.json()["items"]:
                assert item["process_status"] == "needs_manual"

    def test_status_column_in_list(self, api_token):
        _seed(5)
        with TestClient(app) as client:
            html = client.get("/").text
        assert "status-needs_manual" in html or "status-extracted" in html
        assert 'name="process_status"' in html  # 筛选下拉在场


class TestAC5ApiResponseFields:
    """S1.1.4 AC2：组合查询响应字段齐全。"""

    def test_list_response_fields(self, api_token):
        _seed(60)
        with TestClient(app) as client:
            r = client.get("/api/intel/list", params={
                "subject": "三一", "event_type": "新品发布",
                "since": "2026-05-30T00:00:00", "limit": 5,
            }, headers=_auth(api_token))
            assert r.status_code == 200
            body = r.json()
            assert body["count"] >= 1
            item = body["items"][0]
            # 必含字段
            for key in ("id", "facts", "inferences", "admiralty_code", "references"):
                assert key in item, f"缺字段 {key}"
            # 来源引用
            assert "url" in item["references"]
            assert "snapshot_id" in item["references"]
            assert "snapshot_url" in item["references"]
            # Sprint 6 事件占位激活：seed 数据未挂事件，API 返回 None + "未挂事件"
            assert item["event_verification_status"] is None
            assert item["event_verification_note"] == "未挂事件"

    def test_detail_response_fields(self, api_token):
        ids = _seed(60)
        with TestClient(app) as client:
            r = client.get(f"/api/intel/{ids[0]}", headers=_auth(api_token))
            assert r.status_code == 200
            item = r.json()
            for key in ("id", "title", "subject", "event_type", "facts",
                        "inferences", "admiralty_code", "references",
                        "event_verification_status", "event_verification_note"):
                assert key in item

    def test_next_before_cursor_in_response(self, api_token):
        _seed(60)
        with TestClient(app) as client:
            r = client.get("/api/intel/list", params={"limit": 10},
                           headers=_auth(api_token))
            body = r.json()
            assert body["count"] == 10
            assert body["next_before"] is not None


class TestAC6Auth:
    """S1.1.4 AC3：鉴权——缺失/错误 token → 401；env 未配 → 503。"""

    def test_missing_header_returns_401(self, api_token):
        with TestClient(app) as client:
            r = client.get("/api/intel/list")
            assert r.status_code == 401
            assert "items" not in r.json()

    def test_wrong_token_returns_401(self, api_token):
        with TestClient(app) as client:
            r = client.get("/api/intel/list",
                           headers=_auth("wrong-token"))
            assert r.status_code == 401

    def test_env_missing_returns_503(self, monkeypatch):
        monkeypatch.delenv("PIH_API_TOKEN", raising=False)
        with TestClient(app) as client:
            r = client.get("/api/intel/list", headers=_auth("any"))
            assert r.status_code == 503

    def test_valid_token_passes(self, api_token):
        _seed(3)
        with TestClient(app) as client:
            r = client.get("/api/intel/list", headers=_auth(api_token))
            assert r.status_code == 200


class TestHealthz:
    """健康检查不鉴权，返回 PG 连通性。"""

    def test_healthz_no_auth_needed(self):
        with TestClient(app) as client:
            r = client.get("/api/healthz")
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "ok"
            assert body["pg"] is True
