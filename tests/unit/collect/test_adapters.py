"""三源适配器单元测试（T6 / AC5）——用 HTML 夹具验解析钩子，不触网络。

覆盖：列表页详情链接提取（各源正则）、详情页标题提取、CCMA 软 200 存在性判定。
"""
from __future__ import annotations

from pathlib import Path

from pih.collect.adapters.ccma import CcmaAdapter
from pih.collect.adapters.cehome import CehomeAdapter
from pih.collect.adapters.sany import SanyAdapter

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "html"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---- CCMA ----


class TestCcmaAdapter:
    def setup_method(self):
        self.adapter = CcmaAdapter(http=None, snapshots=None)  # type: ignore[arg-type]

    def test_extract_detail_urls_from_list(self):
        urls = self.adapter.extract_detail_urls(_read("ccma_list.html"), "http://www.cncma.org/col/hangyxw")
        assert len(urls) == 3
        assert all("/article/" in u for u in urls)
        assert "http://www.cncma.org/article/22709" in urls

    def test_excludes_non_article_links(self):
        urls = self.adapter.extract_detail_urls(_read("ccma_list.html"), "http://www.cncma.org/col/hangyxw")
        # /about 与 /col/hangyxw?pageIndex=2 不应出现
        assert not any("/about" in u for u in urls)
        assert not any("pageIndex" in u for u in urls)

    def test_extract_title_from_detail(self):
        title = self.adapter.extract_title(_read("ccma_detail.html"))
        assert "工程机械产品进出口" in title

    def test_is_valid_page_true_for_real_detail(self):
        assert self.adapter.is_valid_page(_read("ccma_detail.html")) is True

    def test_is_valid_page_false_for_soft200_template(self):
        """CCMA 软 200：模板页无 /article/\d+ 自链接 → 判无效。"""
        template = "<html><head><title>中国工程机械工业协会</title></head><body>导航</body></html>"
        assert self.adapter.is_valid_page(template) is False


# ---- 三一 ----


class TestSanyAdapter:
    def setup_method(self):
        self.adapter = SanyAdapter(http=None, snapshots=None)  # type: ignore[arg-type]

    def test_extract_detail_urls_from_list(self):
        urls = self.adapter.extract_detail_urls(_read("sany_list.html"), "https://www.sanygroup.com/news")
        assert len(urls) == 3
        assert all(u.endswith(".html") and "/news/" in u for u in urls)
        assert "https://www.sanygroup.com/news/16476.html" in urls

    def test_excludes_product_links(self):
        """spike 误抓 /product/ 的教训：产品链接须排除。"""
        urls = self.adapter.extract_detail_urls(_read("sany_list.html"), "https://www.sanygroup.com/news")
        assert not any("/product/" in u for u in urls)

    def test_extract_title_strips_feff(self):
        """subagent 发现：sany <title> 含 stray U+FEFF，须 strip。"""
        title = self.adapter.extract_title(_read("sany_detail.html"))
        assert not title.startswith("﻿")
        assert "三一" in title


# ---- cehome ----


class TestCehomeAdapter:
    def setup_method(self):
        self.adapter = CehomeAdapter(http=None, snapshots=None)  # type: ignore[arg-type]

    def test_extract_detail_urls_from_list(self):
        urls = self.adapter.extract_detail_urls(_read("cehome_list.html"), "https://www.cehome.com/news/hangye/")
        assert len(urls) == 3
        assert all(".shtml" in u for u in urls)
        assert "https://www.cehome.com/news/20260825/390912.shtml" in urls

    def test_excludes_non_news_links(self):
        urls = self.adapter.extract_detail_urls(_read("cehome_list.html"), "https://www.cehome.com/news/hangye/")
        assert not any("/about/" in u for u in urls)
        assert not any("/hangye/" in u and ".shtml" not in u for u in urls)

    def test_extract_title_from_detail(self):
        title = self.adapter.extract_title(_read("cehome_detail.html"))
        assert "铁甲" in title or "驾驶室" in title


# ---- 注册表 ----


class TestRegistry:
    def test_get_adapter_by_source_id(self):
        # 触发子模块导入以完成注册
        import pih.collect.adapters.ccma  # noqa: F401
        import pih.collect.adapters.cehome  # noqa: F401
        import pih.collect.adapters.sany  # noqa: F401
        from pih.collect.base import SourceConfig, get_adapter

        for sid, cls in [("ccma", CcmaAdapter), ("sany", SanyAdapter), ("cehome", CehomeAdapter)]:
            src = SourceConfig(
                id=sid, name="测试", type="html", url="http://x",
                list_url="http://x", reliability="B", level="L2",
            )
            adapter = get_adapter(src, http=None, snapshots=None)  # type: ignore[arg-type]
            assert isinstance(adapter, cls)
