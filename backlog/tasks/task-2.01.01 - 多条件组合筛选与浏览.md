---
id: TASK-2.01.01
title: 多条件组合筛选与浏览
status: To Do
assignee: []
created_date: '2026-09-01 09:26'
updated_date: '2026-09-02 08:58'
labels:
  - web
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-2.01
type: story
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为消费者，我想按 主体 / 事件类型 / 时间范围 / 标签 / 置信度 组合筛选情报列表，以便快速定位某类信息。

验收面：Web 列表筛选。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 情报库已有数据
When 消费者选定 主体 / 事件类型 / 时间范围 / 标签 / 置信度 组合
Then 列表仅展示同时满足所有条件的情报
And 每条显示 标题、主体、事件类型、置信度、采集时间
- [ ] #2 AC2: Given 筛选结果为空
Then 页面提示无结果，并建议放宽条件
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
