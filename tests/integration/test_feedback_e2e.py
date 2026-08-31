"""反馈闭环端到端集成测试（Sprint 5b S3.1.3 最小切片）。

覆盖 S3.1.3 AC1-AC4：表单提交落库（主体/事实/不该入库）、
详情页已记录提示、聚合视图计数与高亮、JSONL 导出、非法入参 422/404。

需 docker compose up postgres。@pytest.mark.integration 自动打标。
"""
from __future__ import annotations

import json

import psycopg
import pytest
from _factory import PG_DSN, seed_intel_items
from starlette.testclient import TestClient

from pih.consume.web import app
from pih.envs import load_env

load_env()

pytestmark = pytest.mark.integration


def _seed(n: int = 10) -> list[int]:
    with psycopg.connect(PG_DSN) as conn:
        return seed_intel_items(conn, n)


def _feedback_rows() -> list[tuple]:
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT intel_id, feedback_type, fact_index, wrong_value, "
            "correct_value, note, user_id FROM feedback ORDER BY id"
        )
        return cur.fetchall()


class TestSubjectFeedback:
    """AC1：主体错了 → feedback 表落 wrong/correct 值 + 回详情页提示。"""

    def test_form_post_writes_row_and_redirects(self):
        ids = _seed(1)
        with TestClient(app) as client:
            r = client.post(
                "/feedback",
                data={
                    "intel_id": ids[0],
                    "feedback_type": "subject_wrong",
                    "wrong_value": "未知",
                    "correct_value": "三一",
                    "user_id": "reviewer",
                },
                follow_redirects=False,
            )
            assert r.status_code == 303
            assert r.headers["location"] == f"/intel/{ids[0]}?fb=1"
            # 重定向回详情页显示已记录
            page = client.get(f"/intel/{ids[0]}", params={"fb": 1})
            assert "反馈已记录" in page.text

        rows = _feedback_rows()
        assert rows == [(ids[0], "subject_wrong", None, "未知", "三一", None, "reviewer")]

    def test_detail_page_has_feedback_forms(self):
        ids = _seed(1)
        with TestClient(app) as client:
            html = client.get(f"/intel/{ids[0]}").text
        assert 'id="feedback"' in html
        for label in ("主体错了", "事件类型错", "事实不准", "不该入库"):
            assert label in html
        # hidden 透传当前主体作 wrong_value
        assert 'name="wrong_value" value="三一"' in html


class TestFactFeedback:
    """AC2：事实不准 → fact_index 标注到事实项级别。"""

    def test_fact_index_recorded(self):
        ids = _seed(1)
        with TestClient(app) as client:
            r = client.post(
                "/feedback",
                data={
                    "intel_id": ids[0],
                    "feedback_type": "fact_wrong",
                    "fact_index": 2,
                    "note": "销量数字与原文不符",
                },
            )
            assert r.status_code == 200  # follow_redirects 默认跟随到详情页
        rows = _feedback_rows()
        assert rows[0][0] == ids[0]
        assert rows[0][1] == "fact_wrong"
        assert rows[0][2] == 2
        assert rows[0][5] == "销量数字与原文不符"


class TestShouldFilterFeedback:
    """AC3：不该入库 → type=should_filter，聚合视图按信源计数。"""

    def test_should_filter_aggregated_on_view(self):
        ids = _seed(5)
        with TestClient(app) as client:
            for i in ids[:2]:
                client.post(
                    "/feedback",
                    data={"intel_id": i, "feedback_type": "should_filter",
                          "note": "时政类新闻"},
                )
            html = client.get("/feedback").text
        assert "sany_news" in html
        assert "不该入库" in html
        assert "时政类新闻" in html  # 明细行说明


class TestAggregationView:
    """AC4：主体错误率 >30% 高亮 + JSONL 导出。"""

    def test_highlight_over_30_percent(self):
        ids = _seed(10)  # 10 条 extracted
        # 直插 4 条 subject_wrong（40% > 30% 阈值）——聚合态造数走 SQL 更直接
        with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
            for i in ids[:4]:
                cur.execute(
                    "INSERT INTO feedback (intel_id, feedback_type, wrong_value, correct_value) "
                    "VALUES (%s, 'subject_wrong', '未知', '三一')",
                    (i,),
                )
        with TestClient(app) as client:
            html = client.get("/feedback").text
        assert "row-highlight" in html
        assert "建议迭代其抽取 prompt" in html
        # 错误率 40% 展示
        assert "40%" in html

    def test_no_highlight_below_threshold(self):
        ids = _seed(10)
        with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feedback (intel_id, feedback_type, wrong_value, correct_value) "
                "VALUES (%s, 'subject_wrong', '未知', '三一')",
                (ids[0],),
            )
        with TestClient(app) as client:
            html = client.get("/feedback").text
        assert "row-highlight" not in html

    def test_export_jsonl(self):
        ids = _seed(2)
        with TestClient(app) as client:
            client.post(
                "/feedback",
                data={"intel_id": ids[0], "feedback_type": "subject_wrong",
                      "wrong_value": "未知", "correct_value": "三一"},
            )
            r = client.get("/feedback/export")
        assert r.status_code == 200
        line = r.text.strip().splitlines()[0]
        d = json.loads(line)
        assert d["intel_id"] == ids[0]
        assert d["feedback_type"] == "subject_wrong"
        assert d["wrong_value"] == "未知"
        assert d["correct_value"] == "三一"
        assert d["feedback_type_label"] == "主体错了"
        assert "created_at" in d


class TestFeedbackValidation:
    def test_invalid_type_rejected_422(self):
        ids = _seed(1)
        with TestClient(app) as client:
            r = client.post(
                "/feedback",
                data={"intel_id": ids[0], "feedback_type": "随便什么"},
            )
        assert r.status_code == 422

    def test_unknown_intel_404(self):
        with TestClient(app) as client:
            r = client.post(
                "/feedback",
                data={"intel_id": 99999, "feedback_type": "subject_wrong",
                      "correct_value": "三一"},
            )
        assert r.status_code == 404
