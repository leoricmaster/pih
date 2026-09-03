"""graph 单元测试：注入 fake chat 覆盖全分支（TASK-1.02.01）。

覆盖：粗筛三分支（keep/drop/API 失败按保留）、抽取失败、
validate 首过/补问/耗尽、api_retries 与 validate_rounds 分列（既有契约）、
text 在场契约、占位符注入。
"""
from __future__ import annotations

from pih.process.graph import ItemState, build_graph, render_prompt
from pih.process.llm import LLMError

# ---- 测试用领域包（最小可渲染）----

PACK = {
    "meta": {"domain_id": "test_domain", "display_name": "测试行业", "version": "0.1.0"},
    "event_types": ["新品发布", "财报", "其他"],
    "tag_tree": {"技术特征": ["电动化", "远程遥控"], "应用场景": ["场景-矿山"]},
    "competitors": [
        {"id": "sany", "display_name": "三一", "aliases": ["三一重工", "SANY"]},
        {"id": "xcmg", "display_name": "徐工"},
    ],
    "extraction_prompt": (
        "抽取提示词：枚举 <事件类型>，标签 <标签树>，主体 <主体清单>。"
    ),
}


def _ok_pred() -> dict:
    return {
        "主体": "三一",
        "事件类型": "新品发布",
        "事实描述": "销量 1000 台",
        "推断与判断": "依据：正文销量",
        "标签": ["电动化"],
        "量化参数": {"销量": "1000台"},
        "信息可信度": "2",
    }


def _usage(prompt: int = 100, completion: int = 50, retries: int = 0) -> dict:
    return {"prompt_tokens": prompt, "completion_tokens": completion, "retries": retries}


class FakeChat:
    """按调用序返回脚本化响应；记录每次 (tier, messages)。"""

    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, list[dict]]] = []

    def __call__(self, messages: list[dict], tier: str):
        self.calls.append((tier, messages))
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def _state() -> ItemState:
    return {"intel_id": 42, "text": "三一发布新品挖掘机，销量 1000 台"}


class TestRenderPrompt:
    def test_placeholders_injected(self):
        rendered = render_prompt(PACK)
        assert "<事件类型>" not in rendered
        assert "新品发布/财报/其他" in rendered
        assert "<标签树>" not in rendered
        assert "电动化/远程遥控/场景-矿山" in rendered
        assert "<主体清单>" not in rendered
        assert "三一（别名：三一重工、SANY）" in rendered
        assert "徐工" in rendered and "徐工（别名" not in rendered


class TestHappyPath:
    def test_keep_extract_validate_pass(self):
        fake = FakeChat([
            ({"relevant": True}, _usage(10, 5)),
            (_ok_pred(), _usage(100, 60)),
        ])
        graph = build_graph(PACK, chat=fake)
        final = graph.invoke(_state())
        assert final["kept"] is True
        assert final["extraction"] is not None
        assert final["extraction"].subject == "三一"
        assert final["validate_rounds"] == 0
        assert final["failure"] is None
        assert final["prompt_tokens"] == 110
        assert final["completion_tokens"] == 65
        # 粗筛用 small、抽取用 large
        assert fake.calls[0][0] == "small"
        assert fake.calls[1][0] == "large"

    def test_text_survives_all_nodes(self):
        """既有契约：text 字段全程在场（节点不得删除）。"""
        fake = FakeChat([
            ({"relevant": True}, _usage()),
            (_ok_pred(), _usage()),
        ])
        final = build_graph(PACK, chat=fake).invoke(_state())
        assert final["text"] == "三一发布新品挖掘机，销量 1000 台"


class TestPrefilter:
    def test_drop_skips_extract(self):
        """粗筛判不相关：直接结束，不调大模型。"""
        fake = FakeChat([({"relevant": False}, _usage())])
        final = build_graph(PACK, chat=fake).invoke(_state())
        assert final["kept"] is False
        assert "pred" not in final or final.get("pred") is None
        assert len(fake.calls) == 1

    def test_api_failure_keeps_item(self):
        """AC4：粗筛 API 失败按保留处理，继续抽取不丢弃。"""
        fake = FakeChat([
            LLMError("重试耗尽：429"),
            (_ok_pred(), _usage()),
        ])
        final = build_graph(PACK, chat=fake).invoke(_state())
        assert final["kept"] is True
        assert "prefilter" in final["error"]
        assert final["extraction"] is not None


class TestValidate:
    def _bad_pred(self) -> dict:
        return _ok_pred() | {"事件类型": "融资轮次"}  # 枚举外

    def test_reask_once_then_pass(self):
        fake = FakeChat([
            ({"relevant": True}, _usage()),
            (self._bad_pred(), _usage()),
            (_ok_pred(), _usage()),
        ])
        final = build_graph(PACK, chat=fake).invoke(_state())
        assert final["extraction"] is not None
        assert final["validate_rounds"] == 1
        # 补问消息含失败原因提示
        reask = fake.calls[2][1][-1]["content"]
        assert "schema 校验" in reask
        assert "融资轮次" in reask

    def test_reask_recovers_missing_inference_basis(self):
        """AC1 推断必须含依据：缺依据触发重问，补依据后通过。"""
        fake = FakeChat([
            ({"relevant": True}, _usage()),
            (_ok_pred() | {"推断与判断": "布局无人化作业方向"}, _usage()),
            (_ok_pred(), _usage()),
        ])
        final = build_graph(PACK, chat=fake).invoke(_state())
        assert final["extraction"] is not None
        assert final["validate_rounds"] == 1
        reask = fake.calls[2][1][-1]["content"]
        assert "依据" in reask

    def test_extract_failure_recovered_by_reask(self):
        """extract 节点 API 失败（pred=None）→ validate 首轮补问成功。"""
        fake = FakeChat([
            ({"relevant": True}, _usage()),
            LLMError("重试耗尽：超时"),
            (_ok_pred(), _usage()),
        ])
        final = build_graph(PACK, chat=fake).invoke(_state())
        assert final["extraction"] is not None
        assert final["validate_rounds"] == 1
        assert "extract" in final["error"]

    def test_exhausted_rounds_needs_manual(self):
        """AC2：补问 3 轮仍失败 → extraction=None + failure 原因，不丢弃。"""
        fake = FakeChat([
            ({"relevant": True}, _usage()),
            (self._bad_pred(), _usage()),
            (self._bad_pred(), _usage()),
            (self._bad_pred(), _usage()),
            (self._bad_pred(), _usage()),
        ])
        final = build_graph(PACK, chat=fake).invoke(_state())
        assert final["extraction"] is None
        assert final["validate_rounds"] == 3
        assert "融资轮次" in final["failure"]

    def test_validate_api_failure_breaks_to_manual(self):
        fake = FakeChat([
            ({"relevant": True}, _usage()),
            (self._bad_pred(), _usage()),
            LLMError("重试耗尽：连接断开"),
        ])
        final = build_graph(PACK, chat=fake).invoke(_state())
        assert final["extraction"] is None
        assert "validate" in final["failure"]


class TestRetryCounting:
    def test_api_retries_and_rounds_separated(self):
        """既有契约：API 级重试（api_retries）与补问轮次（validate_rounds）分列。

        场景：extract 带 2 次 API 内部重试成功但输出不合格，
        validate 补问 1 轮（0 API 重试）通过。
        """
        fake = FakeChat([
            ({"relevant": True}, _usage(retries=0)),
            (_ok_pred() | {"事件类型": "瞎写"}, _usage(retries=2)),
            (_ok_pred(), _usage(retries=0)),
        ])
        final = build_graph(PACK, chat=fake).invoke(_state())
        assert final["api_retries"] == 2
        assert final["validate_rounds"] == 1
        assert final["extraction"] is not None

    def test_api_retries_accumulate_across_nodes(self):
        fake = FakeChat([
            ({"relevant": True}, _usage(retries=1)),
            (_ok_pred(), _usage(retries=1)),
        ])
        final = build_graph(PACK, chat=fake).invoke(_state())
        assert final["api_retries"] == 2
        assert final["validate_rounds"] == 0
