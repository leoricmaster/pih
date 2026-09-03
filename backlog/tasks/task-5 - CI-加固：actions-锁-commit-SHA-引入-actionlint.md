---
id: TASK-5
title: CI 加固：actions 锁 commit SHA + 引入 actionlint
status: To Do
assignee: []
created_date: '2026-09-03 02:36'
updated_date: '2026-09-03 10:50'
labels:
  - infra
  - ci
dependencies: []
parent_task_id: TASK-8
priority: low
type: chore
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
来源：TASK-1.01.01 交付包遗留改进（doc-5 遗留节两条）。ci.yml 当前 actions 用版本 tag（checkout@v4、setup-uv@v5），存在供应链替换风险；workflow 语法无静态校验——首建时只能以本地等价演练代替 actionlint。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ci.yml 所有 uses 均 pin 到 commit SHA（旁注版本号便于升级）
- [ ] #2 actionlint 可在本地一键运行（make 目标或 uv script）并纳入 CI 自检步骤
- [ ] #3 ci.yml 通过 actionlint 零告警；CI 首跑后 Actions 页面全绿截图/链接记入 notes
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
