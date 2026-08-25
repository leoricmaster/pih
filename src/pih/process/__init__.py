"""处理层·LangGraph 编排（架构 §4 PROCESS）。

模块职责（后续 Sprint 实现，本 Sprint 仅占位）：
- 核实引擎：来源分级、Admiralty 评级、事实/推断分离；verify(item)→IntelItem(预核实)
- 结构化抽取器：按 schema 抽取主体/事件/参数/标签；extract(item, pack)→IntelItem
- 事件聚类器：同事件多源聚类，驱动交叉印证；cluster(item)→event_id
- 时效管理器：有效期计算、过期降权、复核提醒

Sprint 0 设计输入（spike 遗留 Minor 沉淀为此层契约）：
- 重试计数口径混计 → 重试计数须区分"schema 补问"与"真正重试"（ADR-007 范畴）
- 评分口径改语义相似度 → SPK-2 发现字符串相等太严，生产期改语义相似度
- 异常分支 state 缺 text → 流水线状态机须保证 text 字段始终在场
"""
