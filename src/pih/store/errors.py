"""store 层异常（Sprint 3）。"""
from __future__ import annotations


class StoreError(Exception):
    """store 层基础异常。"""


class IntegrityConflict(StoreError):
    """幂等冲突：content_sha1 已存在（ADR-007）。非失败，调用方转 SKIPPED。"""
