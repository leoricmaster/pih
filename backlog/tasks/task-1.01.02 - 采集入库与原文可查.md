---
id: TASK-1.01.02
title: 采集入库与原文可查
status: To Do
assignee: []
created_date: '2026-09-01 09:25'
labels:
  - web
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-1.01
type: story
ordinal: 16000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为消费者，运营者执行采集后新条目出现在 Web 列表、点开可见原文快照与原始链接，重复采集不产生重复条目、无关内容不混入，以便我不用搬运转录、原文永远找得回。

验收面：Web 列表/详情（+ 采集统计 CLI 报告）。去重、粗筛、先落盘可重放并入本故事 AC 与 NFR（doc-003），不独立成卡。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 某已启用信源
When 运营者执行采集
Then 新内容抓取入库，输出统计「入库 N 新增 / M 幂等跳过 / K 失败」
And 新条目出现在 Web 列表（标题、信源、采集时间）
And 详情页提供原文快照与原始链接两个入口（无快照的内容不入库）
- [ ] #2 AC2: Given 重复采集同一信源而内容未更新
Then URL 指纹相同或内容相似度超阈值的条目被幂等跳过
And 情报库行数不变
- [ ] #3 AC3: Given 一条新内容被粗筛（关键词 + 小模型二分类）判为不相关
Then 它不进入消费列表，行级标记保留
And 运营者可在 Web 列表按处理状态筛出复核（漏报审计）
- [ ] #4 AC4: Given 抓取或处理失败
Then 原始内容先落盘不丢失，失败原因可查、可重放（细则见 NFR doc-003 与架构 §8）
<!-- AC:END -->
