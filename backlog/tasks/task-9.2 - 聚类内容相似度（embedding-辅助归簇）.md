---
id: TASK-9.2
title: 聚类内容相似度（embedding 辅助归簇）
status: To Do
assignee: []
created_date: '2026-09-04 02:16'
labels: []
dependencies: []
parent_task_id: TASK-9
priority: low
type: story
ordinal: 36000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
来源：TASK-1.02.01 AC5 口径收窄裁定（2026-09-03 夜，D2）——AC 字面「内容相似度超阈值」经对齐 doc-2 §4 收窄为「主体归一×事件类型×±7天时间窗」；用户 2026-09-04 晨裁定：接受收窄，embedding 相似度剥离为本独立演进故事（区别于 TASK-9.1 近重复去重：9.1 防重复行，本故事提升聚类判据）。方向：intel_item 正文 embedding 入 pgvector 检索列；聚类在主体×类型×时间窗命中候选后加相似度阈值校验（阈值标定需离线评估集，doc-2 §6.3「无评估手段不引入」是当初收窄主因——先建评估集再定阈值）。前置：pgvector 检索列落地（doc-2 §7 检索层规划）。
<!-- SECTION:DESCRIPTION:END -->

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
