"""领域包加载器（架构 §6.3）。

读 repo 内 YAML 领域包 → dict，再做 schema 校验。
ADR-001 后果：缺必选字段拒绝加载并指出位置（路径 + 行号）。
"""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import yaml
from yaml.nodes import MappingNode, SequenceNode

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


def _parse_path(path: str) -> list[tuple[str, int | None]]:
    """jq 风格路径 → (键, 可选数组下标) 段。

    'sources[0].reliability' → [('sources', 0), ('reliability', None)]；
    无法解析（如 '<root>'）→ []。
    """
    segs: list[tuple[str, int | None]] = []
    for m in re.finditer(r"([^\.\[\]]+)(?:\[(\d+)\])?", path):
        idx = int(m.group(2)) if m.group(2) is not None else None
        segs.append((m.group(1), idx))
    return segs


def _line_for(node: object, path: str) -> int | None:
    """沿 compose 出的 YAML 节点树定位 issue 行号（1 基）。

    键缺失（缺必选字段）→ 父映射起始行，即运营者该看的位置；
    键存在 → 值节点起始行（enum 违规等指向出错的值）。路径不可解析 → None。
    """
    cur: object = node
    segs = _parse_path(path)
    for i, (key, idx) in enumerate(segs):
        if not isinstance(cur, MappingNode):
            return None
        value = next((v for k, v in cur.value if k.value == key), None)
        if value is None:
            return cur.start_mark.line + 1
        if idx is not None:
            if not isinstance(value, SequenceNode) or idx >= len(value.value):
                return None
            value = value.value[idx]
        if i == len(segs) - 1:
            return value.start_mark.line + 1
        cur = value
    return None


def load_and_validate(path: str | Path) -> tuple[dict, ValidationResult]:
    """加载并校验：返回 (pack_dict, result)。校验失败不在此抛，由调用方决定。

    失败时经 yaml.compose 回填 issue 行号（TASK-1.01.01 AC1）；
    validator 保持 dict 纯净，行号是文件层关切。
    """
    pack = load_yaml(path)
    result = validate(pack)
    if not result.ok:
        try:
            tree = yaml.compose(Path(path).read_text(encoding="utf-8"))
        except yaml.YAMLError:  # load_yaml 已验证可解析，此为兜底
            tree = None
        if tree is not None:
            result.issues = [
                replace(i, line=_line_for(tree, i.path)) if i.line is None else i
                for i in result.issues
            ]
    return pack, result


def load(path: str | Path) -> dict:
    """加载并严格校验；校验失败直接抛 LoadError（最常用入口）。"""
    pack, result = load_and_validate(path)
    result.raise_if_invalid()
    return pack
