---
id: TASK-9
title: 技术演进
status: To Do
assignee: []
created_date: '2026-09-03 10:48'
labels: []
dependencies: []
type: epic
ordinal: 34000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
已交付能力的演进方向：模糊去重、时效管理等「现在不做但已裁定要做」的增强——区别于技术债（债是欠的清理，演进是向前的增强）。设立出处：2026-09-03 评审裁定；首个故事为模糊/近重复去重（TASK-1.01.02 AC2 评审裁定留演进）。
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
