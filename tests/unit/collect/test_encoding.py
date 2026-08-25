"""encoding 解码链单元测试（T3）。

覆盖 AC3：cehome 无 header charset → 解码链落到 utf-8（非 mojibake）+ 实体解码。
"""
from __future__ import annotations

from pih.collect.encoding import decode_body, decode_entities, decode_full


class TestDecodeBody:
    def test_header_charset_preferred(self):
        raw = "你好".encode()
        text, enc = decode_body(raw, "text/html; charset=utf-8")
        assert enc == "utf-8"
        assert text == "你好"

    def test_unreliable_header_charset_falls_to_meta(self):
        """HTTP 头声明 iso-8859-1（httpx 默认）时不可信，走 meta。"""
        raw = '<meta charset="utf-8"/>你好'.encode()
        text, enc = decode_body(raw, "text/html; charset=iso-8859-1")
        assert enc == "utf-8"
        assert "你好" in text

    def test_no_header_falls_to_meta(self):
        raw = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>正文'.encode()
        text, enc = decode_body(raw, "")
        assert enc == "utf-8"
        assert "正文" in text

    def test_cehome_scenario_lands_utf8_not_mojibake(self):
        """AC3 核心用例：cehome HTTP 头无 charset → 解码链落到 utf-8，标题可读。

        复现 SPK-1 发现：httpx/requests 无 charset 头默认 ISO-8859-1 → mojibake。
        本链路应正确落到 utf-8。
        """
        title = "三一挖掘机新品发布"
        meta = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>'
        raw = f"<html><head>{meta}</head><body><title>{title}</title></body></html>".encode()
        # 模拟 cehome：Content-Type 头无 charset
        text, enc = decode_body(raw, "text/html")
        assert enc == "utf-8"
        assert title in text
        # 确认不是 mojibake（mojibake 不会含可读中文）
        assert "三一" in text

    def test_deep_meta_within_4096_window(self):
        """meta charset 在 2048 之后、4096 之前应被捕获（spike 2048 窗口的修复）。"""
        padding = b"x" * 3000  # 超过旧 2048 窗口
        raw = padding + b'<meta charset="utf-8"/>' + "测试".encode()
        text, enc = decode_body(raw, "")
        assert enc == "utf-8"
        assert "测试" in text

    def test_gbk_page_trial_decode(self):
        """无 header 无 meta 时，gbk 页应被严格试探正确解码。"""
        raw = "中文内容".encode("gbk")
        text, enc = decode_body(raw, "")
        # trial 先试 utf-8 会失败（gbk 字节非合法 utf-8），再试 gbk 成功
        assert "中文内容" in text

    def test_unknown_charset_falls_back_utf8(self):
        raw = b"abc"
        text, enc = decode_body(raw, "text/html; charset=unknown-encoding")
        assert enc == "utf-8"
        assert text == "abc"


class TestDecodeEntities:
    def test_named_entities(self):
        assert decode_entities("a &amp; b &lt; c &gt; d &nbsp;") == "a & b < c > d \xa0"

    def test_numeric_entities(self):
        assert decode_entities("&#65; &#x4e2d;") == "A 中"

    def test_no_entities_unchanged(self):
        assert decode_entities("普通文本") == "普通文本"

    def test_mixed(self):
        assert decode_entities("三一&amp;徐工 &#x5168;") == "三一&徐工 全"


class TestDecodeFull:
    def test_decode_chain_plus_entities(self):
        """AC3：解码链 + 实体解码组合。"""
        title = "三一&amp;徐工"
        raw = f'<meta charset="utf-8"/><title>{title}</title>'.encode()
        text, enc = decode_full(raw, "text/html")
        assert enc == "utf-8"
        assert "三一&徐工" in text
        assert "&amp;" not in text  # 实体已解码

    def test_cehome_full_scenario(self):
        """cehome 端到端：无 header charset + utf-8 字节 + 实体。"""
        body = "工程机械进出口&amp;贸易额"
        raw = f'<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>{body}'.encode()
        text, enc = decode_full(raw, "text/html")
        assert enc == "utf-8"
        assert "工程机械进出口&贸易额" in text
