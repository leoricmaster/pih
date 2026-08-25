"""SPK-2 评分单元测试。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import evaluate  # noqa: E402


def test_score_item_correct_partial_missing():
    golden = {"id": "S01", "主体": "三一 SY375", "事件类型": "新品发布", "事实描述": "x", "标签": ["远程遥控"], "推断与判断": "依据：y", "量化参数": {}}
    pred = {"主体": "三一 SY375", "事件类型": "功能迭代", "事实描述": "x", "标签": ["远程遥控"], "推断与判断": "", "量化参数": {}}
    s = evaluate.score_item(golden, pred)
    assert s["主体"] == "正确"
    assert s["事件类型"] == "错误"
    assert s["推断与判断"] == "漏抽"   # 金答案有推断而预测留空


def test_summarize_metrics():
    per = [
        {"主体": "正确", "事件类型": "正确", "事实描述": "正确", "标签": "正确", "推断与判断": "正确"},
        {"主体": "错误", "事件类型": "错误", "事实描述": "正确", "标签": "漏抽", "推断与判断": "正确"},
    ]
    usage = [
        {"retries": 0, "prompt_tokens": 100, "completion_tokens": 50, "elapsed_ms": 1000},
        {"retries": 2, "prompt_tokens": 150, "completion_tokens": 60, "elapsed_ms": 1500},
    ]
    m = evaluate.summarize(per, usage)
    # 字段准确率口径：KEY_FIELDS(主体/事件类型/事实描述/标签) 中非"跳过"的判定，
    # 本例 8 格中 5 格"正确"（行1×4 + 行2 事实描述）→ 5/8 = 0.625
    assert m["字段准确率"] == 0.625
    assert m["枚举命中率"] == 0.5       # 2 条中 1 条事件类型正确
    assert m["重问率"] == 0.5           # 1/2 条 retries>=1（含 schema 补问）
    assert m["平均耗时ms"] == 1250
