---
id: TASK-1.03.01
title: 统一录入入口
status: To Do
assignee: []
created_date: '2026-09-01 09:25'
updated_date: '2026-09-02 08:58'
labels:
  - web
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-1.03
type: story
ordinal: 18000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为贡献者，我想把文本 / 文件 / 录音丢进一个入口，30 秒内完成，系统自动结构化入库，以便我的见闻不流失。

验收面：录入入口（Web 页面）+ 录入后条目出现在 Web 列表并走完与互联网情报相同的处理链。（录音转写、会议纪要结构化、录入激励与流转机制等子能力待梳理时渐进明细为独立故事。）
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 要点1: 单次录入 ≤30 秒
- [ ] #2 要点2: 走与自动采集同一流水线（来源类型=人工，来源可靠性默认 A/B 级，仍需事实核查）
- [ ] #3 要点3: 自动结构化复用同一抽取链；录入情报同样进事件聚类、人工核实页，可在 Web 消费并反馈——与互联网情报同一质量闭环，无差异对待
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
