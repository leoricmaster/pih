"""领域包校验器（架构 §6.3 / ADR-001）。

把 jsonschema 原生 ValidationError 转成带清晰 path 的 ValidationIssue。
关键转换：required 类错误 jsonschema 给 path=[]，缺失字段名在 message 中，
这里重写为 path=<缺失字段>。其余按 jq 风格拼接 path。
"""
from __future__ import annotations

import re

import jsonschema

from .errors import ValidationIssue, ValidationResult
from .schema import DOMAIN_PACK_SCHEMA


def _jq_path(error: jsonschema.ValidationError) -> str:
    """把 jsonschema 的 absolute_path（list[str|int]）转成 jq 风格字符串。

    例：['sources', 0, 'type'] → 'sources[0].type'
        ['meta', 'version']    → 'meta.version'
        []                      → ''（根级，required 错误走特殊处理）
    """
    parts: list[str] = []
    for seg in error.absolute_path:
        if isinstance(seg, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{seg}]"
            else:
                parts.append(f"[{seg}]")
        else:
            parts.append(str(seg))
    return ".".join(parts)


def _extract_required_field(error: jsonschema.ValidationError) -> str | None:
    """required 错误的 message 形如 "'meta' is a required property"；
    此时 absolute_path 为空，需从 message 提取字段名作为 path。"""
    if error.validator != "required":
        return None
    # required 错误的 validator_value 是必选字段名列表，
    # error.message 列出本次缺失的字段
    msg = error.message
    # "'meta' is a required property" 或 "'a', 'b' are required properties"
    names = re.findall(r"'([^']+)'", msg)
    return names[0] if names else None


def _to_issue(error: jsonschema.ValidationError) -> ValidationIssue:
    """单条 ValidationError → ValidationIssue。"""
    required_field = _extract_required_field(error)
    if required_field is not None:
        # required 错误：path 指向父对象路径下的缺失字段
        parent = _jq_path(error)
        path = f"{parent}.{required_field}" if parent else required_field
        return ValidationIssue(path=path, message="必选字段缺失")

    path = _jq_path(error)
    if not path:
        path = "<root>"
    # enum 违规等：保留 jsonschema 原生 message（已含候选值，信息充分）
    return ValidationIssue(path=path, message=error.message)


def validate(pack: dict) -> ValidationResult:
    """校验领域包 dict，返回 ValidationResult。"""
    validator = jsonschema.Draft202012Validator(DOMAIN_PACK_SCHEMA)
    errors = sorted(validator.iter_errors(pack), key=lambda e: list(e.absolute_path))
    issues = [_to_issue(e) for e in errors]
    return ValidationResult(ok=len(issues) == 0, issues=issues)
