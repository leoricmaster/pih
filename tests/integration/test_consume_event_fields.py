"""消费层事件字段集成测试（S1.3.1 AC4）。

验事件字段上线后：
  - API /api/intel/list 响应含 event_verification_status 实值（挂事件→英文 key）
  - 详情页渲染含事件状态中文 + 跃迁历史列表
  - list_by_filter 加 event_status 筛选生效
  - 排序按 W_c × map(admiralty)（confirmed > single_source > pending）
"""
from __future__ import annotations

import os
from datetime import datetime

import psycopg
import pytest
from _factory import PG_DSN
from fastapi.testclient import TestClient

from pih.consume.web import app
from pih.envs import load_env
from pih.store.db import close_pool

load_env()

pytestmark = pytest.mark.integration

API_TOKEN = os.environ.get("PIH_API_TOKEN", "test-token")


@pytest.fixture(autouse=True)
def _close_pool():
    yield
    close_pool()


def _auth():
    return {"Authorization": f"Bearer {API_TOKEN}"}


def _seed_intel_with_event(
    *,
    intel_id: int,
    source_id: str,
    subject: str,
    event_type: str,
    admiralty: str,
    event_status: str | None,
    fetched_at: datetime,
) -> None:
    """直接 INSERT intel_item + event（绕过 collect/process 流程）。"""
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO source (id, name, domain_id, url, list_url, level, reliability, enabled) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, true) ON CONFLICT (id) DO NOTHING",
            (source_id, f"{source_id} 测", "construction",
             f"http://{source_id}.example/", f"http://{source_id}.example/list",
             "L2", "B"),
        )
        event_id = None
        if event_status is not None:
            cur.execute(
                """INSERT INTO event
                (subject, event_type, status, source_count, first_seen_at, last_seen_at)
                VALUES (%s, %s, %s, 1, %s, %s) RETURNING id""",
                (subject, event_type, event_status, fetched_at, fetched_at),
            )
            event_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO verification_log
                (event_id, from_status, to_status, operator, reason)
                VALUES (%s, NULL, %s, 'system', '事件创建')""",
                (event_id, event_status),
            )
        cur.execute(
            """INSERT INTO intel_item
            (id, source_id, url, title, list_url, fetched_at, http_status, content_type,
             encoding, snapshot_id, content_sha1, raw_html, subject, event_type,
             facts, inferences, tags, quant_params, admiralty_code, process_status,
             processed_at, event_id)
            VALUES (%s, %s, %s, %s, %s, %s, 200, 'text/html', 'utf-8', %s, %s, '<html/>',
                    %s, %s, '事实', '推断', '[]'::jsonb, '{}'::jsonb, %s, 'extracted', %s, %s)""",
            (intel_id, source_id, f"http://{source_id}.example/item-{intel_id}",
             f"{subject} 测试情报", f"http://{source_id}.example/list", fetched_at,
             f"snap-{intel_id}", f"sha-{intel_id}", subject, event_type, admiralty,
             fetched_at, event_id),
        )
        conn.commit()


class TestApiEventFields:
    def test_list_response_has_event_status(self):
        """API 列表：挂事件返回 status 实值；未挂返回 None + "未挂事件"。"""
        _seed_intel_with_event(
            intel_id=1, source_id="sany", subject="三一", event_type="新品发布",
            admiralty="B2", event_status="single_source",
            fetched_at=datetime(2026, 8, 27, 10, 0, 0),
        )
        _seed_intel_with_event(
            intel_id=2, source_id="ccma", subject="徐工", event_type="财报",
            admiralty="A1", event_status=None,
            fetched_at=datetime(2026, 8, 27, 11, 0, 0),
        )

        with TestClient(app) as client:
            r = client.get("/api/intel/list", headers=_auth())
            assert r.status_code == 200
            items = {it["id"]: it for it in r.json()["items"]}

            # 挂事件的条目
            assert items[1]["event_verification_status"] == "single_source"
            assert items[1]["event_verification_note"] == ""
            assert items[1]["event_id"] is not None

            # 未挂事件
            assert items[2]["event_verification_status"] is None
            assert items[2]["event_verification_note"] == "未挂事件"

    def test_event_status_filter_works(self):
        """event_status 筛选：只返回匹配事件状态的条目。"""
        _seed_intel_with_event(
            intel_id=1, source_id="sany", subject="三一", event_type="新品发布",
            admiralty="B2", event_status="single_source",
            fetched_at=datetime(2026, 8, 27, 10, 0, 0),
        )
        _seed_intel_with_event(
            intel_id=2, source_id="ccma", subject="徐工", event_type="财报",
            admiralty="A1", event_status="pending",
            fetched_at=datetime(2026, 8, 27, 11, 0, 0),
        )

        with TestClient(app) as client:
            r = client.get(
                "/api/intel/list",
                params={"event_status": "single_source"},
                headers=_auth(),
            )
            assert r.status_code == 200
            items = r.json()["items"]
            assert len(items) == 1
            assert items[0]["id"] == 1


class TestWebEventFields:
    def test_list_page_shows_event_status_label(self):
        """列表页：挂事件显示中文标签，未挂显示 —。"""
        _seed_intel_with_event(
            intel_id=1, source_id="sany", subject="三一", event_type="新品发布",
            admiralty="B2", event_status="confirmed",
            fetched_at=datetime(2026, 8, 27, 10, 0, 0),
        )
        with TestClient(app) as client:
            html = client.get("/").text
            assert "多源确认" in html  # status_labels[confirmed]

    def test_detail_page_shows_event_timeline(self):
        """详情页：事件状态 + 跃迁历史时间线渲染。"""
        _seed_intel_with_event(
            intel_id=1, source_id="sany", subject="三一", event_type="新品发布",
            admiralty="B2", event_status="single_source",
            fetched_at=datetime(2026, 8, 27, 10, 0, 0),
        )
        with TestClient(app) as client:
            html = client.get("/intel/1").text
            assert "事件核实状态与跃迁历史" in html
            assert "单源确认" in html  # status label
            assert "独立信源数" in html
            assert "事件创建" in html  # verification_log reason
            assert "operator=system" in html


class TestRankingSortOrder:
    def test_confirmed_ranks_above_pending(self):
        """排序：confirmed(W_c=1.0) 应排在 pending(W_c=0.5) 之前，admiralty 相同。"""
        _seed_intel_with_event(
            intel_id=1, source_id="sany", subject="三一", event_type="新品发布",
            admiralty="B2", event_status="pending",
            fetched_at=datetime(2026, 8, 27, 10, 0, 0),
        )
        _seed_intel_with_event(
            intel_id=2, source_id="ccma", subject="徐工", event_type="财报",
            admiralty="B2", event_status="confirmed",
            fetched_at=datetime(2026, 8, 27, 11, 0, 0),
        )

        with TestClient(app) as client:
            r = client.get("/api/intel/list", headers=_auth())
            items = r.json()["items"]
            # 两条 admiralty 相同（B2），confirmed 应排前
            assert items[0]["id"] == 2  # confirmed
            assert items[1]["id"] == 1  # pending

    def test_high_admiralty_pending_ranks_above_low_admiralty_confirmed(self):
        """W_c × map(admiralty)：A1×pending(0.5)=0.5 > B2×confirmed(0.8×1.0)=0.8? 不——

        算式：A1 pending = min(1.0,1.0)×0.5 = 0.5
              B2 confirmed = min(0.8,0.8)×1.0 = 0.8
        B2 confirmed > A1 pending。所以 confirmed 应排前。
        """
        _seed_intel_with_event(
            intel_id=1, source_id="sany", subject="三一", event_type="新品发布",
            admiralty="A1", event_status="pending",
            fetched_at=datetime(2026, 8, 27, 10, 0, 0),
        )
        _seed_intel_with_event(
            intel_id=2, source_id="ccma", subject="徐工", event_type="财报",
            admiralty="B2", event_status="confirmed",
            fetched_at=datetime(2026, 8, 27, 11, 0, 0),
        )

        with TestClient(app) as client:
            r = client.get("/api/intel/list", headers=_auth())
            items = r.json()["items"]
            # B2 confirmed (0.8) > A1 pending (0.5)
            assert items[0]["id"] == 2  # confirmed B2
            assert items[1]["id"] == 1  # pending A1
