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
        def _raise(source, http, snapshots, max_items=10):
            raise NotImplementedError

        monkeypatch.setattr("pih.cli.collect_source", _raise)
        monkeypatch.setattr("pih.cli._make_snapshot_store", lambda no_snapshot: NullSnapshotStore())
        assert main(["collect", "ccma"]) == 1
        assert "暂无特化适配器" in capsys.readouterr().err
