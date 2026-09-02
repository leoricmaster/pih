---
id: TASK-4.02.01
title: 信源健康告警（站内信）
status: To Do
assignee: []
created_date: '2026-09-01 09:26'
updated_date: '2026-09-02 09:21'
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
- [ ] #1 AC1: Given 某信源连续 3 次抓取失败 ｜ Then 运营者打开 Web 可见未读站内信（含信源名与失败原因）｜ And 信源页该源标记异常 ｜ And 其他信源采集不受影响
- [ ] #2 AC2: Given 运营者查看站内信 ｜ Then 通知可标记已读，历史通知可查
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 验收面字段与事实源（领域包 schema / 原型 IA / doc-2）逐项核对一致；偏差先修订事实源或记 ADR，不在代码里私自偏移
- [ ] #2 无新增未论证的自部署组件；核心代码不出现行业知识硬编码（违反即返工）
- [ ] #3 AC 全满足，每条有可复现证据（测试名 / 命令 / 截图），实际运行通过——非臆测的「应能通过」推断
- [ ] #4 CI 有增量测试且变绿；覆盖正常路径与关键失败路径
- [ ] #5 无回归（现有测试不破）
- [ ] #6 触碰的架构 / ADR / NFR / 运营手册同步更新，day0 文档改动进正文不留批注
- [ ] #7 结构化日志与运行留痕按 doc-2 §8 落地；迁移 / 配置变更可回滚（1 人可恢复）
- [ ] #8 无密钥硬编码；新增依赖真实、锁版本、无高危 CVE
- [ ] #9 不违反贯穿性约束与 ADR（偏离须先记 ADR）
<!-- DOD:END -->
