---
id: TASK-2.02.02
title: 人工核实页
status: Done
assignee:
  - '@lancer'
created_date: '2026-09-01 09:26'
updated_date: '2026-09-03 11:39'
labels:
  - web
milestone: m-0
dependencies:
  - TASK-1.02.01
references:
  - docs/prototype.html
parent_task_id: TASK-2.02
priority: high
type: story
ordinal: 21000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为运营者，我想在一个 Web 队列页里查看已具备升级条件与待人工的条目，一键确认或证伪，以便控制入库质量、终态由人把关。

验收面：Web 核实页（队列 + 确认 / 证伪操作）。积压提醒并入 AC4。

不在本故事：聚类与「已具备升级条件」的生产侧判定（→ TASK-1.02.01）；可信度与跃迁历史的只读呈现（→ TASK-2.02.01，本故事承载操作不承载只读呈现）；组合筛选（→ TASK-2.01.01）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 AC1: Given 存在需人工处理的情报 / 事件 ｜ When 运营者打开核实页 ｜ Then 按 置信度升序 + 采集时间升序 排列（低置信、最老的优先）｜ And 队列含三类：已具备升级条件的事件、低置信度情报、待人工条目
- [x] #2 AC2: Given 运营者对单源确认事件点击确认 ｜ Then 事件状态跃迁为 多源确认（人工终态），写 verification_log（操作人、时间、原状态、新状态）
- [x] #3 AC3: Given 运营者点击证伪并填写理由 ｜ Then 事件状态跃迁为 已证伪（人工终态），理由写入日志 ｜ And 该事件下情报在检索结果中默认隐藏（检索权重降级为 0，见 doc-2 §6.3）
- [x] #4 AC4: Given 待核实事件持续 7 天无人处理 ｜ Then 在核实页积压提醒区列出（按滞留时长排序）
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 验收面字段与事实源（领域包 schema / 原型 IA / doc-2）逐项核对一致；偏差先修订事实源或记 ADR，不在代码里私自偏移
- [x] #2 无新增未论证的自部署组件；核心代码不出现行业知识硬编码（违反即返工）
- [x] #3 AC 全满足，每条有可复现证据（测试名 / 命令 / 截图），实际运行通过——非臆测的「应能通过」推断
- [ ] #4 CI 有增量测试且变绿；覆盖正常路径与关键失败路径
- [x] #5 无回归（现有测试不破）
- [x] #6 触碰的架构 / ADR / NFR / 运营手册同步更新，day0 文档改动进正文不留批注
- [x] #7 结构化日志与运行留痕按 doc-2 §8 落地；迁移 / 配置变更可回滚（1 人可恢复）
- [x] #8 无密钥硬编码；新增依赖真实、锁版本、无高危 CVE
- [x] #9 不违反贯穿性约束与 ADR（偏离须先记 ADR）
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
新页面故事（设计 docs/design/TASK-2.02.02-design.md，D5/D6/D7 已决）。切片：1) D7 检索默认排除已证伪（unit 先红→list_by_filter 加子句）2) repo 两新方法 list_low_confidence/list_stale_pending（unit SQL 契约）3) Web 核实页四区+confirm/refute POST（unit test_verify_page fake 注入先红→路由+verify.html+导航+CSS→绿）+ contract verify.html 4) detail 已具备升级条件提示链到 /verify 5) prototype.html 反向更新核实页节 6) integration test_verify_page 全流程 7) README+finalization
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TDD 切片 1（D7 检索默认排除已证伪）：unit test_no_filters_default_excludes_refuted 先红→list_by_filter 无显式 event_status 时追加 (e.status IS NULL OR e.status <> 'refuted')→绿；test_no_filters_no_where 语义随之更新（默认排除=恒有 WHERE）；显式 event_status=refuted 覆盖（test_explicit_refuted_overrides）。
TDD 切片 2（队列查询）：unit TestVerifyQueueQueries 先红→IntelRepository.list_low_confidence（可信度 4-6 ∪ 可靠性 D-F，排除已证伪）+ EventRepository.list_stale_pending（make_interval 7 天，first_seen_at ASC）→绿。
TDD 切片 3（核实页）：unit test_verify_page 7 例先红（路由不存在）→ GET /verify 四区（路由层排序：条目 map(admiralty) 升序破同分 fetched_at 升序；事件 first_seen_at 升序；滞留天数路由侧算 naive/aware 兜底）+ POST confirm（404/400/303）+ refute（空白 400/有理由 303）→绿；EventService.list_stale 透传；verify.html + 侧栏「核实」navlink + qcard CSS；contract TestVerifyPageRender 2 例；详情页已具备升级条件提示改链 /verify。
原型反向更新（D5）：新增 verify 页节（积压/ready 队列/低置信/待人工 四区 wireframe）+ 侧栏核实 navlink + 两处「未来呈现」注记改为已呈现 + crumbs。
integration test_verify_page 7 例：四区渲染（滞留天数/未超期不进积压）、confirm 写终态 log（operator/原态/新态行断言）、终态无出边 400、refute 理由入库+D7 默认隐藏+显式可查、空白 400、未知 404。
README 新增人工核实页段。
回归：unit+contract 423 / integration verify_page 7 / ruff 干净。
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
人工核实页交付（本故事为新增页面：CLI verify 存量，Web 操作面全新）。AC1 /verify 四区队列——积压提醒置顶、已具备升级条件事件（list_ready_for_manual 存量）、低置信度情报（新 list_low_confidence，D6 可信度4-6∪可靠性D-F）、待人工条目（list_inbox needs_manual）；排序=条目 map(admiralty) 升序+采集时间升序（低置信最老优先，路由层 ranking 权重计算）/事件按滞留最久优先（integration 断言含 3 天未超期不进积压）。AC2 POST /verify/{id}/confirm→confirmed 写 verification_log（integration 行断言 operator/single_source→confirmed；终态无出边 400）。AC3 refute 必填理由（空白 400）→refuted 理由入库+该事件下情报检索默认隐藏（D7：list_by_filter 默认排除，显式 event_status=refuted 可查——integration 双向断言）。AC4 list_stale_pending 7 天积压区按滞留排序（integration 滞留天数渲染）。原型反向更新核实页节（D5）。回归 unit+contract 423/integration 7+ruff 干净。DoD 8/9，#4 待 push（PD2）。
<!-- SECTION:FINAL_SUMMARY:END -->
