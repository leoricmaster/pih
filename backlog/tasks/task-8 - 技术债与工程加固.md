---
id: TASK-8
title: 技术债与工程加固
status: To Do
assignee: []
created_date: '2026-09-03 10:48'
labels: []
dependencies: []
type: epic
ordinal: 33000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
工程本身的健康度：CI 加固、代码债清理、测试基建改进等不直接产出产品能力、但决定迭代速度与质量底线的工作。与四个业务 EPIC（情报生产/消费/认知求证/系统自运营）并列。设立出处：2026-09-03 评审裁定——TASK-5/7 原顶层平铺不合规（故事须挂 EPIC/FT），技术债类工作归此 EPIC。
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
