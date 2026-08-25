"""SPK-2 评分：字段级判定与指标汇总。

口径：
- 字段准确率 = KEY_FIELDS(主体/事件类型/事实描述/标签) 中"非跳过"格判定为"正确"的占比。
- 枚举命中率 = 事件类型字段判"正确"的条目占比。
- 事实推断分离合格率 = "推断与判断" 字段为"正确"或"跳过"的条目占比
  （金答案有推断→预测要正确；金答案无推断→跳过视为合格）。
- 重问率 = usage_rows 中 retries>=1 的条目占比（含 schema 补问）。
- 平均耗时ms = elapsed_ms 的均值。
"""
from __future__ import annotations

KEY_FIELDS = ["主体", "事件类型", "事实描述", "标签"]


def _norm(s: str) -> str:
    """归一化：去全部空白并小写，做字段相等比较。"""
    return "".join(str(s).split()).lower()


def score_item(golden: dict, pred: dict) -> dict:
    """逐字段判定：正确/错误/漏抽/跳过。

    - 跳过：金答案该字段为空（无可比对内容）。
    - 漏抽：金答案有内容但预测为空。
    - 正确/错误：归一化后相等/不等。
    标签字段用 Jaccard ≥0.5 判"正确"。
    量化参数字段用"金答案 key 命中率 ≥0.5"判"正确"。
    """
    out: dict[str, str] = {}
    pred = pred or {}
    for f in ["主体", "事件类型", "事实描述", "推断与判断"]:
        g, p = golden.get(f, ""), pred.get(f, "")
        if not g:
            out[f] = "跳过"
        elif not p:
            out[f] = "漏抽"
        else:
            out[f] = "正确" if _norm(g) == _norm(p) else "错误"
    gt, pt = set(golden.get("标签", []) or []), set(pred.get("标签", []) or [])
    if not gt:
        out["标签"] = "跳过" if not pt else "错误"
    else:
        overlap = len(gt & pt) / len(gt | pt) if (gt | pt) else 0
        out["标签"] = "正确" if overlap >= 0.5 else "错误"
    gp = golden.get("量化参数", {}) or {}
    if gp:
        hit = sum(1 for k in gp if k in (pred.get("量化参数", {}) or {}))
        out["量化参数"] = "正确" if hit / len(gp) >= 0.5 else "错误"
    else:
        out["量化参数"] = "跳过"
    return out


def summarize(per_item: list[dict], usage_rows: list[dict]) -> dict:
    """汇总 5 项指标 + token 均值。"""
    total = correct = 0
    for row in per_item:
        for f in KEY_FIELDS:
            if row.get(f) != "跳过":
                total += 1
                correct += row.get(f) == "正确"
    n = len(per_item) if per_item else 0
    sep_ok = sum(1 for r in per_item if r.get("推断与判断") in ("正确", "跳过"))
    usage_cols = ["retries", "prompt_tokens", "completion_tokens", "elapsed_ms"]
    avg = {
        c: (sum(u.get(c, 0) for u in usage_rows) / len(usage_rows) if usage_rows else 0)
        for c in usage_cols
    }
    return {
        "字段准确率": correct / total if total else 0,
        "枚举命中率": sum(1 for r in per_item if r.get("事件类型") == "正确") / n if n else 0,
        "事实推断分离合格率": sep_ok / n if n else 0,
        "重问率": sum(1 for u in usage_rows if u.get("retries", 0) >= 1) / len(usage_rows) if usage_rows else 0,
        "平均耗时ms": avg["elapsed_ms"],
        "平均prompt_tokens": avg["prompt_tokens"],
        "平均completion_tokens": avg["completion_tokens"],
    }
