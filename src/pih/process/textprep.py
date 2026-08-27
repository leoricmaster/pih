"""抽取输入文本准备：raw_html → 剥标签纯文本（Sprint 4 规格 §3.2/D2）。

intel_item.raw_html 是解码后正文 HTML（含标签），直接送 LLM 浪费 token
且干扰抽取。三步正则清洗（golden/make_dataset.py strip_html 的工程化迁移，
SPK-1/2 已按此口径清洗样本）：
1. 去 <script>/<style> 整段（含内容）；
2. 去其余标签（保留标签间文本）；
3. 压连续空白为单空格。

不引入 DOM 解析器：清洗口径须与 spike 金答案样本一致，改口径等于换评估基准。
"""
from __future__ import annotations

import re

_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# 抽取输入截断长度（SPK-2/3 实测口径；规格 D2）
MAX_TEXT_CHARS = 6000


def strip_html(raw: str) -> str:
    """剥 HTML 标签为纯文本。"""
    txt = _SCRIPT_STYLE_RE.sub(" ", raw)
    txt = _TAG_RE.sub(" ", txt)
    return _WS_RE.sub(" ", txt).strip()


def prepare_text(raw_html: str, max_chars: int = MAX_TEXT_CHARS) -> str:
    """raw_html → 抽取输入文本：剥标签 + 截断。"""
    text = strip_html(raw_html)
    if len(text) > max_chars:
        return text[:max_chars]
    return text
