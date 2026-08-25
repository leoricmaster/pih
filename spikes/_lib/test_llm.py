import os

import _lib.llm as llm


def test_load_env_reads_spike_env(monkeypatch):
    # load_env 从 spikes/.env（__file__ 同级父目录）读取，不覆盖已有环境变量。
    # 先清掉已设变量，确认 load_env 会把它从 spikes/.env 读回来。
    monkeypatch.delenv("PIH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("PIH_LLM_API_KEY", raising=False)
    llm.load_env()
    assert os.environ.get("PIH_LLM_BASE_URL") == "https://api.minimaxi.com/v1"
    assert os.environ.get("PIH_LLM_API_KEY", "").startswith("sk-")


def test_load_env_does_not_override_existing(monkeypatch):
    # 已设的环境变量不应被 .env 覆盖（override=False）
    monkeypatch.setenv("PIH_LLM_BASE_URL", "https://preset.example/v1")
    llm.load_env()
    assert os.environ.get("PIH_LLM_BASE_URL") == "https://preset.example/v1"
