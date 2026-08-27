"""textprep 单元测试：剥标签（golden strip_html 口径）+ 截断。"""
from __future__ import annotations

from pih.process.textprep import MAX_TEXT_CHARS, prepare_text, strip_html


class TestStripHtml:
    def test_plain_text_untouched(self):
        assert strip_html("没有标签的文本") == "没有标签的文本"

    def test_simple_tags_removed(self):
        assert strip_html("<p>三一发布<span>新品</span></p>") == "三一发布 新品"

    def test_script_block_removed_entirely(self):
        raw = "前文<script>var x = 1; alert('注入');</script>后文"
        assert strip_html(raw) == "前文 后文"

    def test_style_block_removed(self):
        raw = "<style>.a { color: red }</style>正文"
        assert strip_html(raw) == "正文"

    def test_nested_and_attrs(self):
        raw = '<div class="x"><a href="http://e">链接文字</a><br/>换行</div>'
        assert strip_html(raw) == "链接文字 换行"

    def test_whitespace_collapsed(self):
        assert strip_html("词一\n\t 词二   词三") == "词一 词二 词三"

    def test_multiline_script_with_flags(self):
        raw = "A<SCRIPT\n type='js'>code()</SCRIPT>B"
        assert strip_html(raw) == "A B"


class TestPrepareText:
    def test_truncates_to_max(self):
        text = "字" * (MAX_TEXT_CHARS + 100)
        assert len(prepare_text(text)) == MAX_TEXT_CHARS

    def test_short_text_untouched(self):
        assert prepare_text("<b>短文本</b>") == "短文本"

    def test_truncate_after_strip(self):
        """先剥标签再截断：标签不计入长度。"""
        raw = "<p>" + "字" * 9000 + "</p>"
        out = prepare_text(raw)
        assert len(out) == MAX_TEXT_CHARS
        assert "<" not in out
