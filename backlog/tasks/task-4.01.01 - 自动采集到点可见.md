---
id: TASK-4.01.01
title: 自动采集到点可见
status: To Do
assignee: []
created_date: '2026-09-01 09:26'
updated_date: '2026-09-02 08:58'
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 AC 全满足，每条有可复现证据（测试名 / 命令 / 截图），实际运行通过——非臆测的「应能通过」推断
- [ ] #2 CI 有增量测试且变绿；覆盖正常路径与关键失败路径
- [ ] #3 无回归（现有测试不破）
- [ ] #4 触碰的架构 / ADR / NFR / 运营手册同步更新，day0 文档改动进正文不留批注
- [ ] #5 结构化日志与运行留痕按 doc-2 §8 落地；迁移 / 配置变更可回滚（1 人可恢复）
- [ ] #6 无密钥硬编码；新增依赖真实、锁版本、无高危 CVE
- [ ] #7 不违反贯穿性约束与 ADR（偏离须先记 ADR）
<!-- DOD:END -->
