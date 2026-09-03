---
id: doc-4
title: 术语词表
type: other
created_date: '2026-09-02 11:24'
updated_date: '2026-09-03 03:54'
---
# 术语词表（项目统一词表）

只收在本项目有**特殊含义或易混淆**的术语，以及**用户呈现词**（界面上出现的字眼的统一含义与呈现基线）。防腐化不复制定义正文：定义在事实源，本表收一句话+指针。词条格式：
术语 —— 一句话含义；代码/配置标识符映射；事实源指针；**呈现**（可选）= UI 标签/文案基线。术语歧义先查本表，再查事实源。用户文档未来从本表取材。

## 配置与采集域

- **信源（source）** —— 一个被抓取的网站入口，领域包 `sources[]` 一项；标识符 `source.id`（如 `sany`）；字段事实源：domain_packs/*/pack.yaml + doc-2 §5.1。
- **领域包（Domain Pack）** —— 行业知识的 YAML 配置（信源/主体/事件类型/排序权重等），配置非代码（ADR-001）；标识符 `domain_packs/<domain>/pack.yaml`、`pih.domainpacks`。
- **信源类型（type）** —— 抓取方式，决定用哪类适配器：网页=从列表页网页解析详情链接逐条抓正文；RSS=订阅源标准格式直接取条目；API=站点公开接口取结构化数据；变更监控=对方未提供接口时的主动监控（不解析内容，检测页面变化）；标识符 `sources[].type`、`SOURCE_TYPES`；事实源：doc-2 §4。**呈现**：html→网页、rss→RSS、api→API、change_monitor→变更监控。适配器接入状态是运行时事实（页面查注册表渲染徽标），不入词表。
- **层级（level） vs 来源可靠性（reliability）——两轴不合并** —— 层级看**出身**：L1 官方/主机厂一手、L2 权威/垂直媒体、L3 聚合站、L4 弱信号（结构性，注册时判定）；可靠性看**表现**：Admiralty 来源可靠性官方分档 A 完全可靠 / B 通常可靠 / C 较为可靠 / D 通常不可靠 / E 不可靠 / F 无法判断。两轴正相关但独立，出身好≠表现好（原型期曾把 A/B/C 写进层级列——本混同是建本词表的直接动因）。赋值只经两途：注册人按官方定义**人工初评**；核实历史结局（verification_log）驱动**画像重估**——不设并行赋值规则；标识符 `sources[].level/.reliability`、`SOURCE_LEVELS`/`RELIABILITY_VALUES`；事实源：doc-2 §6.3。**呈现**：值原样（如 L2 / B）+ 图例句「层级看出身，可靠性看表现」。
- **Admiralty 码** —— 可靠性×可信度两维记法（如 B2）；本项目 reliability 维（A–F）挂信源、可信度维（1–6）挂条目，`admiralty_code` 存两位简写；事实源：doc-2 §6.3。
- **试抓取（probe） vs 采集（collect）** —— probe 是启用前的人工验证（不受 enabled 门控，产出四段报告不落库）；collect 是正式采集落库（仅 enabled 源）；标识符 `probe_source()` / `collect` CLI、`pih.collect.probe|run`。
- **enabled 门控** —— `enabled: false` 的源不参与采集（调度器不拾取）；由运营者手工改 YAML、Git 留痕，工具永不改写（ADR-001/002，人最终环节）。**呈现**：on→启用、off→停用。
- **抓取频率（fetch_frequency）** —— 采集节奏，调度器消费；调度器未上线前仅配置落盘不生效；标识符 `FETCH_FREQUENCIES`、`sources[].fetch_frequency`。**呈现**：hourly→每小时、daily→每日、weekly→每周。
- **快照（snapshot）** —— 详情页原始字节的 MinIO 存档，键=内容指纹；标识符 `pih.collect.snapshot.SnapshotStore`、bucket `pih-snapshots`；「原文可查」的依据（ADR-005）。
- **内容指纹（content_sha1）** —— 原文正文的 SHA1，去重键兼快照键；标识符 `intel_item.content_sha1`（UNIQUE）。
- **robots 合规** —— 抓取前查 robots.txt（站点对爬虫的声明文件，RFC 9309），拒绝则不发起后续请求（NFR doc-3）；probe 报告第一段。**呈现**：页面称「robots 合规检查」。

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
