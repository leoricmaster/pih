# TASK-1.02.01 设计：结构化抽取与详情分区

> 故事级细粒度设计，上承架构 doc-2 §4/§6.1/§6.4，下接代码与测试。
> 只记决策与理由、接口与状态语义、事实源偏差——不复述实现。
> 关联：backlog TASK-1.02.01 ｜ 原型 `docs/prototype.html` 详情节 ｜ ADR-002/003/004/007/011。
> 本轮按授权（PD1）设计后直接实现，决策点同步 `docs/mvp-run-decisions-2026-09-03.md` D2/D3。

## 1. 范围与存量映射

旧 Sprint 已交付本故事约九成产能（抽取三节点图 / 重问 / 质量门 / 聚类 / 详情分区），本故事增量=**补硬校验、对照取证、闭环偏差**，不重写既有资产。

| AC | 存量（实测） | 本故事增量 |
|---|---|---|
| AC1 详情分区 | detail.html 已有 结构化字段（主体/事件类型/标签/量化参数/Admiralty）+ 事实描述 + 推断与判断 三节；提示词规则 5 已要求推断以「依据：」开头 | validate_pred 硬校验推断含依据（D3，见 §2）；Admiralty 行补「来源可靠性 X × 可信度 Y」注解（对照原型） |
| AC2 重问≤3 降级不丢 | graph.py node_validate：MAX_VALIDATE_ROUNDS=3，失败 extraction=None → Runner 落 needs_manual | 无代码增量；补证据索引（既有测试） |
| AC3 占位主体→待人工+可筛 | run.py 后验质量门（PLACEHOLDER_SUBJECTS）；/inbox 状态筛选 + 检索视图显式覆盖 | 无代码增量；「进入核实页」由 TASK-2.02.02 核实页承接（doc-2 §6.4 needs_manual 队列与事件核实队列同在核实页），本故事取证到 /inbox 筛选 + 详情可达 |
| AC4 来源继承+Admiralty 非空 | list_pending JOIN source 取 reliability；assemble_admiralty=reliability+credibility | 无代码增量；证据索引 |
| AC5 聚类挂事件+双源自动跃迁 | event.py EventService.cluster：主体归一×事件类型×±7天；attach_and_advance 第二独立信源→pending→single_source（operator=system 写 verification_log）+ ready_for_manual | **口径收窄（D2）**：AC 字面「内容相似度超阈值」不实现——doc-2 §4 权威口径即主体×类型×时间窗，内容相似度属模糊去重演进（TASK-9.1）；comment 记档 |
| AC6 未命中新建待核实事件 | create_event 初始 pending | 无代码增量；证据索引 |

范围外（防私扩）：可信度与事件状态的 Web 呈现深化（→2.02.01）；核实页操作面（→2.02.02）；组合筛选（→2.01.01）；详情页整体 IA 重排（→TASK-6 还原度复查，本故事只做字段级对照）。

## 2. 关键决策与理由

| # | 决策 | 备选与否决理由 |
|---|---|---|
| D1 | **推断依据硬校验**：validate_pred 中「推断与判断」非空时须含「依据」标记（子串匹配，容全/半角冒号），不合格走既有重问→降级链 | 仅提示词引导（现状）不满足 AC「必须含依据」字面；独立小模型判依据=新增调用成本无增益。提示词规则 5 已要求「依据：」开头，硬校验与提示词同构，实测 LLM 输出天然合规，重问为兜底 |
| D2 | 聚类口径收窄（§1 AC5 行）；与 1.01.02 AC2 收窄同构，task comment 记档 | 引入 embedding 相似度：需 pgvector 检索列+阈值标定，超 MVP 且无评估手段 |
| D3 | 详情页 Admiralty 行补双维注解（B2 → 「来源可靠性 B × 可信度 2」），推断保持原文渲染（已含依据串） | 拆依据为独立 tag（原型样式）：字段级增强收益低，排版属 TASK-6 |

## 3. 接口与状态语义

- `validate_pred(pred, vocab)`：新增失败类别——`推断与判断为「…」缺依据`；空串仍放行（无推断无依据要求）。
- 状态机无变化（pending→extracted/needs_manual/filtered_out/dead 既有语义，ADR-011）。
- 事件聚类语义无变化（§6.1 状态机挂事件层；自动跃迁 operator=system）。

## 4. 测试与 CI

| 层 | 增量 |
|---|---|
| unit | test_extraction 新增 TestInferenceBasis（无依据拒/含依据过/空串放行）；test_graph 补一条「推断缺依据触发重问后补依据通过」（锁图级链路） |
| contract | 无新迁移，无增量 |
| integration | 既有 test_process_e2e / test_cluster_e2e 复用作 AC 证据；不新增（接线缝已覆盖） |
| live | finalization 时真实 collect→process 实弹（兼作演示数据），取证 Admiralty 非空与分区渲染 |

## 5. 事实源偏差与裁决

| 偏差 | 裁决 |
|---|---|
| AC5「内容相似度超阈值」vs doc-2 §4「主体归一×事件类型×时间窗」 | 以 doc-2 为准收窄（D2），comment 记档，模糊去重归 TASK-9.1 |
| AC3「进入核实页」 | 核实页属 TASK-2.02.02 验收面；本故事取证止于「按处理状态筛出 + 详情可达」，2.02.02 交付时闭环 |

## 6. AC 证据清单（finalization 逐条补实测）

- AC1：contract test_templates_render（detail 渲染）+ live 详情页 URL 截图/文案 + 新增 Admiralty 注解断言
- AC2：unit test_graph::test_reask_once_then_pass / test_exhausted_rounds_needs_manual / test_validate_api_failure_breaks_to_manual
- AC3：unit test_run::TestPostHocQualityGate 3 例 + /inbox?status=needs_manual 实弹（200 + 行可见）
- AC4：unit test_run::TestAssembleAdmiralty + test_extracted_with_admiralty
- AC5：unit test_event_cluster + integration test_cluster_e2e（自动跃迁 operator=system、ready_for_manual）
- AC6：integration test_cluster_e2e（新建事件初始 pending）
