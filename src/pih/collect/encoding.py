"""HTML 正文解码链（架构 §4 采集层 / SPK-1 §3.1.2 解码契约）。

HTTP 正文解码三级链路，修两处 Minor：
1. meta charset 扫描窗口 2048→4096（深埋 meta 不再漏）；
2. 增加 HTML 实体解码（&amp; &#xx; 等，SPK-1 Minor「HTML 实体未解码」）。

链路：HTTP 头 charset → HTML meta charset → utf-8/gbk 严格试探 → utf-8/replace。
关键修正：cehome 非 GBK，是 HTTP 头缺 charset 导致默认 ISO-8859-1
mojibake；本链路正确落到 utf-8，不为任何源硬编码编码。
"""
from __future__ import annotations

import html
import re

# requests/httpx 无 charset 头时默认 ISO-8859-1，不可信，须跳过
_UNRELIABLE_DEFAULTS = {"iso-8859-1", "ascii", "latin-1"}
# meta charset 扫描窗口（深埋 meta 会漏，扩到 4096）
_META_SCAN_WINDOW = 4096
_META_CHARSET_RE = re.compile(rb'charset\s*=\s*["\']?([\w-]+)', re.IGNORECASE)


def _charset_from_header(content_type: str) -> str | None:
    """从 Content-Type 头解析 charset；不可信的默认值返回 None。"""
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("charset="):
            cs = part.split("=", 1)[1].strip('" ').lower()
            return None if cs in _UNRELIABLE_DEFAULTS else cs
    return None


def _charset_from_meta(raw_bytes: bytes) -> str | None:
    """从 HTML 前 4096 字节扫 meta charset；不可信默认值返回 None。"""
    m = _META_CHARSET_RE.search(raw_bytes[:_META_SCAN_WINDOW])
    if not m:
        return None
    cs = m.group(1).decode("ascii", "ignore").lower()
    return None if cs in _UNRELIABLE_DEFAULTS else cs


def _trial_decode(raw_bytes: bytes) -> str:
    """头与 meta 都无可用 charset 时，用严格解码试探 utf-8 → gbk。"""
    for cand in ("utf-8", "gbk"):
        try:
            return raw_bytes.decode(cand)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def decode_body(raw_bytes: bytes, content_type: str = "") -> tuple[str, str]:
    """解码 HTTP 响应正文，返回 (decoded_text, encoding_used)。

    Args:
        raw_bytes: 响应原始字节
        content_type: Content-Type 响应头（可为空）
    Returns:
        (解码后文本, 判定使用的字符集名)
    """
    charset = _charset_from_header(content_type)
    if charset is None:
        charset = _charset_from_meta(raw_bytes)
    if charset is None:
        text = _trial_decode(raw_bytes)
        return text, "utf-8"  # trial 最终兜底 utf-8
    try:
        return raw_bytes.decode(charset, errors="replace"), charset
    except LookupError:
        return raw_bytes.decode("utf-8", errors="replace"), "utf-8"


def decode_entities(text: str) -> str:
    """解码 HTML 实体（&amp; &#xx; &nbsp; 等）。

    SPK-1 Minor「HTML 实体未解码」落地。
    """
    return html.unescape(text)


def decode_full(raw_bytes: bytes, content_type: str = "") -> tuple[str, str]:
    """完整解码：解码链 + 实体解码。适配器常用入口。

    Returns:
        (解码+去实体后文本, 判定字符集)
    """
    text, encoding = decode_body(raw_bytes, content_type)
    return decode_entities(text), encoding
