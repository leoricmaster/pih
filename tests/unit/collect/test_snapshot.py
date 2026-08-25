"""snapshot 单元测试（T5）——用假 MinIO client，不触真实 MinIO。"""
from __future__ import annotations

import json

import pytest

from pih.collect.rawitem import content_fingerprint
from pih.collect.snapshot import SnapshotMeta, SnapshotStore


class _FakeObject:
    def __init__(self, data: bytes):
        self._data = data


class _FakeMinio:
    """假 minio.Minio：记录 put_object 调用，stat_object 按已存对象返回。"""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.buckets: set[str] = set()

    def bucket_exists(self, name):
        return name in self.buckets

    def make_bucket(self, name):
        self.buckets.add(name)

    def put_object(self, bucket, key, stream, length, content_type=None):
        data = stream.read(length)
        self.objects[f"{bucket}/{key}"] = data

    def stat_object(self, bucket, key):
        full = f"{bucket}/{key}"
        if full not in self.objects:
            raise Exception("NoSuchKey")
        return _FakeObject(self.objects[full])


def _meta(source_id: str, raw: bytes, **overrides) -> SnapshotMeta:
    defaults = {
        "source_id": source_id,
        "url": "http://example.com/a",
        "fetched_at": "2026-08-25T10:00:00+0800",
        "http_status": 200,
        "content_type": "text/html; charset=utf-8",
        "encoding": "utf-8",
        "content_sha1": content_fingerprint(raw),
    }
    defaults.update(overrides)
    return SnapshotMeta(**defaults)


class TestArchive:
    def test_archive_returns_sha1(self):
        store = SnapshotStore(_FakeMinio())
        raw = b"<html>content</html>"
        sha = store.archive("ccma", raw, _meta("ccma", raw))
        assert sha == content_fingerprint(raw)
        assert len(sha) == 40

    def test_archive_stores_html_and_sidecar(self):
        fake = _FakeMinio()
        store = SnapshotStore(fake)
        raw = b"<html>x</html>"
        sha = store.archive("ccma", raw, _meta("ccma", raw))
        assert f"pih-snapshots/snapshots/ccma/{sha}.html" in fake.objects
        assert fake.objects[f"pih-snapshots/snapshots/ccma/{sha}.html"] == raw
        sidecar_key = f"pih-snapshots/snapshots/ccma/{sha}.html.meta.json"
        assert sidecar_key in fake.objects
        sidecar = json.loads(fake.objects[sidecar_key])
        assert sidecar["source_id"] == "ccma"
        assert sidecar["url"] == "http://example.com/a"

    def test_archive_creates_bucket_if_missing(self):
        fake = _FakeMinio()
        store = SnapshotStore(fake)
        store.archive("ccma", b"x", _meta("ccma", b"x"))
        assert "pih-snapshots" in fake.buckets

    def test_archive_rejects_mismatched_sha(self):
        store = SnapshotStore(_FakeMinio())
        raw = b"actual"
        wrong_meta = _meta("ccma", b"different")
        with pytest.raises(ValueError, match="不一致"):
            store.archive("ccma", raw, wrong_meta)

    def test_archive_idempotent_same_content(self):
        """相同内容二次存档：同 key 覆盖，不报错（幂等）。"""
        fake = _FakeMinio()
        store = SnapshotStore(fake)
        raw = b"<html>same</html>"
        sha1 = store.archive("ccma", raw, _meta("ccma", raw))
        sha2 = store.archive("ccma", raw, _meta("ccma", raw))
        assert sha1 == sha2
        # 只有一个 html 对象（同 key 覆盖）
        html_keys = [k for k in fake.objects if k.endswith(".html") and "meta" not in k]
        assert len(html_keys) == 1


class TestExists:
    def test_exists_true_after_archive(self):
        store = SnapshotStore(_FakeMinio())
        raw = b"<html>x</html>"
        sha = store.archive("ccma", raw, _meta("ccma", raw))
        assert store.exists("ccma", sha) is True

    def test_exists_false_for_unknown(self):
        store = SnapshotStore(_FakeMinio())
        assert store.exists("ccma", "0" * 40) is False
