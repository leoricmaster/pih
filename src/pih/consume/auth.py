"""API 鉴权依赖（ADR-006）。

静态 Bearer token——env PIH_API_TOKEN 缺失 → 503；
Authorization: Bearer <t> 不匹配 → 401。Web 路由不挂此依赖。
"""
from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def verify_api_token(authorization: str | None = Header(default=None)) -> None:
    """校验 Authorization: Bearer <token> 是否匹配 env PIH_API_TOKEN。

    - env 缺失 → 503（服务端配置错误，与凭据错区分便于 Agent 排错）
    - header 缺失或格式不对 → 401
    - token 不匹配 → 401（hmac.compare_digest 常量时间比较）
    """
    expected = os.environ.get("PIH_API_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="PIH_API_TOKEN 未配置")
    if authorization is None:
        raise HTTPException(status_code=401, detail="missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(status_code=401, detail="invalid Authorization scheme")
    if not hmac.compare_digest(parts[1], expected):
        raise HTTPException(status_code=401, detail="invalid credentials")
