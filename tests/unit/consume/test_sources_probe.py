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
    r.list_count = 3
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
    def test_success_renders_summary_not_pipeline_segments(self, client, fixture_pack, monkeypatch):
        """R7：成功路径收敛为结论+产出摘要+快照链接；管线分段不呈现。"""
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(_ok_report(), None))
        r = client.post("/sources/s1/probe")
        assert r.status_code == 200
        html = r.text
        assert "试抓通过" in html
        assert "抓到 1 条正文" in html
        assert "原文已存档" in html
        assert "示例：『某详情』" in html  # 「真抓到了」的用户可感证据
        assert "enabled" in html  # 通过后的启用指引（AC4 语义：人改 YAML）
        assert 'class="probe-segs"' not in html  # 工程分段不上成功路径
        assert "robots 合规检查" not in html
        assert "列表页可达" not in html

    def test_robots_denied_marks_following_unreached(self, client, fixture_pack, monkeypatch):
        rep = ProbeReport(source_id="s1", robots_allowed=False, robots_note="robots 拒绝：Disallow")
        rep.list_note = "robots 不允许抓取，未发起列表页请求"
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(rep, None))
        html = client.post("/sources/s1/probe").text
        assert "失败" in html
        assert html.count("未达") >= 3  # 列表/详情/快照均未执行
        assert "robots 合规检查" in html  # 失败路径保留分段诊断（R7）
        assert "试抓未通过" in html
        assert "服务日志" in html

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

    def test_robots_detail_not_rendered_on_page(self, client, fixture_pack, monkeypatch):
        """二轮验收反馈：robots 排查材料（正文前 200 字 dump）不上客户页。"""
        rep = _ok_report()
        rep.robots_invalid = True
        rep.robots_note = "无效 robots（软 200）：按未声明处理【告警】建议人工复核站点行为"
        rep.robots_detail = "Content-Type=text/html，正文前 200 字：'<html>…'"
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(rep, None))
        html = client.post("/sources/s1/probe").text
        assert "未提供有效 robots 声明" in html  # 用户视角解释，非实现者术语
        assert "正文前" not in html

    def test_probe_log_carries_robots_detail(self, client, fixture_pack, monkeypatch, caplog):
        """排查材料只留日志（用户裁定）：pih.probe JSON line 含 robots_detail。"""
        rep = _ok_report()
        rep.robots_detail = "Content-Type=text/html，正文前 200 字：'<html>…'"
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(rep, None))
        with caplog.at_level(logging.INFO, logger="pih.probe"):
            client.post("/sources/s1/probe")
        record = next(r for r in caplog.records if r.name == "pih.probe")
        payload = json.loads(record.getMessage())
        assert "正文前 200 字" in payload["robots_detail"]


class TestProbeViewMapping:
    """四段三态映射语义锁定（robots/列表页/详情/快照）+ 用户视角文案（R4）。"""

    def test_full_success(self):
        segs, success = web._probe_view(_ok_report())
        assert success is True
        assert [s["state_label"] for s in segs] == ["成功", "成功", "成功", "成功"]

    def test_user_copy_per_segment_on_success(self):
        """R4：各段 note 是用户能据以行动的话，不是实现者术语。"""
        segs, _ = web._probe_view(_ok_report())
        robots, list_, detail, snap = segs
        assert robots["label"] == "robots 合规检查"
        assert robots["note"] == "允许抓取"
        assert list_["note"] == "列表页可达，找到 3 条待抓内容"
        assert detail["note"].startswith("已抓取 1/1 条正文")
        assert "『某详情』" in detail["note"]  # 示例标题给用户可感证据
        assert snap["note"] == "1 份原文快照已存档"

    def test_robots_soft200_explains_undeclared_treatment(self):
        """软 200：向用户解释「按无限制处理」并提示确认。"""
        rep = _ok_report()
        rep.robots_invalid = True
        segs, _ = web._probe_view(rep)
        assert "未提供有效 robots 声明" in segs[0]["note"]
        assert "按无限制处理" in segs[0]["note"]

    def test_robots_denied_note_passes_through(self):
        rep = ProbeReport(source_id="s1", robots_allowed=False, robots_note="拒绝：Disallow")
        segs, _ = web._probe_view(rep)
        assert segs[0]["note"] == "拒绝：Disallow"  # 失败原因原样透传

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


class TestProbeSummary:
    """R7：成功路径的产出摘要——一句「试抓产出了什么」。"""

    def test_summary_counts_and_sample(self):
        assert web._probe_summary(_ok_report()) == (
            "抓到 1 条正文，1 份原文已存档，示例：『某详情』"
        )

    def test_summary_without_title_omits_sample(self):
        rep = _ok_report()
        rep.detail_results[0].title = ""
        assert "示例" not in web._probe_summary(rep)


class TestProbeWarnAggregation:
    """告警与三态正交：通过+告警时结论行聚合呈现（TASK-1.01.01 验收反馈修复）。"""

    def test_warns_extraction(self):
        rep = _ok_report()
        rep.robots_invalid = True
        warns = web._probe_warns(rep)
        assert len(warns) == 1
        assert "未提供有效 robots 声明" in warns[0]
        assert "请确认可接受" in warns[0]

    def test_no_warns_when_valid(self):
        assert web._probe_warns(_ok_report()) == []

    def test_pass_with_warn_renders_review_verdict(self, client, fixture_pack, monkeypatch):
        rep = _ok_report()
        rep.robots_invalid = True
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(rep, None))
        html = client.post("/sources/s1/probe").text
        assert "试抓通过" in html
        assert "含 1 项告警" in html
        assert "确认无碍" in html


class TestVerdictCopy:
    """R6：结论行告诉用户下一步做什么（启用路径）与失败时去哪排查。"""

    def test_pass_verdict_guides_manual_enable(self, client, fixture_pack, monkeypatch):
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(_ok_report(), None))
        html = client.post("/sources/s1/probe").text
        assert "启用本信源" in html
        assert "enabled 改为 true" in html
        assert "人工操作" in html

    def test_fail_verdict_points_to_service_log(self, client, fixture_pack, monkeypatch):
        rep = ProbeReport(source_id="s1", robots_allowed=False, robots_note="拒绝")
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(rep, None))
        html = client.post("/sources/s1/probe").text
        assert "试抓未通过" in html
        assert "服务日志" in html


class TestSnapshotLinks:
    """R5：试抓报告给出原文快照的查看入口（真存档了→点得开）。"""

    def test_pass_renders_presigned_snapshot_links(
        self, client, fixture_pack, monkeypatch
    ):
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(_ok_report(), None))
        monkeypatch.setattr(web, "make_snapshot_client", lambda: object())
        monkeypatch.setattr(
            web, "presigned_snapshot_url",
            lambda c, sid, sha: f"http://minio.local/snapshots/{sid}/{sha}.html",
        )
        html = client.post("/sources/s1/probe").text
        assert 'href="http://minio.local/snapshots/s1/sha123.html"' in html
        assert "查看原文" in html
        assert "『某详情』" in html

    def test_minio_unreachable_degrades_to_no_links(self, client, fixture_pack, monkeypatch):
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(_ok_report(), None))
        monkeypatch.setattr(web, "make_snapshot_client", lambda: None)
        html = client.post("/sources/s1/probe").text
        assert "查看原文" not in html
        assert "已存档" in html  # 存档事实仍在（试抓时已写入）

    def test_pass_without_warn_keeps_plain_verdict(self, client, fixture_pack, monkeypatch):
        monkeypatch.setattr(web, "run_probe", lambda sid: web.ProbeOutcome(_ok_report(), None))
        html = client.post("/sources/s1/probe").text
        assert "项告警" not in html
