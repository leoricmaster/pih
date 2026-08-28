"""Jinja2 模板契约测试（Sprint 5a）。

验：渲染不抛未定义变量 / 含「待事件模型上线后自动激活」占位 / autoescape 生效。
用 pih.consume.web.templates.env 直接 render（不走 FastAPI）。
"""
from __future__ import annotations

from datetime import datetime

from pih.consume.query_service import IntelFilters
from pih.consume.web import templates
from pih.store.repository import IntelRecord


def _make_record(
    *,
    id: int = 1,
    title: str = "三一发布 SY375 新机型",
    subject: str = "三一",
    event_type: str = "新品发布",
    admiralty_code: str = "B2",
    tags: list | None = None,
    facts: str = (
        "三一重工发布 SY375 履带式挖掘机，主打矿山场景；"
        "设备搭载电动化动力系统，功率 200kW；整机重量 75t。"
    ),
    inferences: str = "三一持续加码大吨位挖掘机市场，对标徐工同类产品。",
    process_status: str = "extracted",
) -> IntelRecord:
    return IntelRecord(
        id=id,
        source_id="sany_news",
        url="https://www.sanygroup.com/news/123",
        title=title,
        list_url="https://www.sanygroup.com/news",
        fetched_at=datetime(2026, 8, 27, 14, 30, 0),
        http_status=200,
        content_type="text/html",
        encoding="utf-8",
        snapshot_id="snap-abc123",
        content_sha1="sha-abc123",
        raw_html="<html><body>...</body></html>",
        event_id=None,
        created_at=datetime(2026, 8, 27, 14, 30, 5),
        subject=subject,
        event_type=event_type,
        facts=facts,
        inferences=inferences,
        tags=tags if tags is not None else ["电动化", "矿山"],
        quant_params={"weight": "75t", "power": "200kW"},
        admiralty_code=admiralty_code,
        process_status=process_status,
        process_error=None,
        process_meta={"node_timings": {"extract": 10.4}},
        processed_at=datetime(2026, 8, 27, 14, 35, 0),
    )


def _render(template_name: str, context: dict) -> str:
    return templates.env.get_template(template_name).render(context)


class TestListRender:
    def test_renders_with_items(self):
        items = [_make_record(id=1), _make_record(id=2, title="徐工 XE470 上市")]
        html = _render(
            "list.html",
            {
                "items": items,
                "filters": IntelFilters(),
                "next_url": None,
                "event_placeholder": "待事件模型上线后自动激活",
            },
        )
        assert "三一发布 SY375" in html
        assert "徐工 XE470" in html
        assert "B2" in html

    def test_renders_empty_message(self):
        html = _render(
            "list.html",
            {
                "items": [],
                "filters": IntelFilters(),
                "next_url": None,
                "event_placeholder": "待事件模型上线后自动激活",
            },
        )
        assert "无结果，建议放宽条件" in html
        assert "下一页" not in html

    def test_renders_next_page_link(self):
        html = _render(
            "list.html",
            {
                "items": [_make_record(id=1)],
                "filters": IntelFilters(),
                "next_url": "/?before=2026-08-27T14%3A30%3A00",
                "event_placeholder": "待事件模型上线后自动激活",
            },
        )
        assert "下一页" in html
        assert 'href="/?before=2026-08-27T14%3A30%3A00"' in html

    def test_contains_event_placeholder(self):
        html = _render(
            "list.html",
            {
                "items": [_make_record()],
                "filters": IntelFilters(),
                "next_url": None,
                "event_placeholder": "待事件模型上线后自动激活",
            },
        )
        assert "待事件模型上线后自动激活" in html

    def test_form_preserves_filter_values(self):
        filters = IntelFilters(subject="三一", event_type="新品发布", admiralty="B2")
        html = _render(
            "list.html",
            {
                "items": [],
                "filters": filters,
                "next_url": None,
                "event_placeholder": "待事件模型上线后自动激活",
            },
        )
        assert 'value="三一"' in html
        assert 'value="新品发布"' in html
        assert 'value="B2"' in html


class TestDetailRender:
    def _feedback_ctx(self) -> dict:
        return {
            "feedbacked": False,
            "pack_subjects": ["三一", "徐工", "三一重工"],
            "pack_event_types": ["新品发布", "财报", "其他"],
        }

    def test_renders_all_sections(self):
        rec = _make_record()
        html = _render(
            "detail.html",
            {
                "rec": rec,
                "snapshot_url": "http://minio.local/snap-abc123?token=x",
                "event_placeholder": "待事件模型上线后自动激活",
                **self._feedback_ctx(),
            },
        )
        assert "基础元信息" in html
        assert "结构化字段" in html
        assert "事实描述" in html
        assert "推断与判断" in html
        assert "原文与快照" in html
        assert "处理状态" in html
        assert "事件核实状态与跃迁历史" in html
        assert rec.url in html
        assert "75t" in html  # quant_params
        # list_url 折叠在「技术详情」详情块里（默认折叠但仍在 HTML）
        assert "技术详情" in html
        assert "采集诊断" not in html
        assert rec.list_url in html
        # 快照 ID / 内容指纹合并为一行「内容指纹」（二者同值）
        assert "快照 ID" not in html
        assert "内容指纹" in html
        # 快照 presigned 入口（链接文本简化为「原文快照」，过期信息挪到 title）
        assert 'href="http://minio.local/snap-abc123?token=x"' in html
        assert "原文快照</a>" in html
        assert "HTML，1小时有效" not in html

    def test_renders_feedback_section(self):
        """Sprint 5b S3.1.3：反馈区四表单 + datalist 主体清单注入。"""
        rec = _make_record()
        html = _render(
            "detail.html",
            {
                "rec": rec,
                "snapshot_url": None,
                "event_placeholder": "x",
                **self._feedback_ctx(),
            },
        )
        assert 'id="feedback"' in html
        for label in ("主体错了", "事件类型错", "事实不准", "不该入库"):
            assert label in html
        # datalist 主体清单选项
        assert '<option value="三一重工">' in html
        # 事件类型 select 选项
        assert '<option value="新品发布">' in html
        # hidden 透传当前错值
        assert 'name="wrong_value" value="三一"' in html
        # 未提交时不显示已记录提示
        assert "反馈已记录" not in html

    def test_feedbacked_flag_shows_notice(self):
        html = _render(
            "detail.html",
            {
                "rec": _make_record(),
                "snapshot_url": None,
                "event_placeholder": "x",
                **(self._feedback_ctx() | {"feedbacked": True}),
            },
        )
        assert "反馈已记录" in html

    def test_facts_split_into_list(self):
        """facts 按 '；' 拆成无序列表（事实间无顺序语义），每条事实一行。"""
        rec = _make_record()
        html = _render(
            "detail.html",
            {"rec": rec, "snapshot_url": None, "event_placeholder": "x", **self._feedback_ctx()},
        )
        # 事实区块用 <ul>（无序），不用 <ol>（避免引入不存在的顺序关系）
        assert "事实描述" in html
        # 三条事实各自独立成项
        assert "三一重工发布 SY375" in html
        assert "设备搭载电动化动力系统" in html
        assert "整机重量 75t" in html

    def test_snapshot_url_none_shows_id_text(self):
        """MinIO 不可达时降级展示快照 ID 文本，不渲染失效链接。"""
        rec = _make_record()
        html = _render(
            "detail.html",
            {"rec": rec, "snapshot_url": None, "event_placeholder": "x", **self._feedback_ctx()},
        )
        assert "MinIO 不可达" in html
        assert rec.snapshot_id in html

    def test_contains_event_placeholder(self):
        html = _render(
            "detail.html",
            {
                "rec": _make_record(),
                "snapshot_url": None,
                "event_placeholder": "待事件模型上线后自动激活",
                **self._feedback_ctx(),
            },
        )
        assert "待事件模型上线后自动激活" in html

    def test_unextracted_record_shows_dash(self):
        rec = _make_record(
            subject=None,
            event_type=None,
            admiralty_code=None,
            tags=[],
            facts="",
            inferences="",
            process_status="pending",
        )
        html = _render(
            "detail.html",
            {"rec": rec, "snapshot_url": None, "event_placeholder": "..."},
        )
        assert "—" in html
        assert "（未抽取）" in html
        assert "（无）" in html
        assert "pending" in html


class TestAutoescape:
    def test_title_script_escaped_in_list(self):
        rec = _make_record(title="<script>alert(1)</script>")
        html = _render(
            "list.html",
            {
                "items": [rec],
                "filters": IntelFilters(),
                "next_url": None,
                "event_placeholder": "x",
            },
        )
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_facts_script_escaped_in_detail(self):
        rec = _make_record(facts="<script>x</script>事实内容")
        html = _render(
            "detail.html",
            {"rec": rec, "snapshot_url": None, "event_placeholder": "x"},
        )
        assert "<script>x</script>" not in html
        assert "&lt;script&gt;" in html
