"""Process 端到端集成测试（S1.1.2 采集入库 + S1.2.1 结构化抽取）。

需 docker compose up（postgres + minio）+ 外网。真实 LLM 段（AC1/AC5/AC6）
另需 PIH_LLM_* env，任一缺失该类 skip（密闭性口径）；
脚本化 chat 段（AC2/AC3/AC4）不依赖 LLM 凭据，注入确定性失败路径。

验收路径：
  AC1  collect ccma → process → ≥1 条 extracted：subject/event_type/facts
      非空 + admiralty_code 首字符 = source.reliability（ccma 为 B）
  AC2  LLM 输出反复未过 schema（脚本化 chat + 真实库）→ needs_manual，
      条目保留可 pih query 查到（不丢弃）
  AC3  粗筛判无关（脚本化 chat）→ filtered_out，行保留可查（审计口径）
  AC4  粗筛 API 失败（脚本化 chat 抛 LLMError）→ 灰条目保留，走抽取
  AC5  query --event-type=<实际抽取值> 召回 extracted 条目
  AC6  二次 process → 处理 0 条（pending 幂等）
  AC7  主体占位值「未知」（脚本化 chat）→ needs_manual + 结构化字段保留
      （S1.2.1 AC3 后验质量门）

断言结构不断言具体文本（LLM 输出不稳定）。
"""
from __future__ import annotations

import os

import pytest
from _factory import ScriptChat, ok_pred, usage
from conftest import q as _q

from pih.cli import _default_pack, main
from pih.domainpacks.loader import load
from pih.envs import load_env
from pih.process.llm import LLMError
from pih.process.run import ProcessRunner
from pih.store.db import close_pool, get_pool
from pih.store.repository import IntelRepository

load_env()

LLM_ENV_VARS = (
    "PIH_LLM_BASE_URL", "PIH_LLM_API_KEY",
    "PIH_LLM_SMALL_MODEL", "PIH_LLM_LARGE_MODEL",
)
REAL_LLM = pytest.mark.skipif(
    not all(os.environ.get(v) for v in LLM_ENV_VARS),
    reason="PIH_LLM_* 任一未配置，跳过真实 LLM 集成测试",
)
pytestmark = pytest.mark.integration


def _collect_fresh(n: int = 3) -> None:
    """采集 n 条 ccma 情报作为 process 输入。"""
    code = main(["collect", "ccma", "--max-items", str(n)])
    assert code == 0, "采集失败（前置条件不满足）"


def _run_scripted(chat) -> None:
    """真实库 + 真实 pack + 脚本化 chat 跑一轮 process。"""
    pool = get_pool()
    try:
        runner = ProcessRunner(IntelRepository(pool), load(_default_pack()), chat=chat)
        stats = runner.run(source_id="ccma", limit=10)
        assert stats.failed == 0, f"写库失败：{stats.details}"
    finally:
        close_pool()


@REAL_LLM
class TestAC1RealLLMExtraction:
    def test_extracted_fields_and_admiralty(self, capsys):
        """AC1：真实 LLM 抽取 → 结构化字段非空 + Admiralty 首字符=reliability。"""
        _collect_fresh(3)
        code = main(["process", "--source-id=ccma", "--limit=3"])
        out = capsys.readouterr().out
        assert code == 0, f"process 失败：\n{out}"
        assert "处理 3 条" in out
        assert "token 用量" in out

        rows = _q(
            "SELECT i.subject, i.event_type, i.facts, i.admiralty_code, s.reliability "
            "FROM intel_item i JOIN source s ON s.id = i.source_id "
            "WHERE i.process_status = 'extracted'"
        )
        assert rows, "无 extracted 条目（LLM 全部判无关/待人工，重跑观察）"
        for subject, event_type, facts, admiralty, reliability in rows:
            assert subject and subject.strip()
            assert event_type and event_type.strip()
            assert facts and facts.strip()
            assert admiralty and admiralty[0] == reliability, (
                f"Admiralty 首字符 {admiralty!r} ≠ 来源可靠性 {reliability!r}"
            )


class TestAC2NeedsManualKeepsItem:
    def test_schema_failure_retains_queryable_row(self, capsys):
        """AC2：抽取输出反复未过枚举校验 → needs_manual，条目保留可查。"""
        _collect_fresh(1)

        def large(messages):
            return ok_pred() | {"事件类型": "瞎写"}, usage()

        _run_scripted(ScriptChat(
            small=lambda m: ({"relevant": True}, usage()),
            large=large,
        ))

        rows = _q(
            "SELECT process_status, process_error, subject FROM intel_item WHERE source_id='ccma'"
        )
        assert rows and rows[0][0] == "needs_manual"
        assert "瞎写" in rows[0][1]
        assert rows[0][2] is None  # 未写结构化字段

        code = main(["query", "--source-id=ccma"])
        out = capsys.readouterr().out
        assert code == 0
        assert "needs_manual" in out  # 保留可查（不丢弃）


class TestAC3FilteredOutAuditable:
    def test_irrelevant_item_stays_queryable(self, capsys):
        """AC3：粗筛判无关 → filtered_out，行保留可查（审计口径）。"""
        _collect_fresh(1)
        _run_scripted(ScriptChat(
            small=lambda m: ({"relevant": False}, usage()),
            large=lambda m: (ok_pred(), usage()),  # 不应被调用
        ))

        rows = _q("SELECT process_status, subject FROM intel_item WHERE source_id='ccma'")
        assert rows and rows[0] == ("filtered_out", None)

        code = main(["query", "--source-id=ccma"])
        out = capsys.readouterr().out
        assert code == 0
        assert "filtered_out" in out


class TestAC4GrayItemPolicy:
    def test_prefilter_failure_falls_through_to_extraction(self):
        """AC4：粗筛 API 失败 → 灰条目保留，走抽取节点（不整条丢弃）。"""
        _collect_fresh(1)

        def small(messages):
            raise LLMError("模拟限流")

        _run_scripted(ScriptChat(small=small, large=lambda m: (ok_pred(), usage())))

        rows = _q("SELECT process_status FROM intel_item WHERE source_id='ccma'")
        assert rows and rows[0][0] == "extracted"  # 落灰保留 → 正常抽取


class TestAC7PostHocQualityGate:
    """S1.2.1 AC3：主体占位值 → needs_manual 且结构化字段保留。"""

    def test_placeholder_subject_needs_manual_with_fields_kept(self, capsys):
        _collect_fresh(1)
        _run_scripted(ScriptChat(
            small=lambda m: ({"relevant": True}, usage()),
            large=lambda m: (ok_pred() | {"主体": "未知", "事件类型": "其他"}, usage()),
        ))

        rows = _q(
            "SELECT process_status, subject, event_type, admiralty_code, process_error "
            "FROM intel_item WHERE source_id='ccma'"
        )
        assert rows
        status, subject, event_type, admiralty, error = rows[0]
        assert status == "needs_manual"  # 非 extracted——列表不被低质条目稀释
        assert subject == "未知"  # 字段保留（复核依据）
        assert event_type == "其他"
        assert admiralty == "B2"  # reliability B × 可信度 2 照常拼装
        assert "后验质量门" in error

        code = main(["query", "--source-id=ccma"])
        out = capsys.readouterr().out
        assert code == 0
        assert "needs_manual" in out  # 条目保留可查


@REAL_LLM
class TestAC5StructuredQuery:
    def test_query_by_event_type_recalls(self, capsys):
        """AC5：query --event-type=<实际抽取值> 召回 extracted 条目。"""
        _collect_fresh(3)
        assert main(["process", "--source-id=ccma", "--limit=3"]) == 0

        types = _q(
            "SELECT DISTINCT event_type FROM intel_item "
            "WHERE process_status='extracted' AND event_type IS NOT NULL"
        )
        assert types, "无 extracted 条目可验结构化筛选"
        for (event_type,) in types:
            code = main(["query", "--event-type", event_type])
            out = capsys.readouterr().out
            assert code == 0
            assert "共" in out
            assert "共 0 条" not in out  # 该事件类型至少召回 1 条

        # 无关枚举值不召回
        code = main(["query", "--event-type", "不存在的类型"])
        out = capsys.readouterr().out
        assert code == 0
        assert "（无结果）" in out


@REAL_LLM
class TestAC6IdempotentRerun:
    def test_second_process_handles_zero(self, capsys):
        """AC6：二次 process → 处理 0 条（pending 已清空，幂等）。"""
        _collect_fresh(1)
        assert main(["process", "--source-id=ccma", "--limit=3"]) == 0

        code = main(["process", "--source-id=ccma", "--limit=3"])
        out = capsys.readouterr().out
        assert code == 0
        assert "处理 0 条" in out
        assert "prompt 0" in out  # 无 LLM 调用
