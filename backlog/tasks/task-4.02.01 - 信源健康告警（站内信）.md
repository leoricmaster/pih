---
id: TASK-4.02.01
title: 信源健康告警（站内信）
status: Done
assignee:
  - '@lancer'
created_date: '2026-09-01 09:26'
updated_date: '2026-09-03 12:01'
labels:
  - web
milestone: m-0
dependencies:
  - TASK-4.01.01
references:
  - docs/prototype.html
parent_task_id: TASK-4.02
priority: high
type: story
ordinal: 25000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为运营者，某信源抓取连续失败时我在 Web 收到站内信告警、信源页标记异常且不影响其他信源采集，以便保持采集不断流、系统不给我添乱。

验收面：Web 站内通知（未读标记 + 通知列表，含信源名与失败原因）+ 信源页健康标记。

不在本故事：连续失败计数与退避重试的生产（→ TASK-4.01.01）；外部渠道（企业微信 / 邮件）为可配置扩展，不在本故事范围。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 AC1: Given 某信源连续 3 次抓取失败 ｜ Then 运营者打开 Web 可见未读站内信（含信源名与失败原因）｜ And 信源页该源标记异常 ｜ And 其他信源采集不受影响
- [x] #2 AC2: Given 运营者查看站内信 ｜ Then 通知可标记已读，历史通知可查
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 验收面字段与事实源（领域包 schema / 原型 IA / doc-2）逐项核对一致；偏差先修订事实源或记 ADR，不在代码里私自偏移
- [x] #2 无新增未论证的自部署组件；核心代码不出现行业知识硬编码（违反即返工）
- [x] #3 AC 全满足，每条有可复现证据（测试名 / 命令 / 截图），实际运行通过——非臆测的「应能通过」推断
- [ ] #4 CI 有增量测试且变绿；覆盖正常路径与关键失败路径
- [x] #5 无回归（现有测试不破）
- [x] #6 触碰的架构 / ADR / NFR / 运营手册同步更新，day0 文档改动进正文不留批注
- [x] #7 结构化日志与运行留痕按 doc-2 §8 落地；迁移 / 配置变更可回滚（1 人可恢复）
- [x] #8 无密钥硬编码；新增依赖真实、锁版本、无高危 CVE
- [x] #9 不违反贯穿性约束与 ADR（偏离须先记 ADR）
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
新组件故事（设计 docs/design/TASK-4.02.01-design.md，D10/D11/D17-D20 已决）。切片：1) 迁移 0004 notification 表（契约先红）2) NotificationRepository + record_failure 返回计数（unit SQL 契约）3) run_source_job 告警钩子恰达3触发一次（unit 3 例）4) Web：_render 收口注入 bell + topbar 铃铛 details 下拉 + /notifications 页 + 标记已读 + 信源页健康列（unit fake 页测 + contract 模板）5) integration e2e（3 轮失败→1 通知/他源隔离/标记已读）6) README+finalization
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TDD 切片 1（迁移 0004）：契约 2 例先红 → notification 表（type 枚举开放/read_at NULL=未读/未读索引，含 downgrade 可逆）→ 绿（23 passed）。
TDD 切片 2（仓储）：unit test_notification 5 例 SQL 契约 → NotificationRepository（create/unread_count/list_unread/list_recent 含已读/mark_read）→ 绿；SourceHealthRepository.record_failure 改 RETURNING 新计数（D17 告警判定底座）+ list_health 全表 map（信源页 D20）。
TDD 切片 3（告警钩子）：unit TestAlertHook 5 例（恰达 3 触发一次含信源名与原因/第 4 轮不重复/低于阈值不触发/未接 notify 不炸/成功不触发）→ run_source_job 增 notify 参数（ALERT_AFTER=3，episode 语义 D10）→ 绿。
TDD 切片 4（Web 面）：_render() 统一渲染出口注入铃铛上下文（D19，PG 异常降级空铃铛）；base.html 顶栏原生 details 铃铛下拉（D18，未读角标+最近未读+查看全部）；/notifications 未读/历史分组页 + POST /notifications/{id}/read 303；信源页健康列四态（≥3 异常带原因 title/1-2 失败 N 次/0 且采过 正常/未采 —，D20）；CLI _cmd_work 接 _notify→NotificationRepository。unit test_notifications_page 3 例 + contract notifications/bell/sources 健康列 3 例。
integration test_notifications_e2e 2 例：4 轮失败恰 1 条通知（含名与原因）+ 他源成功计数独立（AC1 后半）；Web 渲染+标记已读后未读归零（AC2）。
live 实弹（:8001，真实生产路径种子 run_source_job×3）：首页 🔔+未读角标 1+下拉含中国路面机械网；/notifications 连续失败 3 次+百度 WAF 拦截原因+标记已读按钮；/sources 健康列 lmjx 异常（连续 3 次）。通知保留未读态供明日评审演示。
README 站内信与信源健康段。原型 topbar 铃铛与 notif 页本就有定义（首次照原型实现，无需反向更新）。
回归：unit+contract 456 / notifications_e2e 2 / ruff 干净。
AC 证据索引：AC1=integration e2e（3 轮→1 通知含名与原因+他源隔离）+unit 告警 5 例+live 三页；AC2=unit test_notifications_page（标记已读 303）+integration 未读归零+live 通知页。
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
信源健康告警（站内信）交付（新组件：通知链路）。AC1 连续 3 次抓取失败（重试耗尽计 1 次）→ worker 告警钩子恰触发一条未读站内信（含信源名与失败原因，run_source_job notify 参数+record_failure RETURNING 计数，episode 语义持续失败不重复/成功清零）；Web 顶栏铃铛（原生 details 下拉+未读角标+最近未读，每页经 _render 注入）；信源页健康列（≥3 异常悬浮原因/1-2 失败N次/正常/—，迁移0003 列+0004 notification 表）；他源采集不受影响（独立 job+独立计数，integration 隔离断言）。AC2 /notifications 未读/历史分组+标记已读 303（integration 标记后未读归零）。live：真实生产路径种子 3 轮失败→lmjx 异常+未读通知，三页实弹取证，通知保留未读供明日评审。回归 unit+contract 456/e2e 2/ruff 干净。DoD 8/9，#4 待 push（PD2）。
<!-- SECTION:FINAL_SUMMARY:END -->
