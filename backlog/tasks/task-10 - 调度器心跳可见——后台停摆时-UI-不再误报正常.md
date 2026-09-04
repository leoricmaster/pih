---
id: TASK-10
title: 调度器心跳可见——后台停摆时 UI 不再误报正常
status: To Do
assignee: []
created_date: '2026-09-04 06:48'
labels:
  - consume
  - observability
dependencies: []
references:
  - doc-6 - 用户旅程与使用节奏-User-Journeys.md
  - TASK-4.01.01
priority: medium
type: bug
ordinal: 37000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
走查发现：`pih work` 调度器进程可静默僵死（本次实测停摆 10.5h），期间 `/sources` 健康列仍显示「正常」——因为「正常」语义是 `last_success_at` 曾成功，而非进程活着。铃铛只对「失败」告警，进程死了反而安静。运营者晨检（旅程 A 第 4 步「确认自运转」）在当前 UI 下结构性不可达成：无法发现系统其实停了。与 D13 同级的可见性缺口。\n\n根因：无调度器心跳可见性——无人值守门槛（Charter §7）计时也因此中断不可察觉。\n\n建议方向（待排期细化）：信源页或独立面板显示「最近调度时间 + 已 N 小时未运行」，或后台超 N 小时无 pipeline_run 自动发站内信告警。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 调度器进程停摆超过阈值（如 2h 无 pipeline_run）时，运营者在 Web UI 上能直接看到异常提示（而非 `/sources` 全绿）
- [ ] #2 异常提示路径与旅程 A 晨检一致——运营者无需主动查 CLI/日志即可发现
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
