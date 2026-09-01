---
id: TASK-4.02.01
title: 信源健康告警（站内信）
status: To Do
assignee: []
created_date: '2026-09-01 09:26'
labels:
  - web
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-4.02
type: story
ordinal: 25000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为运营者，某信源抓取连续失败时我在 Web 收到站内信告警、信源页标记异常且不影响其他信源采集，以便保持采集不断流、系统不给我添乱。

验收面：Web 站内通知（未读标记 + 通知列表，含信源名与失败原因）+ 信源页健康标记。外部渠道（企业微信 / 邮件）为可配置扩展渠道，不在本故事范围。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 某信源连续 3 次抓取失败
Then 运营者打开 Web 可见未读站内信（含信源名与失败原因）
And 信源页该源标记异常
And 其他信源采集不受影响
- [ ] #2 AC2: Given 运营者查看站内信
Then 通知可标记已读，历史通知可查
<!-- AC:END -->
