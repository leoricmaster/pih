---
id: TASK-7
title: 技术债清理：load_pack 吞错显式化 + 测试层标记统一 + web.py 拆分阈值
status: To Do
assignee: []
created_date: '2026-09-03 02:36'
labels:
  - tech-debt
dependencies: []
priority: low
type: chore
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
来源：TASK-1.01.01 实现中发现的三处债（原建议挂 TASK-1.01.02，独立成单便于单独排期；TASK-1.01.02 规划时可按需吸收）。(a) load_pack 将文件/解析错误吞成 None——信源页有错误诊断面，但 api/event 服务路径静默降级为空数据，错误不可见；(b) pytest 契约/集成层的容器前置 marker 命名与 README 分层表口径存在漂移（哪些标记、如何跳过）；(c) web.py 已 426 行且随故事增长，拆分时机无判据。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 load_pack 错误路径显式化：调用方可区分「无包」与「包损坏」，api/event 路径不再静默空数据（附先红后绿测试）
- [ ] #2 pytest marker 与 README「测试分层与 CI」表逐一对应，容器前置跳过行为有测（无容器环境跑 unit 不误报）
- [ ] #3 web.py 拆分定阈值与方案（如超 N 行或双故事触达即拆 routes/web 分层），记入 doc-2 或 ADR 并获用户确认
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
