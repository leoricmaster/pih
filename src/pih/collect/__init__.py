"""采集层（架构 §4 COLLECT）。

已交付：
- 信源适配器（adapters/）：按源特化列表/详情解析（type=html 的通用基类
  HtmlAdapter + 未特化源的 NotImplementedError 占位）；fetch → RawItem
- HTTP 客户端（httpclient）：重试/节流/编码；robots 合规（robots）
- 原文快照（snapshot）：HTML 存 MinIO，返回快照 ID
- 采集编排（run）：enabled 门控 + source 表同步 + 幂等落库（ADR-007）
- 试抓取（probe）：robots→列表→详情→快照 报告（S3.2.1 AC1）

待交付：
- 调度器：按信源频率触发，失败重试与告警（APScheduler，ADR-004）
- 去重器：内容相似度（URL 指纹已由 content_sha1 唯一约束覆盖）

采集层契约（SPK-1 验证沉淀）：
- HTML 实体未解码 → 适配器层须对抓取文本做实体解码（&amp; &#xx; 等）
- robots 合规、交错间隔、charset 窗口 → 见 SPK-1
"""
