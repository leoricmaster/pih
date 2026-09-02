"""领域包加载/校验错误类型（架构 §6.3 / ADR-001）。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ValidationIssue:
    """单条校验问题：带路径与人类可读说明。

    path 采用 jq 风格定位：顶层字段用字段名，数组元素用 [i]。
    例：'meta' / 'sources[0].reliability' / 'tag_tree'。
    """

    path: str
    message: str
    severity: str = "error"  # error | warning
    line: int | None = None  # YAML 源文件行号（1 基），加载器回填；无法定位为 None

    def __str__(self) -> str:
        if self.line is not None:
            return f"{self.path}: {self.message}（第 {self.line} 行）"
        return f"{self.path}: {self.message}"


@dataclass
class ValidationResult:
    """校验结果：ok 与问题清单。"""

    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def raise_if_invalid(self) -> None:
        """校验失败即抛 LoadError（ADR-001：缺必选字段拒绝加载）。"""
        if not self.ok:
            msgs = "\n".join(f"  - {i}" for i in self.errors)
            raise LoadError(f"领域包校验失败，{len(self.errors)} 个错误：\n{msgs}")


class LoadError(Exception):
    """领域包加载失败（文件缺失/解析错误/校验不通过）。"""
