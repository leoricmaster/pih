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


def test_every_source_has_level_and_list_url():
    """Backlog S3.2.1 AC3：信源缺必填字段（层级）拒绝。契约层保证每源有 level + list_url。

    Sprint 2 扩 schema 后，level/list_url 为必选；此测试防止回退。
    """
    pack = load(DOMAIN_PACKS_DIR / "construction_machinery" / "pack.yaml")
    for s in pack["sources"]:
        assert "level" in s, f"信源 {s['id']} 缺 level"
        assert s["level"] in ("L1", "L2", "L3", "L4"), f"信源 {s['id']} level 非法：{s['level']}"
        assert "list_url" in s, f"信源 {s['id']} 缺 list_url"


def test_three_target_sources_have_fetch_frequency():
    """首批接入的三源（CCMA/三一/cehome）须有 fetch_frequency（虽调度器未做，字段先落盘）。"""
    pack = load(DOMAIN_PACKS_DIR / "construction_machinery" / "pack.yaml")
    by_id = {s["id"]: s for s in pack["sources"]}
    for sid in ("ccma", "sany", "cehome"):
        assert "fetch_frequency" in by_id[sid], f"{sid} 缺 fetch_frequency"
        assert by_id[sid]["level"] in ("L1", "L2")


def test_event_type_enum_has_11_categories():
    """事件类型枚举 11 类（SPK-2 golden EVENTS 迁移至 event_types 节，Sprint 4）。

    枚举单一事实源从 spike golden/make_dataset.py 移入领域包配置；
    「其他」为兜底类（粗筛漏网/领域边缘内容归此，不丢弃）。
    """
    pack = load(DOMAIN_PACKS_DIR / "construction_machinery" / "pack.yaml")
    event_types = pack["event_types"]
    expected = {
        "新品发布", "功能迭代", "专利公开", "中标落地", "组织人事",
        "价格变动", "标准动态", "行业统计", "行业合作", "财报", "其他",
    }
    assert set(event_types) == expected, f"枚举不一致，缺/多：{expected ^ set(event_types)}"


def test_tag_tree_no_longer_carries_event_types():
    """Sprint 4 修正：tag_tree 不再含「事件类型」子树（曾与 event_types 重复且口径过时 8 类）。"""
    pack = load(DOMAIN_PACKS_DIR / "construction_machinery" / "pack.yaml")
    assert "事件类型" not in pack["tag_tree"]


def test_extraction_prompt_has_all_placeholders():
    """D5：extraction_prompt 含三个占位符 token（加载即校验，此处契约级回归）。"""
    pack = load(DOMAIN_PACKS_DIR / "construction_machinery" / "pack.yaml")
    prompt = pack["extraction_prompt"]
    for token in ("<事件类型>", "<标签树>", "<主体清单>"):
        assert token in prompt, f"提示词缺占位符 {token}"


def test_prompt_mentions_credibility_rating():
    """S4.2.2 AC1：提示词含信息可信度评级（Admiralty 1–6）输出键。"""
    pack = load(DOMAIN_PACKS_DIR / "construction_machinery" / "pack.yaml")
    assert "信息可信度" in pack["extraction_prompt"]
