"""领域包加载器（架构 §6.3）。

读 repo 内 YAML 领域包 → dict，再做 schema 校验。
ADR-001 后果：缺必选字段拒绝加载并指出位置。
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .errors import LoadError, ValidationResult
from .validator import validate

DEFAULT_PACK_DIR = Path(__file__).resolve().parents[3] / "domain_packs"


def load_yaml(path: str | Path) -> dict:
    """读单个 YAML 文件 → dict。文件级错误（缺失/空/非映射/解析失败）→ LoadError。"""
    p = Path(path)
    if not p.exists():
        raise LoadError(f"领域包文件不存在：{p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise LoadError(f"YAML 解析失败 {p}：{e}") from e
    if data is None:
        raise LoadError(f"领域包为空：{p}")
    if not isinstance(data, dict):
        raise LoadError(f"领域包顶层必须是映射，得到 {type(data).__name__}：{p}")
    return data


def load_and_validate(path: str | Path) -> tuple[dict, ValidationResult]:
    """加载并校验：返回 (pack_dict, result)。校验失败不在此抛，由调用方决定。"""
    pack = load_yaml(path)
    result = validate(pack)
    return pack, result


def load(path: str | Path) -> dict:
    """加载并严格校验；校验失败直接抛 LoadError（最常用入口）。"""
    pack, result = load_and_validate(path)
    result.raise_if_invalid()
    return pack
