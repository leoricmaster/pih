"""pih.envs.load_env 分层加载单元测试（env 漂移治理，2026-08-31）。

验证优先级承诺：真实环境变量 > .env > .env.defaults。
用 tmp_path 造两层文件，monkeypatch 清理被测键避免污染真实环境。
"""
from __future__ import annotations

import os

from pih.envs import load_env

KEY = "PIH_TEST_ENV_KEY"


def _clean(monkeypatch):
    monkeypatch.delenv(KEY, raising=False)


def _write(path, text):
    path.write_text(text, encoding="utf-8")


def test_defaults_fill_when_override_missing(tmp_path, monkeypatch):
    """无 .env 时 defaults 兜底（新机 clone 场景）。"""
    _clean(monkeypatch)
    _write(tmp_path / ".env.defaults", f"{KEY}=from_defaults\n")
    load_env(cwd=tmp_path)
    assert os.environ[KEY] == "from_defaults"


def test_override_beats_defaults(tmp_path, monkeypatch):
    """两层都有时 .env 胜出（秘密覆盖默认值）。"""
    _clean(monkeypatch)
    _write(tmp_path / ".env", f"{KEY}=from_override\n")
    _write(tmp_path / ".env.defaults", f"{KEY}=from_defaults\n")
    load_env(cwd=tmp_path)
    assert os.environ[KEY] == "from_override"


def test_real_env_beats_override(tmp_path, monkeypatch):
    """真实环境变量最强（CI/容器注入场景，load_env 不得翻转）。"""
    _write(tmp_path / ".env", f"{KEY}=from_override\n")
    _write(tmp_path / ".env.defaults", f"{KEY}=from_defaults\n")
    monkeypatch.setenv(KEY, "from_real_env")
    load_env(cwd=tmp_path)
    assert os.environ[KEY] == "from_real_env"


def test_missing_files_tolerated(tmp_path, monkeypatch):
    """两层文件都不存在：不抛错、不设值（最小 clone 场景）。"""
    _clean(monkeypatch)
    load_env(cwd=tmp_path)
    assert KEY not in os.environ


def test_defaults_never_overwrite_existing_real_env(tmp_path, monkeypatch):
    """defaults 的 override=False：真实 env 已设（即使 defaults 也有）不翻转。"""
    _write(tmp_path / ".env.defaults", f"{KEY}=from_defaults\n")
    monkeypatch.setenv(KEY, "from_real_env")
    load_env(cwd=tmp_path)
    assert os.environ[KEY] == "from_real_env"
