"""信源适配器基类与注册表（架构 §4 COLLECT 层 / ADR-001 配置精神延伸）。

适配器按 source.type 分四类基类（rss/html/api/change_monitor），注册表 type→class。
新增类型加基类 + 注册，不改核心（与 ADR-001「配置而非插件」一致：类型是有限枚举，
扩展走加基类而非动态加载第三方插件）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .rawitem import RawItem


@dataclass(frozen=True)
class SourceConfig:
    """从领域包 sources[] 抽取的单源配置（适配器消费的视图）。"""

    id: str
    name: str
    type: str
    url: str
    list_url: str
    reliability: str
    level: str
    fetch_frequency: str | None = None
    enabled: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> SourceConfig:
        return cls(
            id=d["id"],
            name=d["name"],
            type=d["type"],
            url=d["url"],
            list_url=d["list_url"],
            reliability=d["reliability"],
            level=d["level"],
            fetch_frequency=d.get("fetch_frequency"),
            enabled=d["enabled"],
        )


class SourceAdapter(ABC):
    """信源适配器基类。子类按 source.type 实现。"""

    type: str = ""

    @abstractmethod
    def fetch_list(self, source: SourceConfig) -> list[str]:
        """抓取列表页，返回详情页 URL 列表。"""
        ...

    @abstractmethod
    def fetch_detail(self, url: str, source: SourceConfig) -> RawItem:
        """抓取单条详情，产出 RawItem（含快照已存档）。"""
        ...


# 两层注册：按 source.id 注册特化适配器，按 source.type 注册通用基类
_REGISTRY_BY_ID: dict[str, type[SourceAdapter]] = {}
_REGISTRY_BY_TYPE: dict[str, type[SourceAdapter]] = {}


def register(cls: type[SourceAdapter]) -> type[SourceAdapter]:
    """类装饰器：按 cls.type 注册通用适配器基类。

    特化子类（某源专属解析）用 register_for_source 按 source.id 注册。
    """
    if not cls.type:
        raise ValueError(f"{cls.__name__} 未声明 type")
    if cls.type in _REGISTRY_BY_TYPE and _REGISTRY_BY_TYPE[cls.type] is not cls:
        raise ValueError(f"type '{cls.type}' 已注册：{_REGISTRY_BY_TYPE[cls.type].__name__}")
    _REGISTRY_BY_TYPE[cls.type] = cls
    return cls


def register_for_source(source_id: str):
    """类装饰器工厂：按 source.id 注册特化适配器（优先于 type 查找）。"""

    def decorator(cls: type[SourceAdapter]) -> type[SourceAdapter]:
        if source_id in _REGISTRY_BY_ID:
            raise ValueError(f"source '{source_id}' 已注册：{_REGISTRY_BY_ID[source_id].__name__}")
        _REGISTRY_BY_ID[source_id] = cls
        return cls

    return decorator


def get_adapter(source: SourceConfig, *args: object, **kwargs: object) -> SourceAdapter:
    """取适配器实例：优先按 source.id 查特化，退回按 source.type 查通用。"""
    cls = _REGISTRY_BY_ID.get(source.id) or _REGISTRY_BY_TYPE.get(source.type)
    if cls is None:
        raise KeyError(
            f"无适配器（source.id={source.id}, type={source.type}；"
            f"已注册 id={list(_REGISTRY_BY_ID)}, type={list(_REGISTRY_BY_TYPE)}）"
        )
    return cls(*args, **kwargs)  # type: ignore[call-arg]
