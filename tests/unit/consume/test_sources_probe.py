"""信源页试抓（TASK-1.01.01 AC3）——路由渲染、四段三态映射、编排边界、结构化日志。

run_probe 是 web 层编排缝：渲染测试 monkeypatch 它；编排测试 monkeypatch
更深的依赖（get_adapter / make_snapshot_client / probe_source）。
三态语义（设计文档 §3）：成功=通过；失败=执行且未通过；未达=前置失败未执行。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import pih.consume.web as web
from pih.collect.probe import DetailProbeResult, ProbeReport
from pih.consume import pack_loader

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _ok_report() -> ProbeReport:
    r = ProbeReport(source_id="s1", robots_allowed=True, robots_note="robots 允许")
    r.list_ok = True
    r.list_note = "列表页 200，解析出 3 条详情链接"
    r.detail_results = [
        DetailProbeResult(
            "https://x/1", True, title="某详情", snapshot_id="sha123",
            note="详情页产出，快照已存档",
        )
    ]
    return r


@pytest.fixture
def client():
    return TestClient(web.app)


@pytest.fixture
def fixture_pack(monkeypatch):
    monkeypatch.setattr(pack_loader, "_pack_path", lambda: FIXTURES / "good" / "pack.yaml")


class TestProbeRouteRendering:
    def test_success_renders_four_dimensions(self, client, fixture_pack, monkeypatch):
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(_ok_report(), None))
        r = client.post("/sources/s1/probe")
        assert r.status_code == 200
        html = r.text
        for label in ("robots", "列表页", "详情", "快照"):
            assert label in html
        assert "成功" in html
        assert "试抓通过" in html
        assert "enabled" in html  # 通过后的启用指引（AC4 语义：人改 YAML）

    def test_robots_denied_marks_following_unreached(self, client, fixture_pack, monkeypatch):
        rep = ProbeReport(source_id="s1", robots_allowed=False, robots_note="robots 拒绝：Disallow")
        rep.list_note = "robots 不允许抓取，未发起列表页请求"
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(rep, None))
        html = client.post("/sources/s1/probe").text
        assert "失败" in html
        assert html.count("未达") >= 3  # 列表/详情/快照均未执行

    def test_not_executed_note_renders(self, client, fixture_pack, monkeypatch):
        monkeypatch.setattr(
            web, "run_probe", lambda sid: web.ProbeOutcome(None, "适配器未接入（type=rss）")
        )
        html = client.post("/sources/s1/probe").text
        assert "适配器未接入" in html

    def test_unknown_source_404(self, client, fixture_pack):
        r = client.post("/sources/zzz/probe")
        assert r.status_code == 404
        assert "不在领域包" in r.text

    def test_probe_logs_json_line(self, client, fixture_pack, monkeypatch, caplog):
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(_ok_report(), None))
        with caplog.at_level(logging.INFO, logger="pih.probe"):
            client.post("/sources/s1/probe")
        record = next(r for r in caplog.records if r.name == "pih.probe")
        payload = json.loads(record.getMessage())
        assert payload["event"] == "probe"
        assert payload["source_id"] == "s1"
        assert payload["success"] is True
        assert "duration_ms" in payload


class TestProbeViewMapping:
    """四段三态映射语义锁定（robots/列表页/详情/快照）。"""

    def test_full_success(self):
        segs, success = web._probe_view(_ok_report())
        assert success is True
        assert [s["state_label"] for s in segs] == ["成功", "成功", "成功", "成功"]

    def test_robots_denied(self):
        rep = ProbeReport(source_id="s1", robots_allowed=False, robots_note="拒绝")
        segs, success = web._probe_view(rep)
        assert success is False
        assert [s["state_label"] for s in segs] == ["失败", "未达", "未达", "未达"]

    def test_list_fail_details_unreached(self):
        rep = ProbeReport(source_id="s1", robots_allowed=True, robots_note="允许")
        rep.list_note = "列表页 HTTP 403"
        segs, _ = web._probe_view(rep)
        assert [s["state_label"] for s in segs] == ["成功", "失败", "未达", "未达"]

    def test_detail_fail_snapshot_fail(self):
        rep = ProbeReport(source_id="s1", robots_allowed=True, robots_note="允许")
        rep.list_ok = True
        rep.list_note = "200"
        rep.detail_results = [DetailProbeResult("https://x/1", False, note="抓取异常")]
        segs, success = web._probe_view(rep)
        assert [s["state_label"] for s in segs] == ["成功", "成功", "失败", "失败"]
        assert success is False


class TestRunProbe:
    def test_happy_path_calls_probe_source(self, fixture_pack, monkeypatch):
        calls = {}

        def fake_probe(src, http, snapshots):
            calls["src"] = src
            return _ok_report()

        monkeypatch.setattr(web, "has_adapter", lambda s: True)
        monkeypatch.setattr(web, "make_snapshot_client", lambda: object())
        monkeypatch.setattr(web, "SnapshotStore", lambda c: c)
        monkeypatch.setattr(web, "probe_source", fake_probe)
        out = web.run_probe("s1")
        assert out.report is not None and out.note is None
        assert calls["src"].id == "s1"  # SourceConfig 已从 pack dict 构造

    def test_adapter_missing_note(self, fixture_pack, monkeypatch):
        monkeypatch.setattr(web, "has_adapter", lambda s: False)
        out = web.run_probe("s1")
        assert out.report is None
        assert "适配器未接入" in out.note

    def test_minio_unreachable_note(self, fixture_pack, monkeypatch):
        monkeypatch.setattr(web, "has_adapter", lambda s: True)
        monkeypatch.setattr(web, "make_snapshot_client", lambda: None)
        out = web.run_probe("s1")
        assert out.report is None
        assert "MinIO" in out.note
