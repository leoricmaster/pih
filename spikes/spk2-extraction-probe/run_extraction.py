"""SPK-2 试抽：对金答案集逐条抽取，落 results.json。

提示词版本由 PROMPT_FILE 指定（默认 prompt_v1.txt），便于迭代 v2/v3。
EVENTS 从 make_dataset 导入，确保与金答案枚举一致（11 类）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# HERE = .../spikes/spk2-extraction-probe；parents[0]=spikes（_lib 所在），golden 子目录用于 make_dataset
sys.path.insert(0, str(HERE.parents[0]))
sys.path.insert(0, str(HERE / "golden"))

from _lib.llm import LLMError, chat_json  # noqa: E402
from make_dataset import EVENTS  # noqa: E402  —— 11 类枚举，单一出处

# 标签树（SPK-1 报告锁定清单口径；与 golden.jsonl 实际标签对齐）
TAGS = "无人化作业/远程遥控/3D引导与机控/电动化/智能辅助施工/场景-矿山/场景-港口/场景-市政/核心零部件（电液控制·传感器）"

SCHEMA_KEYS = ["主体", "事件类型", "事实描述", "推断与判断", "标签", "量化参数"]

# 可通过第二位置参数切换提示词文件以迭代（如 prompt_v2.txt）
_arg_prompt = sys.argv[2] if len(sys.argv) > 2 else "prompt_v1.txt"
PROMPT_FILE = (HERE / _arg_prompt) if not Path(_arg_prompt).is_absolute() else Path(_arg_prompt)


def build_prompt(text: str) -> list[dict]:
    system = PROMPT_FILE.read_text(encoding="utf-8")
    system = system.replace("<事件类型>", "/".join(EVENTS)).replace("<标签树>", TAGS)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": text[:6000]},
    ]


def validate(pred: dict) -> bool:
    return isinstance(pred, dict) and all(k in pred for k in SCHEMA_KEYS)


def main() -> int:
    golden = [json.loads(l) for l in (HERE / "golden" / "golden.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    samples = {r["id"]: r for r in json.loads((HERE / "golden" / "samples.json").read_text(encoding="utf-8"))}
    results = []
    for g in golden:
        text = samples[g["id"]]["text"]
        t0 = time.monotonic()
        try:
            pred, usage = chat_json(build_prompt(text))
            if not validate(pred):
                pred, usage2 = chat_json(build_prompt(text) + [{"role": "user", "content": "输出缺字段，严格按 schema 重出 JSON"}])
                usage = {k: usage[k] + usage2[k] for k in usage}
            elapsed = int((time.monotonic() - t0) * 1000)
            results.append({"id": g["id"], "pred": pred, **usage, "elapsed_ms": elapsed})
            print(f"[ok] {g['id']} retries={usage['retries']} {elapsed}ms")
        except LLMError as exc:
            results.append({"id": g["id"], "pred": None, "error": str(exc), "elapsed_ms": int((time.monotonic() - t0) * 1000)})
            print(f"[fail] {g['id']}: {exc}")
        time.sleep(0.3)
    # 输出文件名带提示词版本（便于迭代对比）：results_v1.json / results_v2.json ...
    _ver = PROMPT_FILE.stem  # prompt_v1 -> v1
    out = HERE / f"results_{_ver}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    # 同时写一份 results.json 供下游脚本默认读取
    (HERE / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r.get("pred"))
    print(f"完成 {ok}/{len(results)} -> {out}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
