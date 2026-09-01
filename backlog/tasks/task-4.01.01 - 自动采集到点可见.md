---
id: TASK-4.01.01
title: 自动采集到点可见
status: To Do
assignee: []
created_date: '2026-09-01 09:26'
labels:
  - web
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-4.01
type: story
ordinal: 24000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为消费者，注册信源按其频率自动更新，我什么都不做——到点打开 Web 列表就出现新情报（带采集时间戳），以便真正省去盯源与手动触发的机械工作。

验收面：Web 列表到点自动出现新条目（无需任何人运行命令）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 信源配置频率为每日且已启用
When 调度时间到达
Then 系统自动抓取新内容并生成原文快照
And 新条目出现在 Web 列表（采集入库故事的全部 AC 对调度触发同样成立）
And 无快照的内容不进入后续流水线
- [ ] #2 AC2: Given 抓取失败（网络 / 反爬）
Then 按指数退避重试 3 次，仍失败计入信源健康统计（触发信源健康告警）
<!-- AC:END -->
