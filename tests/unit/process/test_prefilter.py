"""prefilter 独立粗筛单元测试（TASK-1.01.02 D3/D4）。

粗筛从抽取图解耦为独立函数：关键词命中 + 小模型二分类双通道。
- 关键词命中（确定性信号）→ kept=True（领域相关，保留走抽取）
- 关键词不命中 AND 小模型判定不相关 → kept=False（filtered_out）
- 小模型 API 失败 → 按保留处理（架构 §8 不丢弃），kept=True
不耦合大模型配置：关键词通道独立成立，小模型通道由注入 chat 承载。
"""
from __future__ import annotations

from pih.process.prefilter import keyword_hit, prefilter

PACK = {
    "meta": {"domain_id": "test_domain", "display_name": "测试行业", "version": "0.1.0"},
    "keywords": ["挖机", "挖掘机", "无人化"],
}


class TestKeywordHit:
    def test_keyword_present_returns_true(self):
        """正文含监控关键词 → 命中（确定性相关信号）。"""
        assert keyword_hit("三一发布新款挖掘机，配远程操控", PACK) is True

    def test_keyword_absent_returns_false(self):
        """正文不含任何监控关键词 → 未命中。"""
        assert keyword_hit("今日天气晴朗，适合户外散步", PACK) is False

    def test_case_sensitive_exact(self):
        """关键词匹配为子串包含（中文无大小写问题）。"""
        assert keyword_hit("挖机销量增长", PACK) is True
        assert keyword_hit("挖 机械", PACK) is False  # 不连续不命中


class TestPrefilterDualChannel:
    def test_keyword_hit_keeps_regardless_of_llm(self):
        """关键词命中 → kept=True，不调小模型（确定性信号优先，省一次调用）。"""
        calls = []

        def chat(msgs, tier):
            calls.append((msgs, tier))
            return {"relevant": False}, {"prompt_tokens": 0, "completion_tokens": 0, "retries": 0}

        kept, reason = prefilter("三一发布新款挖掘机", PACK, chat=chat)
        assert kept is True
        assert calls == []  # 关键词命中短路，未调小模型
        assert "关键词" in reason

    def test_no_keyword_llm_relevant_keeps(self):
        """关键词未命中 + 小模型判相关 → kept=True。"""

        def chat(msgs, tier):
            return {"relevant": True}, {"prompt_tokens": 10, "completion_tokens": 5, "retries": 0}

        kept, reason = prefilter("某行业论坛讨论新技术趋势", PACK, chat=chat)
        assert kept is True

    def test_no_keyword_llm_irrelevant_filters_out(self):
        """关键词未命中 + 小模型判不相关 → kept=False（filtered_out）。"""

        def chat(msgs, tier):
            return {"relevant": False}, {"prompt_tokens": 10, "completion_tokens": 5, "retries": 0}

        kept, reason = prefilter("今日股市大盘走势分析", PACK, chat=chat)
        assert kept is False
        assert "不相关" in reason or "粗筛" in reason

    def test_no_keyword_llm_failure_keeps(self):
        """关键词未命中 + 小模型 API 失败 → 按保留处理（不丢弃，架构 §8）。"""
        from pih.process.llm import LLMError

        def chat(msgs, tier):
            raise LLMError("api down")

        kept, reason = prefilter("无关正文但小模型不可用", PACK, chat=chat)
        assert kept is True
        assert "保留" in reason or "灰" in reason

    def test_no_chat_keyword_miss_keeps_as_gray(self):
        """无小模型注入（独立粗筛路径，不耦合大模型配置）+ 关键词未命中 → 灰条目保留。

        解耦语义：粗筛可脱离 LLM 配置独立运行；无 chat 时仅关键词通道，
        未命中按灰条目保留（走抽取链由大模型最终判定）。
        """
        kept, reason = prefilter("无关正文无小模型", PACK, chat=None)
        assert kept is True
        assert "灰" in reason or "保留" in reason
