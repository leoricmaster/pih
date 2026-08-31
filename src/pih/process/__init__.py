"""处理层·LangGraph 编排（架构 §4 PROCESS）。

模块：
- llm.py        OpenAI 兼容客户端（trust_env=False / tier 路由 / 线性退避重试）
- textprep.py   raw_html → 剥标签纯文本 + 截断
- extraction.py 抽取模型 + validate_pred（7 键 / 枚举 / 标签树 / 可信度校验）
- graph.py      三节点图：粗筛→抽取→校验（SPK-3 工程化，领域包注入）
- run.py        ProcessRunner：pending 批处理 + Admiralty 拼装 + 统计

三条契约已落实：
- 重试计数区分 schema 补问（validate_rounds）与 API 重试（api_retries）✅；
- 评分口径改语义相似度——留提示词迭代（领域包版本化），非工程化范畴；
- 流水线状态机保证 text 字段始终在场（Runner 构态契约 + 单测）✅。

待交付：时效管理器（decay，过期降权与复核提醒）。
"""
