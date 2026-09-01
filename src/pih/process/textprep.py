"""抽取输入文本准备：raw_html → 剥标签纯文本。

intel_item.raw_html 是解码后正文 HTML（含标签），直接送 LLM 浪费 token
且干扰抽取。三步正则清洗（金答案样本制作脚本 strip_html 的工程化迁移，
样本已按此口径清洗）：
1. 去 <script>/<style> 整段（含内容）；
2. 去其余标签（保留标签间文本）；
3. 压连续空白为单空格。

不引入 DOM 解析器：清洗口径与金答案样本对齐，改口径等于换评估基准。
"""
from __future__ import annotations

import re

_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# 抽取输入截断长度（实测口径：6000 字符）
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
