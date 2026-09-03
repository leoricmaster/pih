"""CLI 单元测试——参数与用法错误路径（不触网络、不触 MinIO）。"""
from __future__ import annotations

from pih.cli import main
from pih.collect.probe import NullSnapshotStore


class TestUsageErrors:
    def test_probe_unknown_source_id(self, capsys):
        assert main(["probe-source", "no-such-id", "--no-snapshot"]) == 2
        err = capsys.readouterr().err
        assert "未知信源 id：no-such-id" in err
        assert "ccma" in err  # 列出可用 id

    def test_probe_requires_id_or_all(self, capsys):
        assert main(["probe-source", "--no-snapshot"]) == 2
        assert "source_id 或 --all" in capsys.readouterr().err

    def test_probe_id_and_all_mutually_exclusive(self, capsys):
        assert main(["probe-source", "ccma", "--all", "--no-snapshot"]) == 2
        assert "source_id 或 --all" in capsys.readouterr().err

    def test_collect_unknown_source_id(self, capsys):
        assert main(["collect", "no-such-id"]) == 2
        assert "未知信源 id" in capsys.readouterr().err

    def test_bad_pack_path(self, capsys):
        assert main(["probe-source", "ccma", "--pack", "/nonexistent/pack.yaml",
                     "--no-snapshot"]) == 2
        assert "领域包加载失败" in capsys.readouterr().err

    def test_probe_source_without_specialized_adapter(self, capsys, monkeypatch):
        """type=html 但无特化子类的源：通用基类解析钩子抛 NotImplementedError，
        CLI 须转为失败报告（退出码 1），不裸 traceback。"""
        def _raise(source, http, snapshots, details=1):
            raise NotImplementedError

        monkeypatch.setattr("pih.cli.probe_source", _raise)
        assert main(["probe-source", "d1cm", "--no-snapshot"]) == 1
        out = capsys.readouterr().out
        assert "暂无特化适配器" in out

    def test_collect_source_without_specialized_adapter(self, capsys, monkeypatch):
        def _raise(source, http, snapshots, max_items=10, repository=None):
            raise NotImplementedError

        monkeypatch.setattr("pih.cli.collect_source", _raise)
        monkeypatch.setattr("pih.cli._make_snapshot_store", lambda no_snapshot: NullSnapshotStore())
        # 用 --no-ingest 跳过 PG 连接（单元测试不依赖 DB）
        assert main(["collect", "ccma", "--no-ingest"]) == 1
        assert "暂无特化适配器" in capsys.readouterr().err


class TestProbeReportRendering:
    def test_probe_report_prints_robots_detail(self, capsys, monkeypatch):
        """二轮验收反馈：排查材料分层——CLI（开发者面）保留 dump，Web 客户页不上。"""
        from pih.collect.probe import DetailProbeResult, ProbeReport

        rep = ProbeReport(
            source_id="ccma", robots_allowed=True,
            robots_note="无效 robots（软 200）：按未声明处理【告警】建议人工复核站点行为",
            robots_detail="Content-Type=text/html，正文前 200 字：'<html>…'",
        )
        rep.list_ok = True
        rep.list_note = "列表页 200，解析出 51 条详情链接"
        rep.detail_results = [
            DetailProbeResult("https://x/1", True, title="t", snapshot_id="s" * 40)
        ]
        monkeypatch.setattr("pih.cli.probe_source", lambda *a, **k: rep)
        assert main(["probe-source", "ccma", "--no-snapshot"]) == 0
        out = capsys.readouterr().out
        assert "正文前 200 字" in out  # CLI 排查面保留


class TestProcessUsageErrors:
    def _clear_llm_env(self, monkeypatch):
        for var in ("PIH_LLM_BASE_URL", "PIH_LLM_API_KEY",
                    "PIH_LLM_LARGE_MODEL", "PIH_LLM_SMALL_MODEL"):
            monkeypatch.setenv(var, "")
        monkeypatch.setattr("pih.cli.get_pool", lambda: None)  # 跳过 PG 连接

    def test_missing_llm_env_exits_usage(self, capsys, monkeypatch):
        """AC8：LLM env 缺失 → 退出码 2 + 配置指引，不产生半写状态。"""
        self._clear_llm_env(monkeypatch)
        assert main(["process"]) == 2
        err = capsys.readouterr().err
        assert "PIH_LLM" in err
        assert ".env" in err

    def test_unknown_source_id_exits_usage(self, capsys, monkeypatch):
        """信源 id 未知 → 退出码 2（LLM env 齐备才到达该校验）。"""
        for var in ("PIH_LLM_BASE_URL", "PIH_LLM_API_KEY",
                    "PIH_LLM_LARGE_MODEL", "PIH_LLM_SMALL_MODEL"):
            monkeypatch.setenv(var, "x")
        monkeypatch.setattr("pih.cli.get_pool", lambda: None)
        assert main(["process", "--source-id=no-such"]) == 2
        assert "未知信源 id" in capsys.readouterr().err


class TestQueryUsageErrors:
    def test_requires_id_or_filter(self, capsys):
        assert main(["query"]) == 2
        assert "筛选条件" in capsys.readouterr().err

    def test_structured_filters_accepted_without_source_id(self, capsys, monkeypatch):
        """--event-type 等结构化条件可独立使用（不再强制 --source-id）。

        只验参数解析层——list_by_filter 之前的校验不再拒绝；
        mock pool + repository 返回空列表，验退出码 0。
        """
        from unittest.mock import MagicMock

        repo = MagicMock()
        repo.list_by_filter.return_value = []
        monkeypatch.setattr("pih.cli.get_pool", lambda: None)
        monkeypatch.setattr("pih.cli.IntelRepository", lambda pool: repo)
        monkeypatch.setattr("pih.cli.close_pool", lambda: None)
        assert main(["query", "--event-type=新品发布"]) == 0
        repo.list_by_filter.assert_called_once_with(
            subject=None, event_type="新品发布", tag=None,
            source_id=None, limit=10,
        )


class TestReplayCommand:
    """pih replay <id>：重放失败条目 → 重置 pending 重入处理链（AC4 可重放）。"""

    def test_replay_resets_to_pending(self, capsys, monkeypatch):
        from unittest.mock import MagicMock

        rec = MagicMock()
        rec.id = 7
        rec.title = "(抓取失败)"
        rec.process_status = "dead"
        rec.process_error = "ConnectionError: timeout"
        repo = MagicMock()
        repo.get.return_value = rec
        monkeypatch.setattr("pih.cli.get_pool", lambda: None)
        monkeypatch.setattr("pih.cli.IntelRepository", lambda pool: repo)
        monkeypatch.setattr("pih.cli.close_pool", lambda: None)
        assert main(["replay", "7"]) == 0
        repo.mark_status.assert_called_once()
        args = repo.mark_status.call_args[0]
        assert args[0] == 7
        assert args[1] == "pending"  # 默认重置 pending 重入链
        out = capsys.readouterr().out
        assert "已重置" in out
        assert "ConnectionError: timeout" in out  # 失败原因可查

    def test_replay_unknown_id_fails(self, capsys, monkeypatch):
        from unittest.mock import MagicMock

        repo = MagicMock()
        repo.get.return_value = None
        monkeypatch.setattr("pih.cli.get_pool", lambda: None)
        monkeypatch.setattr("pih.cli.IntelRepository", lambda pool: repo)
        monkeypatch.setattr("pih.cli.close_pool", lambda: None)
        assert main(["replay", "999"]) == 1
        assert "未找到" in capsys.readouterr().err
