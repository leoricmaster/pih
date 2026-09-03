"""Jinja2 模板契约测试（消费层模板 + 事件区渲染）。

验：渲染不抛未定义变量 / 事件区实查渲染 / autoescape 生效。
用 pih.consume.web.templates.env 直接 render（不走 FastAPI）。
"""
from __future__ import annotations

from datetime import datetime

from pih.consume.query_service import IntelFilters
from pih.consume.web import templates
from pih.domainpacks.errors import ValidationIssue
from pih.process.event import STATUS_LABELS, STATUS_ORDER, EventWithLog
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
    event_id: int | None = None,
    event_status: str | None = None,
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
        event_id=event_id,
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
        event_status=event_status,
    )


def _render(template_name: str, context: dict) -> str:
    return templates.env.get_template(template_name).render(context)


def _list_ctx(**extra) -> dict:
    """list.html 渲染所需最小 context（事件状态下拉引入后 status_labels/status_options 必填）。"""
    return {
        "items": [],
        "filters": IntelFilters(),
        "next_url": None,
        "status_labels": STATUS_LABELS,
        "status_options": STATUS_ORDER,
        **extra,
    }


def _detail_ctx(**extra) -> dict:
    """detail.html 渲染所需最小 context（事件区引入后 event_with_log 必填）。"""
    return {
        "rec": _make_record(),
        "snapshot_url": None,
        "event_with_log": EventWithLog(event=None, logs=[]),
        "status_labels": STATUS_LABELS,
        "feedbacked": False,
        "pack_subjects": ["三一", "徐工", "三一重工"],
        "pack_event_types": ["新品发布", "财报", "其他"],
        **extra,
    }


class TestListRender:
    def test_renders_with_items(self):
        items = [_make_record(id=1), _make_record(id=2, title="徐工 XE470 上市")]
        html = _render("list.html", _list_ctx(items=items))
        assert "三一发布 SY375" in html
        assert "徐工 XE470" in html
        assert "B2" in html

    def test_unattached_event_shows_label(self):
        """TASK-2.02.01 AC1：未挂事件条目事件列显示「未挂事件」（非 —）。"""
        html = _render(
            "list.html",
            _list_ctx(items=[_make_record(id=9, event_id=None, event_status=None)]),
        )
        assert "未挂事件" in html


class TestNotificationsRender:
    """TASK-4.02.01：站内信页未读/历史分组 + 标记已读表单。"""

    def test_notifications_page(self):
        row = {
            "id": 3, "type": "source_health", "source_id": "lmjx",
            "title": "信源异常：路面机械网 连续失败 3 次",
            "body": "ConnectError: WAF 拦截", "read_at": None,
            "created_at": datetime(2026, 9, 3, 9, 0),
        }
        read_row = dict(row, id=4, read_at=datetime(2026, 9, 3, 10, 0))
        html = _render(
            "notifications.html",
            {"unread": [row], "history": [row, read_row]},
        )
        assert "未读" in html and "历史" in html
        assert "路面机械网" in html and "WAF 拦截" in html
        assert 'action="/notifications/3/read"' in html
        assert "已读" in html

    def test_bell_dropdown_in_base(self):
        """顶栏铃铛（D18 原生 details 下拉 + 未读角标 + 查看全部入口）。"""
        recent = [{
            "id": 1, "type": "source_health", "source_id": "lmjx",
            "title": "信源异常：X 连续失败 3 次", "body": "r",
            "read_at": None, "created_at": datetime(2026, 9, 3, 9, 0),
        }]
        html = _render(
            "notifications.html",
            {"unread": recent, "history": recent,
             "bell_count": 1, "bell_recent": recent},
        )
        assert "🔔" in html
        assert '<span class="dot">1</span>' in html
        assert "查看全部历史" in html


class TestSourcesHealthColumn:
    """TASK-4.02.01 D20：信源页健康列四态。"""

    def _ctx(self, health_by_id):
        sources = [
            {"id": "ok_src", "name": "正常源", "type": "html", "url": "http://a/",
             "list_url": "http://a/l", "reliability": "B", "level": "L2",
             "fetch_frequency": "daily", "enabled": True},
            {"id": "bad_src", "name": "异常源", "type": "html", "url": "http://b/",
             "list_url": "http://b/l", "reliability": "B", "level": "L2",
             "fetch_frequency": "daily", "enabled": True},
            {"id": "flaky_src", "name": "波动源", "type": "html", "url": "http://c/",
             "list_url": "http://c/l", "reliability": "B", "level": "L2",
             "fetch_frequency": "daily", "enabled": True},
            {"id": "new_src", "name": "新源", "type": "html", "url": "http://d/",
             "list_url": "http://d/l", "reliability": "B", "level": "L2",
             "fetch_frequency": "daily", "enabled": True},
        ]
        return {
            "sources": sources, "issues": [], "error": None,
            "adapter_ready_ids": {"ok_src", "bad_src", "flaky_src", "new_src"},
            "health_by_id": health_by_id,
        }

    def test_health_states_render(self):
        html = _render(
            "sources.html",
            self._ctx({
                "ok_src": {"consecutive_failures": 0,
                           "last_success_at": datetime(2026, 9, 3),
                           "last_failure_reason": None},
                "bad_src": {"consecutive_failures": 3,
                            "last_success_at": None,
                            "last_failure_reason": "ConnectError: WAF"},
                "flaky_src": {"consecutive_failures": 2,
                              "last_success_at": None,
                              "last_failure_reason": None},
            }),
        )
        assert ">正常<" in html
        assert "异常（连续 3 次）" in html
        assert 'title="ConnectError: WAF"' in html  # 原因悬浮可见
        assert "失败 2 次" in html
        # new_src 无健康行 → —
        assert "—" in html


class TestVerifyPageRender:
    """TASK-2.02.02：核实页四区 + 确认/证伪表单契约。"""

    def _ctx(self, **extra) -> dict:
        from pih.store.event_repository import EventRecord

        ev = EventRecord(
            id=5, subject="三一", event_type="新品发布", status="single_source",
            source_count=2, ready_for_manual=True,
            first_seen_at=datetime(2026, 8, 27, 8, 0),
            last_seen_at=datetime(2026, 9, 1, 8, 0),
        )
        return {
            "ready_events": [ev],
            "stale_cards": [],
            "low_conf_items": [],
            "needs_manual_items": [],
            "status_labels": STATUS_LABELS,
            **extra,
        }

    def test_sections_and_actions_render(self):
        html = _render("verify.html", self._ctx())
        for section in ("积压提醒", "已具备升级条件", "低置信度情报", "待人工条目"):
            assert section in html
        assert 'action="/verify/5/confirm"' in html
        assert 'action="/verify/5/refute"' in html
        assert 'name="reason" required' in html
        assert "无积压" in html  # 空积压区提示

    def test_stale_event_card_renders(self):
        from pih.store.event_repository import EventRecord

        stale = EventRecord(
            id=8, subject="徐工", event_type="中标落地", status="pending",
            source_count=1, ready_for_manual=False,
            first_seen_at=datetime(2026, 8, 20, 8, 0),
            last_seen_at=datetime(2026, 8, 20, 8, 0),
        )
        html = _render(
            "verify.html", self._ctx(stale_cards=[{"event": stale, "days": 14}])
        )
        assert "徐工" in html
        assert "滞留 14 天" in html


class TestFilterFormIA:
    """TASK-2.01.01 D2/D3/D4：主行五要素（词表下拉）+ 时间预设 + 更多筛选折叠 + 清空。"""

    def _html(self, **extra) -> str:
        return _render(
            "list.html",
            _list_ctx(
                filter_subjects=["三一", "三一重工", "SANY"],
                filter_event_types=["新品发布", "财报", "其他"],
                filter_tags=["电动化", "矿山"],
                time_range="30d",
                **extra,
            ),
        )

    def test_primary_row_vocab_dropdowns(self):
        html = self._html()
        # 主体 datalist（可输入的▾，候选含别名）
        assert '<datalist id="filter-subjects">' in html
        assert '<option value="三一重工">' in html
        # 事件类型 / 标签 select 候选来自领域包
        assert '<option value="新品发布">' in html
        assert '<option value="电动化">' in html
        # 置信度 ≥ 档选项（A 最优）
        assert '<option value="B">≥ B</option>' in html
        # 时间范围预设（未选项无 selected 后缀，已选项回显）
        assert '<option value="7d">近7天</option>' in html
        assert '<option value="30d" selected>近30天</option>' in html

    def test_more_filters_collapsed_and_reset(self):
        html = self._html()
        assert "更多筛选" in html
        assert "<details" in html
        for label in ("信源", "处理状态", "事件状态"):
            assert label in html
        assert 'name="source_id"' in html
        assert 'name="process_status"' in html
        assert 'name="event_status"' in html
        assert ">清空</a>" in html
        # ISO 手输时间字段撤出表单（预设替代；URL 直参仍受理）
        assert 'name="since"' not in html
        assert 'name="until"' not in html

    def test_renders_empty_message(self):
        html = _render("list.html", _list_ctx())
        assert "无结果，建议放宽条件" in html
        assert "下一页" not in html

    def test_renders_next_page_link(self):
        html = _render(
            "list.html",
            _list_ctx(
                items=[_make_record(id=1)],
                next_url="/?before=2026-08-27T14%3A30%3A00",
            ),
        )
        assert "下一页" in html
        assert 'href="/?before=2026-08-27T14%3A30%3A00"' in html

    def test_event_status_column_renders_label_or_dash(self):
        """事件状态列——挂事件显示中文标签，未挂显示「未挂事件」（TASK-2.02.01 AC1）。"""
        rec_with_event = _make_record(id=1, event_status="single_source")
        rec_no_event = _make_record(id=2, event_status=None)
        html = _render("list.html", _list_ctx(items=[rec_with_event, rec_no_event]))
        assert "单源确认" in html  # status_labels[single_source]
        # 未挂事件的行该列显示「未挂事件」
        assert "未挂事件" in html

    def test_event_status_filter_dropdown_present(self):
        """筛选 form 含事件状态下拉（pending/single_source/confirmed/refuted/expired）。"""
        html = _render("list.html", _list_ctx())
        assert 'name="event_status"' in html
        for label in ("待核实", "单源确认", "多源确认", "已证伪", "已过期"):
            assert label in html

    def test_form_preserves_filter_values(self):
        """筛选回显：主体输入框回值，事件类型/置信度下拉 selected（≥ 档语义 D1）。"""
        filters = IntelFilters(subject="三一", event_type="新品发布", admiralty="B")
        html = _render(
            "list.html",
            _list_ctx(
                filters=filters,
                filter_subjects=["三一"],
                filter_event_types=["新品发布"],
                filter_tags=[],
            ),
        )
        assert 'value="三一"' in html
        assert '<option value="新品发布" selected>' in html
        assert '<option value="B" selected>≥ B</option>' in html


class TestDetailRender:
    def test_renders_all_sections(self):
        rec = _make_record()
        html = _render(
            "detail.html",
            _detail_ctx(
                rec=rec,
                snapshot_url="http://minio.local/snap-abc123?token=x",
            ),
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
        # AC1（TASK-1.02.01）：Admiralty 双维注解（来源可靠性 × 可信度）
        assert "来源可靠性 B × 可信度 2" in html
        assert "技术详情" in html
        assert rec.list_url in html
        assert "快照 ID" not in html
        assert "内容指纹" in html
        assert 'href="http://minio.local/snap-abc123?token=x"' in html
        assert "原文快照</a>" in html
        assert "HTML，1小时有效" not in html

    def test_renders_feedback_section(self):
        """TASK-4.03.01：反馈区四表单 + datalist 主体清单注入。"""
        html = _render("detail.html", _detail_ctx())
        assert 'id="feedback"' in html
        for label in ("主体错了", "事件类型错", "事实不准", "不该入库"):
            assert label in html
        assert '<option value="三一重工">' in html
        assert '<option value="新品发布">' in html
        assert 'name="wrong_value" value="三一"' in html
        assert "反馈已记录" not in html

    def test_feedbacked_flag_shows_notice(self):
        html = _render("detail.html", _detail_ctx(feedbacked=True))
        assert "反馈已记录" in html

    def test_facts_split_into_list(self):
        rec = _make_record()
        html = _render("detail.html", _detail_ctx(rec=rec))
        assert "事实描述" in html
        assert "三一重工发布 SY375" in html
        assert "设备搭载电动化动力系统" in html
        assert "整机重量 75t" in html

    def test_snapshot_url_none_shows_id_text(self):
        rec = _make_record()
        html = _render("detail.html", _detail_ctx(rec=rec))
        assert "MinIO 不可达" in html
        assert rec.snapshot_id in html

    def test_event_section_no_event_shows_hint(self):
        """未挂事件时显示降级提示（空态文案）。"""
        html = _render("detail.html", _detail_ctx())
        assert "未挂事件" in html

    def test_event_section_with_event_renders_status_and_timeline(self):
        """挂事件时渲染状态徽章 + 跃迁历史时间线。"""
        from dataclasses import replace

        from pih.store.event_repository import EventRecord, VerificationLogRecord

        ev = EventRecord(
            id=42, subject="三一", event_type="新品发布",
            status="single_source", source_count=2, ready_for_manual=True,
            first_seen_at=datetime(2026, 8, 27, 10, 0, 0),
            last_seen_at=datetime(2026, 8, 27, 14, 30, 0),
        )
        logs = [
            VerificationLogRecord(
                id=1, event_id=42, from_status=None, to_status="pending",
                operator="system", reason="事件创建",
                created_at=datetime(2026, 8, 27, 10, 0, 0),
            ),
            VerificationLogRecord(
                id=2, event_id=42, from_status="pending", to_status="single_source",
                operator="system", reason="第二独立信源命中",
                created_at=datetime(2026, 8, 27, 14, 30, 0),
            ),
        ]
        rec = replace(_make_record(event_id=42, event_status="single_source"))
        html = _render(
            "detail.html",
            _detail_ctx(
                rec=rec,
                event_with_log=EventWithLog(event=ev, logs=logs),
            ),
        )
        assert "#42" in html
        assert "单源确认" in html  # status label
        assert "独立信源数" in html
        assert "已具备升级条件" in html  # ready_for_manual 提示
        assert "第二独立信源命中" in html  # reason
        assert "operator=system" in html
        assert "事件创建" in html  # 初始 log

    def test_unextracted_record_shows_dash(self):
        rec = _make_record(
            subject=None, event_type=None, admiralty_code=None,
            tags=[], facts="", inferences="", process_status="pending",
        )
        html = _render("detail.html", _detail_ctx(rec=rec))
        assert "—" in html
        assert "（未抽取）" in html
        assert "（无）" in html
        assert "pending" in html


class TestAutoescape:
    def test_title_script_escaped_in_list(self):
        rec = _make_record(title="<script>alert(1)</script>")
        html = _render("list.html", _list_ctx(items=[rec]))
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_facts_script_escaped_in_detail(self):
        rec = _make_record(facts="<script>x</script>事实内容")
        html = _render("detail.html", _detail_ctx(rec=rec))
        assert "<script>x</script>" not in html
        assert "&lt;script&gt;" in html


class TestSourcesPageTemplate:
    """信源页模板契约（TASK-1.01.01 AC2）——字段一一对应、错误态不半截、autoescape。"""

    def _src(self, **over):
        s = {
            "id": "sany", "name": "三一集团", "type": "html",
            "url": "https://www.sanygroup.com/",
            "list_url": "https://www.sanygroup.com/news",
            "reliability": "B", "level": "L1", "fetch_frequency": "daily",
            "enabled": True,
        }
        s.update(over)
        return s

    def _ctx(self, **extra) -> dict:
        """sources.html 渲染最小 context。"""
        ctx = {"sources": [], "issues": [], "error": None}
        ctx.update(extra)
        return ctx

    def test_renders_all_fields_per_source_row(self):
        html = _render("sources.html", self._ctx(sources=[self._src()]))
        # AC2 六字段：名称/类型/层级/可靠性/频率/启用（+id 便于试抓定位）
        # 值用呈现词（doc-4 呈现基线）：网页/每日/启用，非原始枚举
        for expect in ("三一集团", "网页", "L1", "B", "每日", "启用", "sany"):
            assert expect in html

    def test_disabled_source_shows_off(self):
        html = _render("sources.html", self._ctx(sources=[self._src(enabled=False)]))
        assert '<span class="tag muted">停用</span>' in html
        assert '<span class="tag ok">启用</span>' not in html  # 表头 <th>启用</th> 不算

    def test_field_legend_renders(self):
        """R2：字段图例——用户视角的字段含义（doc-4 统一词表呈现基线）。"""
        html = _render("sources.html", self._ctx(sources=[self._src()]))
        for expect in ("字段说明", "看出身", "看表现", "变更监控", "Admiralty"):
            assert expect in html

    def test_adapter_missing_badge_marks_sources_without_adapter(self):
        """R3：适配器接入状态是运行时事实——无适配器的源在清单面标记「未接入」。"""
        ready = self._src()
        missing = self._src(id="x1", name="徐工集团", type="api")
        html = _render(
            "sources.html",
            self._ctx(sources=[ready, missing], adapter_ready_ids={"sany"}),
        )
        assert html.count("未接入") == 1

    def test_probe_button_posts_to_source_probe(self):
        html = _render("sources.html", self._ctx(sources=[self._src()]))
        assert 'action="/sources/sany/probe"' in html
        assert "试抓" in html

    def test_customer_page_has_no_implementation_note(self):
        """验收反馈（2026-09-03）：客户界面不承载实现者术语——页首 YAML/Git 说明撤下。"""
        html = _render("sources.html", self._ctx(sources=[self._src()]))
        assert "配置编辑在仓内" not in html
        assert "版本留痕" not in html
        assert "page-note" not in html

    def test_validation_error_state_lists_issues_without_table(self):
        issue = ValidationIssue(
            path="sources[0].reliability", message="必选字段缺失", line=7
        )
        html = _render("sources.html", self._ctx(sources=None, issues=[issue]))
        assert "sources[0].reliability" in html
        assert "第 7 行" in html
        assert "<table" not in html  # 不半截：错误态不渲染表格

    def test_file_error_state(self):
        html = _render(
            "sources.html", self._ctx(sources=None, error="领域包文件不存在：x.yaml")
        )
        assert "领域包文件不存在" in html
        assert "<table" not in html

    def test_source_name_script_escaped(self):
        html = _render(
            "sources.html",
            self._ctx(sources=[self._src(name="<script>alert(1)</script>")]),
        )
        assert "<script>alert(1)</script>" not in html


class TestSidebarNav:
    """全局侧边栏 IA（原型还原，TASK-1.01.01 验收反馈）——分组导航与禁用态。"""

    def _ctx(self) -> dict:
        return {"sources": [], "issues": [], "error": None}

    def test_sidebar_groups_and_links(self):
        html = _render("sources.html", self._ctx())
        assert 'class="sidebar"' in html
        for group in ("消费区", "运营", "观察面"):
            assert group in html
        assert 'href="/"' in html          # 情报
        assert 'href="/sources"' in html   # 信源
        assert 'href="/feedback"' in html  # 反馈

    def test_unimplemented_entries_disabled(self):
        html = _render("sources.html", self._ctx())
        # 假设/录入/配置/仪表盘 未上线：呈现 IA 但禁用
        assert html.count('navlink disabled') == 4

    def test_active_marker_on_sources(self):
        html = _render("sources.html", self._ctx())
        assert 'class="navlink active" href="/sources"' in html
        assert 'class="navlink" href="/"' in html  # 情报非当前页

    def test_active_marker_on_intel(self):
        html = _render("list.html", _list_ctx())
        assert 'class="navlink active" href="/"' in html
        assert 'class="navlink" href="/sources"' in html
