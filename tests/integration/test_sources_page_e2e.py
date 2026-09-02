"""信源页端到端集成（TASK-1.01.01 AC2/AC3）——compose 全栈 + 仓内真领域包。

与 unit 层差异：不 monkeypatch run_probe/get_adapter——真实适配器注册表、
真实 MinIO（make_snapshot_client → SnapshotStore）、真实 lifespan PG pool。
外网抓取仍在缝处打桩（probe_source）——真实站点抓取属 live 层（test_cli_live.py）。

需 docker compose up postgres minio。@pytest.mark.integration。
"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

import pih.consume.web as web
from pih.collect.probe import DetailProbeResult, ProbeReport
from pih.consume.pack_loader import load_sources_view
from pih.envs import load_env

load_env()

pytestmark = pytest.mark.integration


def _ok_report(source_id: str) -> ProbeReport:
    r = ProbeReport(source_id=source_id, robots_allowed=True, robots_note="robots 允许")
    r.list_ok = True
    r.list_note = "列表页 200"
    r.detail_results = [
        DetailProbeResult("https://x/1", True, snapshot_id="sha1", note="详情产出")
    ]
    return r


class TestSourcesPageE2E:
    def test_lists_all_real_pack_sources(self):
        """AC2：真领域包全信源列出，每源带试抓表单入口。"""
        with TestClient(web.app) as client:
            r = client.get("/sources")
        assert r.status_code == 200
        sources, issues, error = load_sources_view()
        assert error is None and not issues
        assert len(sources) >= 3  # 仓内真实包不止夹具规模
        for s in sources:
            assert f"/sources/{s['id']}/probe" in r.text

    def test_probe_uses_real_registry_and_minio(self, monkeypatch):
        """AC3：真实注册表（sany 有 id 适配器）+ 真 MinIO 建出 SnapshotStore；
        外网抓取在 probe_source 缝打桩。"""
        seen = {}

        def fake_probe(src, http, snapshots):
            seen["src"], seen["snapshots"] = src, snapshots
            return _ok_report(src.id)

        monkeypatch.setattr(web, "probe_source", fake_probe)
        with TestClient(web.app) as client:
            r = client.post("/sources/sany/probe")
        assert r.status_code == 200
        assert "试抓通过" in r.text
        assert seen["src"].id == "sany"
        assert seen["snapshots"] is not None  # 真 MinIO 客户端构建的 SnapshotStore

    def test_probe_api_type_source_without_adapter(self):
        """AC3 回归锁：type=api 的源（xcmg）无适配器 → 「未执行」不 500。"""
        with TestClient(web.app) as client:
            r = client.post("/sources/xcmg/probe")
        assert r.status_code == 200
        assert "适配器未接入" in r.text
