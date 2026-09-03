---
id: TASK-9.1
title: 模糊/近重复去重
status: To Do
assignee: []
created_date: '2026-09-03 10:48'
labels: []
dependencies: []
references:
  - backlog/tasks/task-1.01.02 - 采集入库与原文可查.md
parent_task_id: TASK-9
type: story
ordinal: 35000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
现状：幂等仅精确指纹——content_sha1（正文规范化哈希）UNIQUE，ON CONFLICT DO NOTHING（ADR-007）。正文微改（广告位/时间戳/转载小改）即指纹不同，重复采集会产生近重复条目。裁定出处：TASK-1.01.02 AC2 评审（2026-09-03）「模糊/近重复去重留作一个演进故事」。方向：近重复识别（相似度阈值或规范化增强指纹），重复投递合并或行级标记；不破坏精确指纹幂等既有语义。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Given 同一内容以微小差异（如广告位/时间戳变化）被重复采集 | When 入库 | Then 近重复被识别并合并或标记，不产生多条实质重复条目
- [ ] #2 Given 既有精确指纹幂等路径 | When 本故事落地 | Then content_sha1 UNIQUE 语义与既有行为无回归
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
