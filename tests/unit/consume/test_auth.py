"""verify_api_token 单测（Sprint 5a，ADR-006）。

三分支：env 缺失 503 / header 错误 401 / 正确通过。hmac.compare_digest 被调用。
"""
from __future__ import annotations

import hmac

import pytest
from fastapi import HTTPException

from pih.consume.auth import verify_api_token


class TestEnvMissing:
    def test_env_missing_returns_503(self, monkeypatch):
        monkeypatch.delenv("PIH_API_TOKEN", raising=False)
        with pytest.raises(HTTPException) as exc:
            verify_api_token(authorization="Bearer xxx")
        assert exc.value.status_code == 503

    def test_env_empty_string_returns_503(self, monkeypatch):
        monkeypatch.setenv("PIH_API_TOKEN", "")
        with pytest.raises(HTTPException) as exc:
            verify_api_token(authorization="Bearer xxx")
        assert exc.value.status_code == 503


class TestHeaderErrors:
    def test_missing_header_returns_401(self, monkeypatch):
        monkeypatch.setenv("PIH_API_TOKEN", "secret")
        with pytest.raises(HTTPException) as exc:
            verify_api_token(authorization=None)
        assert exc.value.status_code == 401

    def test_wrong_scheme_returns_401(self, monkeypatch):
        monkeypatch.setenv("PIH_API_TOKEN", "secret")
        with pytest.raises(HTTPException) as exc:
            verify_api_token(authorization="Basic secret")
        assert exc.value.status_code == 401

    def test_no_space_returns_401(self, monkeypatch):
        monkeypatch.setenv("PIH_API_TOKEN", "secret")
        with pytest.raises(HTTPException) as exc:
            verify_api_token(authorization="Bearersecret")
        assert exc.value.status_code == 401

    def test_wrong_token_returns_401(self, monkeypatch):
        monkeypatch.setenv("PIH_API_TOKEN", "secret")
        with pytest.raises(HTTPException) as exc:
            verify_api_token(authorization="Bearer wrong")
        assert exc.value.status_code == 401


class TestCorrectToken:
    def test_passes_silently(self, monkeypatch):
        monkeypatch.setenv("PIH_API_TOKEN", "secret")
        # 不抛即通过
        verify_api_token(authorization="Bearer secret")

    def test_compare_digest_used(self, monkeypatch):
        """常量时间比较防时序攻击——验 compare_digest 被调用而非 ==。"""
        monkeypatch.setenv("PIH_API_TOKEN", "secret")
        called = {"n": 0}
        real = hmac.compare_digest

        def spy(a, b):
            called["n"] += 1
            return real(a, b)

        monkeypatch.setattr("pih.consume.auth.hmac.compare_digest", spy)
        verify_api_token(authorization="Bearer secret")
        assert called["n"] == 1
