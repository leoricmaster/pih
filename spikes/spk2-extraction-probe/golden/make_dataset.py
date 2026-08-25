"""把 SPK-1 样本存档转成 samples.json（清洗 HTML、抽 frontmatter）。

用法：.venv/bin/python spk2-extraction-probe/golden/make_dataset.py [samples目录] [输出路径]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DEFAULT_SRC = Path(__file__).resolve().parents[2] / "spk1-source-probe" / "samples"
DEFAULT_OUT = Path(__file__).resolve().parent / "samples.json"

# 事件类型枚举（需求 §4.4；Task 6/7 试抽与评分复用同一常量）
EVENTS: list[str] = [
    "新品发布", "功能迭代", "专利公开", "中标落地",
    "组织人事", "价格变动", "标准动态", "其他",
]

# 来源层级映射（Spike 简版：按信源名人工映射，锁定清单为准）
# 依据 SPK-1 报告 §4 锁定清单（spk1-report.md）：CCMA=L2 行业权威、三一官网=L1 官方一手、
# 铁甲网 cehome=L2 行业权威、第一工程机械网 d1cm=L2 行业权威、KHL=L2 行业权威（观察级）。
# 样本中未出现的锁定清单源（徐工 L1、CNIPA L1、千里马 L4 法务前不启用、lmjx 待复核）不在此列。
LEVEL_BY_SOURCE: dict[str, str] = {
    "ccma": "L2",
    "sany": "L1",
    "cehome": "L2",
    "d1cm": "L2",
    "khl": "L2",
}


def strip_html(raw: str) -> str:
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", raw, flags=re.S)
    if not m:
        return {}, raw
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    records = []
    for i, f in enumerate(sorted(src.glob("*.md")), start=1):
        meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        text = strip_html(body)
        records.append(
            {
                "id": f"S{i:02d}",
                "source": meta.get("source", f.stem),
                "url": meta.get("url", ""),
                "level": LEVEL_BY_SOURCE.get(meta.get("source", ""), "未知"),
                "text": text,
            }
        )
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(records)} 条 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
