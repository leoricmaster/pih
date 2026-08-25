"""采集层（架构 §4 COLLECT）。

模块职责（后续 Sprint 实现，本 Sprint 仅占位）：
- 信源适配器：按类型抓取（RSS/网页/API/变更监控），插件化；fetch(source)→RawItem[]
- 调度器：按信源频率触发，失败重试与告警（APScheduler）
- 去重器：URL 指纹 + 内容相似度；dedup(RawItem)→bool
- 相关性粗筛：关键词 + 小模型二分类；classify(RawItem)→keep/drop
- 快照采集：原文存档（HTML/PDF/截图）存 MinIO，返回快照 ID

Sprint 0 设计输入（spike 遗留 Minor 沉淀为此层契约）：
- HTML 实体未解码 → 适配器层须对抓取文本做实体解码（&amp; &#xx; 等）
- robots 合规、交错间隔、charset 窗口 → 见 SPK-1 报告
"""
