---
id: doc-4
title: 术语词表
type: other
created_date: '2026-09-02 11:24'
updated_date: '2026-09-02 11:24'
---
# 术语词表（项目特殊含义）

只收在本项目有**特殊含义或易混淆**的术语，防腐化不复制定义正文。词条格式：
术语 —— 一句话含义；代码/配置标识符映射；事实源指针。术语歧义先查本表，再查事实源。

## 配置与采集域

- **信源（source）** —— 一个被抓取的网站入口，领域包 `sources[]` 一项；标识符 `source.id`（如 `sany`）；字段事实源：domain_packs/*/pack.yaml + doc-2 §5.1。
- **领域包（Domain Pack）** —— 行业知识的 YAML 配置（信源/主体/事件类型/排序权重等），配置非代码（ADR-001）；标识符 `domain_packs/<domain>/pack.yaml`、`pih.domainpacks`。
- **试抓取（probe） vs 采集（collect）** —— probe 是启用前的人工验证（不受 enabled 门控，产出四段报告不落库）；collect 是正式采集落库（仅 enabled 源）；标识符 `probe_source()` / `collect` CLI、`pih.collect.probe|run`。
- **enabled 门控** —— `enabled: false` 的源不参与采集（调度器不拾取）；由运营者手工改 YAML、Git 留痕，工具永不改写（ADR-001/002，人最终环节）。
- **reliability vs level** —— reliability 是**来源可靠性**（Admiralty 码 A–F），level 是**信息层级**（L1–L4，一手/转述…）；原型期曾把 A/B/C 写进层级列——本混同是建本词表的直接动因；事实源：pack.yaml sources 字段 + doc-2 §5.1。
- **Admiralty 码** —— 可靠性×可信度两维记法（如 B2）；本项目只用 reliability 维（A–F）+ admiralty_code 字段存两位简写；事实源：doc-2 §6.3。
- **快照（snapshot）** —— 详情页原始字节的 MinIO 存档，键=内容指纹；标识符 `pih.collect.snapshot.SnapshotStore`、bucket `pih-snapshots`；「原文可查」的依据（ADR-005）。
- **内容指纹（content_sha1）** —— 原文正文的 SHA1，去重键兼快照键；标识符 `intel_item.content_sha1`（UNIQUE）。
- **robots 合规** —— 抓取前查 robots.txt，拒绝则不发起后续请求（NFR doc-3）；probe 报告第一段。

## 处理与事件域

- **情报条目（intel item） vs 事件（event）** —— intel_item 是单源单页的结构化抽取结果；event 是跨源聚合的核实主体（主体×事件类型）；标识符 `intel_item.event_id → event`；事实源：doc-2 §5.2。
- **粗筛（screening） 与 process_status** —— LLM 相关性粗筛是 process 流水线一步；process_status 是 intel_item 的处理状态机（pending/extracted/…），勿与事件核实状态混淆；标识符 `intel_item.process_status`。
- **核实状态机（verification status）** —— 事件级五态：pending/待核实 → single_source/单源确认 → confirmed/多源确认，及 refuted/已证伪、expired/已过期；跃迁写 verification_log；标识符 `event.status`、`pih.process.event`；事实源：doc-2 §5.2 + 状态机 ADR。
- **收件箱（inbox）** —— 新事件进入人工核实的入口视图（m-0 后续故事）；勿与「站内信」混淆——本项目无用户消息系统。
- **站内信** —— 消费层对运营者的页内提示（如反馈已记录）；非用户间消息。

## 消费域与测试

- **未达（unreached）** —— 试抓报告三态之一：**前置失败导致未执行**（如 robots 拒绝后列表/详情/快照均未达）；区别于「失败」（执行了未通过）；标识符 `_probe_view` state=skip、模板 tag muted。
- **信源页** —— Web 端 `/sources`：信源清单 + 页内试抓 + 配置错误诊断面；编辑仍在 YAML+Git。
- **测试分层** —— unit（无容器）/ contract（PG）/ integration（compose 全栈）/ live（外网真实站点）；不变式：CI 可运行集单调增长；事实源：README「测试分层与 CI」。
