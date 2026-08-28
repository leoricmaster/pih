"""消费层（架构 §4 CONSUME）。

Sprint 5a 已交付：
- 查询服务（Web + API）：QueryService 同源，Web 列表/详情 + JSON API（ADR-006）
- 鉴权：API 端点 Bearer token，Web 内网开放
- 北极星指标：结构化日志按 Web/API 分别计数

后续 Sprint：
- RAG 问答服务（M2）：混合检索问答，答案强制带引用
- 报告服务（M2）：周/月报生成，模板由领域包提供
- 推送服务（M2）：即时/定期推送，渠道可配置
"""
