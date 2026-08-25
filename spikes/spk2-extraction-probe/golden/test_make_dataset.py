import json
from pathlib import Path

HERE = Path(__file__).parent
SAMPLES_MD = HERE.parent.parent / "spk1-source-probe" / "samples"


def _make(tmp_path, monkeypatch, content: str) -> Path:
    src = tmp_path / "tiejia-00.md"
    src.write_text(content, encoding="utf-8")
    out = tmp_path / "samples.json"
    monkeypatch.setattr("sys.argv", ["make_dataset.py", str(tmp_path), str(out)])
    import golden.make_dataset as m
    import importlib
    importlib.reload(m)
    m.main()
    return out


def test_extracts_frontmatter_and_body(tmp_path, monkeypatch):
    content = (
        "---\nsource: tiejia\nurl: https://example.com/a\n"
        "fetched_at: 2026-08-25T10:00:00+0800\nhttp_status: 200\n---\n\n"
        "<html><body>三一发布无人挖掘机</body></html>"
    )
    out = _make(tmp_path, monkeypatch, content)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["id"] == "S01"
    assert data[0]["source"] == "tiejia"
    assert data[0]["url"] == "https://example.com/a"
    assert "无人挖掘机" in data[0]["text"]


def test_strips_html_tags(tmp_path, monkeypatch):
    content = (
        "---\nsource: x\nurl: https://e.com/b\nfetched_at: t\nhttp_status: 200\n---\n\n"
        "<p>遥控挖掘机</p><script>ignore()</script>"
    )
    out = _make(tmp_path, monkeypatch, content)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "遥控挖掘机" in data[0]["text"]
    assert "ignore" not in data[0]["text"]
