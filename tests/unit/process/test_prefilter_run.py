"""run_prefilter_batch 编排测试：inbox pending → 粗筛 → 标记（TASK-1.01.02 D3）。

粗筛独立编排缝：从 inbox 取 pending 条目，逐条跑 prefilter 双通道，
kept=False 落 filtered_out（mark_status），kept=True 保持 pending（等抽取）。
不耦合大模型配置（小模型 chat 可选注入）。
"""
from __future__ import annotations

from unittest.mock import MagicMock

from pih.process.run import run_prefilter_batch

PACK = {
    "meta": {"domain_id": "d", "display_name": "测试行业", "version": "0.1"},
    "keywords": ["挖掘机", "无人化"],
}


def _inbox_rec(idx: int, text: str, status: str = "pending") -> MagicMock:
    rec = MagicMock()
    rec.id = idx
    rec.raw_html = text
    rec.source_id = "ccma"
    rec.process_status = status
    return rec


class TestRunPrefilterBatch:
    def test_filters_out_irrelevant(self):
        """关键词未命中 + 小模型判否 → mark_status(filtered_out)。"""
        inbox = MagicMock()
        inbox.list_pending.return_value = [_inbox_rec(1, "今日股市大盘走势")]
        inbox.mark_status = MagicMock()

        def chat(msgs, tier):
            return {"relevant": False}, {"prompt_tokens": 1, "completion_tokens": 1, "retries": 0}

        stats = run_prefilter_batch(inbox, PACK, chat=chat, limit=10)
        inbox.mark_status.assert_called_once()
        args = inbox.mark_status.call_args[0]
        assert args[0] == 1
        assert args[1] == "filtered_out"
        assert stats.filtered_out == 1
        assert stats.kept == 0

    def test_keeps_keyword_hit(self):
        """关键词命中 → 保持 pending（不调 mark_status）。"""
        inbox = MagicMock()
        inbox.list_pending.return_value = [_inbox_rec(2, "三一发布新款挖掘机")]
        inbox.mark_status = MagicMock()
        stats = run_prefilter_batch(inbox, PACK, chat=None, limit=10)
        inbox.mark_status.assert_not_called()
        assert stats.kept == 1
        assert stats.filtered_out == 0

    def test_no_chat_keeps_as_gray(self):
        """无小模型 + 关键词未命中 → 灰条目保留（保持 pending）。"""
        inbox = MagicMock()
        inbox.list_pending.return_value = [_inbox_rec(3, "无关正文无关键词")]
        inbox.mark_status = MagicMock()
        stats = run_prefilter_batch(inbox, PACK, chat=None, limit=10)
        inbox.mark_status.assert_not_called()
        assert stats.kept == 1

    def test_mark_failure_does_not_block(self):
        """mark_status 异常不阻断其余条目（容错）。"""
        inbox = MagicMock()
        inbox.list_pending.return_value = [
            _inbox_rec(4, "无关正文"),
            _inbox_rec(5, "挖掘机新品"),
        ]
        inbox.mark_status = MagicMock(side_effect=[RuntimeError("db down"), None])

        def chat(msgs, tier):
            return {"relevant": False}, {"prompt_tokens": 1, "completion_tokens": 1, "retries": 0}

        stats = run_prefilter_batch(inbox, PACK, chat=chat, limit=10)
        # 第一条过滤但 mark 失败计入 failed，第二条关键词命中保持
        assert stats.failed == 1
        assert stats.kept == 1

    def test_source_id_filter_passed(self):
        """source_id 透传 list_pending 限定信源。"""
        inbox = MagicMock()
        inbox.list_pending.return_value = []
        run_prefilter_batch(inbox, PACK, chat=None, source_id="ccma", limit=5)
        inbox.list_pending.assert_called_once_with(source_id="ccma", limit=5)
