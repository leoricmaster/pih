# TASK-4.02.01 设计：信源健康告警（站内信）

> 关联：backlog TASK-4.02.01 ｜ doc-2 §7 notification 表 / §8 告警与消费同一入口 ｜ 原型 topbar 铃铛 + notif 页。
> 决策同步 `docs/mvp-run-decisions-2026-09-03.md` D10/D11。

## 1. 范围与存量映射

| AC | 存量（实测） | 本故事增量 |
|---|---|---|
| AC1 连续3次失败→未读站内信+信源页标记+他源不受影响 | 4.01.01 交付 consecutive_failures 健康列 + job 失败回写；信源页六字段（无健康列） | **迁移 0004** notification 表；NotificationRepository；run_source_job 增告警钩子（record_failure 返回新计数，恰达 3 触发一次 D10）；Web topbar 铃铛（`<details>` 下拉+未读角标，无 JS）+ `/notifications` 未读/历史页；信源页健康列（读 DB 健康行并示） |
| AC2 标记已读+历史可查 | 无 | POST /notifications/{id}/read → 303 回列表；历史页按 created_at DESC 分组未读/已读 |

范围外：外部渠道（企微/邮件，可配置扩展）；恢复通知（D10 留演进）；假设命中通知类型（TASK-3.01 复用 type 枚举）。

## 2. 关键决策与理由

| # | 决策 | 备选与否决理由 |
|---|---|---|
| D17 | **告警判定在 job 内**：record_failure 改为 RETURNING 新计数；run_source_job 拿到恰 ==3 时调 notify(title, body) 钩子一次 | 独立巡检进程（新组件违 DoD#2）；web 请求时惰性判定（告警延迟到有人看页面，违背「及时告警」） |
| D18 | 铃铛用 **`<details>` 原生下拉**（summary=🔔+未读角标；下拉体=最近 5 条未读+查看全部链接），无 JS 无框架 | 原型是 JS dropdown——原生 details 交互等价、零依赖；axios/htmx 引入超 MVP 需要 |
| D19 | **每页渲染注入 bell 上下文**：web.py 收口 `_render()` 包装 TemplateResponse（统一合并 unread_count/recent） | FastAPI 无 context processor；每路由手写易漏；中间件注入模板上下文不可行（渲染在路由内） |
| D20 | 信源页健康列口径：连续失败 ≥3 → 异常（warn tag，title 显示原因）；1–2 → 失败 N 次；0 且有 last_success → 正常；0 且从未采集 → —（配置存在未运行） | 与告警阈值同口径；「未采集」与「正常」区分（新注册未跑 vs 跑过健康） |

## 3. 接口与状态语义

- 迁移 0004：`notification`（id/type/source_id FK/title/body/read_at NULL/created_at + 未读索引），type 枚举开放（source_health 先行，hypothesis_hit 等留 3.01）。
- `store/notification.py` NotificationRepository：`create(type, source_id, title, body)` / `unread_count()` / `list_unread(limit)` / `list_recent(limit)`（含已读）/ `mark_read(id)`。
- `SourceHealthRepository.record_failure` **返回新 consecutive_failures**（RETURNING）；`list_health() -> dict[source_id, row]`（信源页一次取全）。
- `run_source_job(..., notify: Callable[[str, str], None] | None = None)`：恰达 ALERT_AFTER=3 调 `notify(title, body)` 一次（title=「信源异常：{name} 连续失败 3 次」，body=失败原因）。
- Web：`GET /notifications`、`POST /notifications/{id}/read`；`_render()` 注入 `bell`（unread_count + 最近 5 条）；sources 路由并 DB 健康行 → 模板健康列。

## 4. 测试与 CI

| 层 | 增量 |
|---|---|
| unit | test_notification（SQL 契约：create/未读计数/标记已读）；test_source_health 增 record_failure 返回值断言；test_scheduler 增告警钩子 3 例（恰达 3 触发一次/第 4 次不再触发/成功路径不触发）；test_notifications_page（fake 注入：未读角标+标记已读 303+历史）；test_sources_page 健康列渲染（正常/异常/—） |
| contract | 迁移 0004（表列/索引/downgrade 可逆）+ notifications.html 模板契约 |
| integration | test_notifications_e2e：job 连续失败 3 轮 → notification 行恰 1 条（含信源名与原因）+ 第 4 轮仍 1 条；另一源成功不受影响（AC1 后半）；/notifications 渲染 + 标记已读后未读数归零 |
| live | 收尾演示数据实弹（造一个失败源或以 integration 为准 + 真实通知展示） |

## 5. 事实源偏差与裁决

| 偏差 | 裁决 |
|---|---|
| 原型铃铛下拉为 JS 实现 | D18 原生 details 等价实现（IA 同构：角标/最近未读/查看全部入口） |
| 原型通知样例含假设命中/积压提醒类型 | type 枚举开放但本故事只产 source_health；其他类型随对应故事激活 |

## 6. AC 证据清单

- AC1：integration e2e（3 轮失败→1 条通知含名与原因；他源不受影响）+ unit 告警钩子 3 例 + live 信源页健康列+铃铛
- AC2：unit test_notifications_page（标记已读 303/历史渲染）+ integration 标记后未读归零 + live
