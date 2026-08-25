"""RawItem 单元测试（T2）。"""
from __future__ import annotations

import pytest

from pih.collect.rawitem import RawItem, content_fingerprint


class TestContentFingerprint:
    def test_sha1_hex_40_chars(self):
        fp = content_fingerprint(b"hello")
        assert len(fp) == 40
        assert all(c in "0123456789abcdef" for c in fp)

    def test_deterministic(self):
        assert content_fingerprint(b"same") == content_fingerprint(b"same")

    def test_different_input_different_fp(self):
        assert content_fingerprint(b"a") != content_fingerprint(b"b")

    def test_known_vector(self):
        # sha1("hello") 的已知值
        assert content_fingerprint(b"hello") == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"


class TestRawItem:
    def _make(self, **overrides):
        defaults = {
            "source_id": "ccma",
            "url": "http://www.cncma.org/article/22709",
            "title": "测试标题",
            "list_url": "http://www.cncma.org/col/hangyxw",
            "fetched_at": "2026-08-25T10:00:00+0800",
            "http_status": 200,
            "content_type": "text/html; charset=utf-8",
            "encoding": "utf-8",
            "raw_html": "<html>...</html>",
            "snapshot_id": "abc123",
            "content_sha1": "abc123",
        }
        defaults.update(overrides)
        return RawItem(**defaults)

    def test_valid_construction(self):
        item = self._make()
        assert item.source_id == "ccma"
        assert item.snapshot_id == item.content_sha1

    def test_frozen(self):
        item = self._make()
        with pytest.raises(AttributeError):  # FrozenInstanceError 属 AttributeError
            item.source_id = "other"  # type: ignore[misc]

    def test_snapshot_id_must_equal_content_sha1(self):
        with pytest.raises(ValueError, match="不一致"):
            self._make(snapshot_id="aaa", content_sha1="bbb")

    def test_fingerprint_drives_both_fields(self):
        """实际用法：content_fingerprint 同时作为 snapshot_id 与 content_sha1。"""
        raw = "<html>真实字节</html>".encode()
        fp = content_fingerprint(raw)
        item = self._make(snapshot_id=fp, content_sha1=fp, raw_html=raw.decode("utf-8"))
        assert item.snapshot_id == fp
