# TASK-2.02.02 设计：人工核实页

> 关联：backlog TASK-2.02.02 ｜ 原型（无核实页——D5 新设计 IA 并反向更新原型）｜ ADR-002/003。
> 决策同步 `docs/mvp-run-decisions-2026-09-03.md` D5/D6/D7。

## 1. 范围与存量映射

| AC | 存量（实测） | 本故事增量 |
|---|---|---|
| AC1 三类队列+排序 | EventRepository.list_ready_for_manual（队列①）；IntelRepository.list_inbox(status=needs_manual)（队列③雏形）；EventService/CLI confirm/refute | **Web 核实页** `GET /verify`：四区（积压提醒置顶→已具备升级条件事件→低置信度情报→待人工条目）；新增 `list_low_confidence`（队列②，D6 阈值）与 `list_stale_pending`（AC4）；排序「置信度升序+采集时间升序」在路由层以 ranking 权重计算 score 后 Python 排序（队列小、单用户；事件队列按 first_seen_at 升序=滞留最久优先） |
| AC2 确认→多源确认 | EventService.confirm→repo.confirm 写 verification_log（operator/时间/原态/新态）——CLI 已用 | `POST /verify/{event_id}/confirm`（303 回核实页）；详情页已具备升级条件提示改为链接核实页 |
| AC3 证伪→默认隐藏 | repo.refute 必填理由已实现；排序 W_c(refuted)=0 仅沉底 | `POST /verify/{event_id}/refute`（reason 表单必填，空白 400）；**D7：list_by_filter 默认排除所属事件=refuted 的条目**（`e.status IS DISTINCT FROM 'refuted'`），显式 `event_status=refuted` 可查（审计可达，与 filtered_out 显式筛出同构） |
| AC4 7 天积压提醒 | 无 | `list_stale_pending(days=7)`：status=pending 且 first_seen_at < now-7d，按 first_seen_at 升序（滞留时长降序）；核实页顶部提醒区 |

范围外：低置信度阈值领域包化（D6 留演进）；时间线 sys/human 样式（TASK-6）；恢复通知（D10 留演进）。

## 2. 关键决策与理由（D5/D6/D7 见决策日志，此处记实现向）

| # | 决策 | 备选与否决理由 |
|---|---|---|
| D8 | 队列排序在**路由层 Python 计算**（score=map(admiralty) 以 ranking 权重，升序=低置信优先；fetched_at 升序破同分） | 三队列均小列表（单用户系统）；SQL 侧注入反向 CASE 排序复杂化 list_by_filter（它承载检索视图），两处语义分立更清晰 |
| D9 | 核实页操作用**独立 POST 路由**（confirm/refute），303 回 /verify——与 /inbox replay 同模式（信任域内网，无 CSRF token，ADR-006 内网默认开放口径） | 复用 CLI 子进程（慢、错误面差）；API 化再页面调（过度分层） |
| D10 | refute 理由空白 → 400 带提示页（表单 required 为第一道，服务端校验兜底，EventService.refute ValueError 不上 500） | 422（FastAPI 缺字段语义）不适合「填了空白」场景 |

## 3. 接口与状态语义

- `IntelRepository.list_low_confidence(limit)`：`process_status='extracted'` 且 `SUBSTRING(admiralty_code,2,1) IN ('4','5','6') OR LEFT(admiralty_code,1) IN ('D','E','F')`（D6 并集），fetched_at DESC 取回由路由排序。
- `EventRepository.list_stale_pending(days, limit)`：`status='pending' AND first_seen_at < now()-days`，first_seen_at ASC。
- `list_by_filter`：event_status 未显式给定时追加 `AND (e.status IS NULL OR e.status <> 'refuted')`（D7）。
- 路由：`GET /verify`、`POST /verify/{event_id}/confirm`、`POST /verify/{event_id}/refute`（Form: reason 必填）。

## 4. 测试与 CI

| 层 | 增量 |
|---|---|
| unit | test_repository：D7 默认排除子句 + 显式覆盖；list_low_confidence/list_stale_pending SQL（_MockConn）。新增 test_verify_page：四区渲染（fake repo/svc）、confirm 303+service 调用、refute 空白 400/有理由 303、未知 id 404 |
| contract | verify.html 渲染契约（四区标题 + 确认/证伪表单 + 积压区） |
| integration | 新增 test_verify_page.py：seed_event/seed_intel 全流程——ready 事件确认→confirmed+log（operator/原态/新态）；证伪→refuted+理由入 log+检索默认隐藏+显式可查；stale pending 事件进积压区且按滞留排序；needs_manual 条目列出 |
| live | 收尾演示数据实弹（confirm/refute 各一） |

## 5. 事实源偏差与裁决

| 偏差 | 裁决 |
|---|---|
| 原型无核实页（「随核实层未来呈现」） | D5：新设计 IA（侧栏运营组「核实」+四区布局），**原型反向更新**（R2 先例闭环），明日评审重点项 |

## 6. AC 证据清单

- AC1：integration test_verify_page 队列区+排序断言 + contract verify.html + live
- AC2：integration confirm 用例（log 行 operator/from/to 断言）+ unit 303
- AC3：integration refute 用例（理由入 log+默认隐藏+显式可达）+ unit test_repository D7
- AC4：integration stale 用例（7 天前事件进提醒区、按滞留排序）
