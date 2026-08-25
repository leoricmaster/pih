"""契约测试：domain_packs/ 下每个领域包 YAML 必须通过 schema 校验。

这是 AC1 的落点：合规的领域包加载即通过校验。
若有人改坏 pack.yaml，本测试立即拦截。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pih.domainpacks.loader import load, load_and_validate

DOMAIN_PACKS_DIR = Path(__file__).resolve().parents[2] / "domain_packs"


def _all_pack_files() -> list[Path]:
    """递归找 domain_packs/ 下所有 pack.yaml。"""
    return sorted(DOMAIN_PACKS_DIR.rglob("pack.yaml"))


@pytest.fixture(scope="module")
def pack_files() -> list[Path]:
    files = _all_pack_files()
    assert files, "domain_packs/ 下未找到任何 pack.yaml"
    return files


def test_at_least_one_domain_pack_exists(pack_files):
    assert len(pack_files) >= 1


def test_every_pack_validates_clean(pack_files):
    """每个 pack.yaml 必须校验通过（ok=True，无 error）。"""
    failures = []
    for p in pack_files:
        _, result = load_and_validate(p)
        if not result.ok:
            failures.append(f"{p.relative_to(DOMAIN_PACKS_DIR)}: {[str(i) for i in result.errors]}")
    assert not failures, "以下领域包校验失败：\n" + "\n".join(failures)


def test_construction_machinery_pack_loads_strict():
    """第一领域包严格加载不抛（load() 即严格模式）。"""
    pack = load(DOMAIN_PACKS_DIR / "construction_machinery" / "pack.yaml")
    assert pack["meta"]["domain_id"] == "construction_machinery"
    assert len(pack["sources"]) == 9  # SPK-1 锁定 9 源
    assert len(pack["competitors"]) >= 1


def test_construction_machinery_sources_match_spk1_locked():
    """SPK-1 锁定的 9 源 id 齐全（回归保护：防误删信源）。"""
    pack = load(DOMAIN_PACKS_DIR / "construction_machinery" / "pack.yaml")
    ids = {s["id"] for s in pack["sources"]}
    expected = {"ccma", "sany", "xcmg", "cehome", "d1cm", "khl", "qianlima", "cnipa_patent", "lmjx"}
    assert ids == expected, f"信源集合不一致，缺/多：{expected ^ ids}"


def test_event_type_enum_has_11_categories():
    """SPK-2 扩展后事件类型枚举 11 类（tag_tree.事件类型 落 8 类可见 + 其他 = 11）。

    需求 §4.4 枚举 11 类：新品发布/功能迭代/中标落地/行业统计/行业合作/
    财报/标准动态/其他（本 Sprint pack 显式落 8 类 + 其他；SPK-2 已验 11 类全集）。
    """
    pack = load(DOMAIN_PACKS_DIR / "construction_machinery" / "pack.yaml")
    event_types = pack["tag_tree"]["事件类型"]
    required = {
        "新品发布", "功能迭代", "中标落地", "行业统计",
        "行业合作", "财报", "标准动态", "其他",
    }
    assert required.issubset(set(event_types))
