---
id: TASK-1.01.01
title: 信源注册与信源页试抓取
status: To Do
assignee: []
created_date: '2026-09-01 09:25'
updated_date: '2026-09-02 08:58'
labels:
  - web
milestone: m-0
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-1.01
priority: high
type: story
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为运营者，我在 repo 的领域包 YAML 中注册信源（URL、类型、层级、频率、列表页入口），在 Web 信源页查看全部信源状态、触发试抓取验证可达性，以便信源配置可信、抓得通才启用——状态与验收都在页面上。

验收面：Web 信源页（信源状态列表 + 页内试抓报告）。注册与配置编辑保留在 YAML + Git（版本化留痕，ADR-001）；信源页承载可视、试抓与健康（健康随 Feature 推进逐层加深）。IA：详情页为聚合面、状态词表跨页一致（见原型 docs/prototype.html）。

不在本故事：采集入库与去重 / 粗筛（→ TASK-1.01.02）；信源健康告警与连续失败统计（→ TASK-4.02.01）；领域包其它节（关键词 / 竞品 / 标签树 / 模板 / 提示词）的生效由各消费故事自验（→ TASK-1.02.01 等）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 运营者在领域包 YAML 中新增信源并提交且缺必填字段之一（id / name / type / url / list_url / reliability / level / fetch_frequency / enabled）｜When 流水线加载配置｜Then 加载被拒绝，错误指出缺失字段名与所在行号，且已加载配置不受影响（不半截加载）
- [ ] #2 AC2: Given 一个已成功加载的领域包｜When 运营者打开 Web 信源页｜Then 页面列出全部信源，每源展示名称、类型、层级、可靠性、频率、启用状态，列表与 sources 节一一对应；新增或删除信源经重载后在页面上反映
- [ ] #3 AC3: Given 信源页上某个 enabled=false 的新增信源｜When 运营者点击试抓取｜Then 页面展示试抓报告，按 robots / 列表页 / 详情 / 快照 四维逐项标成败；robots 禁止抓取时标记拒绝且不发起后续抓取（合规 NFR · doc-3）
- [ ] #4 AC4: Given 某信源试抓取通过｜Then 报告仅作启用依据——通过后由运营者在 YAML 中将 enabled 置 true（Git 留痕），工具不自动改写 YAML（人最终环节，ADR-001 / ADR-002）；enabled=false 的源不参与采集（调度器不拾取，跨 TASK-4.01）
- [ ] #5 AC5: Given 运营者在领域包 YAML 中新增 / 修改 / 删除信源｜When 重新加载配置｜Then 信源页与调度器按新信源清单生效，核心系统无任何代码变更（ADR-001）
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 验收面字段与事实源（领域包 schema / 原型 IA / doc-2）逐项核对一致；偏差先修订事实源或记 ADR，不在代码里私自偏移
- [ ] #2 无新增未论证的自部署组件；核心代码不出现行业知识硬编码（违反即返工）
- [ ] #3 AC 全满足，每条有可复现证据（测试名 / 命令 / 截图），实际运行通过——非臆测的「应能通过」推断
- [ ] #4 CI 有增量测试且变绿；覆盖正常路径与关键失败路径
- [ ] #5 无回归（现有测试不破）
- [ ] #6 触碰的架构 / ADR / NFR / 运营手册同步更新，day0 文档改动进正文不留批注
- [ ] #7 结构化日志与运行留痕按 doc-2 §8 落地；迁移 / 配置变更可回滚（1 人可恢复）
- [ ] #8 无密钥硬编码；新增依赖真实、锁版本、无高危 CVE
- [ ] #9 不违反贯穿性约束与 ADR（偏离须先记 ADR）
<!-- DOD:END -->
