"""消费层领域包加载辅助（抽出以避免 web/api 循环 import）。

web.py 与 api.py 共用 _load_pack / _pack_ranking / _load_pack_vocab，
保证 Web 与 JSON API 出口同源（ADR-006）：ranking 注入一致 → 排序同序。
"""
from __future__ import annotations

from pathlib import Path


def _pack_path() -> Path:
    """领域包路径：cwd 优先，回退包内默认目录。"""
    from pih.domainpacks.loader import DEFAULT_PACK_DIR

    cwd_pack = Path("domain_packs/construction_machinery/pack.yaml")
    fallback = DEFAULT_PACK_DIR / "construction_machinery" / "pack.yaml"
    return cwd_pack if cwd_pack.exists() else fallback


def load_pack() -> dict | None:
    """加载领域包 dict（供 ranking 注入与主体归一化复用）。

    万一加载失败返回 None——调用方降级（ranking=None 回退简版排序，
    主体清单空时反馈表单自由输入仍可用）。模块级不缓存：领域包在 repo 内
    应恒可加载，每次请求 load 一次开销可忽略（YAML < 10KB）。
    """
    from pih.domainpacks.loader import load

    try:
        return load(_pack_path())
    except Exception:  # noqa: BLE001 领域包缺失不阻塞消费层
        return None


def load_sources_view() -> tuple[list[dict] | None, list, str | None]:
    """信源页数据（TASK-1.01.01 AC2）。

    返回 (sources, issues, error)：pack 有效 → (sources, [], None)；
    校验失败 → (None, errors, None)——信源页兼任配置诊断面，issues
    呈现给运营者而非吞掉（与 load_pack 的降级语义相反：诊断面错误必须可见）；
    文件级错误 → (None, [], error 文案)。均不抛，呈现是页面的事。
    """
    from pih.domainpacks.errors import LoadError
    from pih.domainpacks.loader import load_and_validate

    try:
        pack, result = load_and_validate(_pack_path())
    except LoadError as e:
        return None, [], str(e)
    if not result.ok:
        return None, result.errors, None
    return pack["sources"], [], None


def pack_ranking() -> dict | None:
    """从领域包取 ranking 节（注入 QueryService 排序权重，架构 §6.2）。"""
    pack = load_pack()
    if pack is None:
        return None
    return pack.get("ranking")


def load_pack_vocab() -> tuple[list[str], list[str]]:
    """详情页反馈表单的候选清单（主体 datalist / 事件类型 select）。"""
    pack = load_pack()
    if pack is None:
        return [], []
    subjects = [
        name
        for c in pack["competitors"]
        for name in [c["display_name"], *c.get("aliases", [])]
    ]
    return subjects, list(pack["event_types"])


def load_filter_vocab() -> tuple[list[str], list[str], list[str]]:
    """列表筛选表单候选（TASK-2.01.01 D3）：主体 datalist（规范名+别名）/
    事件类型 select / 标签 select（tag_tree 叶子扁平化）。pack 缺失时全空
    （自由输入仍可用）。"""
    pack = load_pack()
    if pack is None:
        return [], [], []
    subjects = [
        name
        for c in pack["competitors"]
        for name in [c["display_name"], *c.get("aliases", [])]
    ]
    tags = [leaf for leaves in pack["tag_tree"].values() for leaf in leaves]
    return subjects, list(pack["event_types"]), tags
