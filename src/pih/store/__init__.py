"""存储层（架构 §4 STORE / §7 数据架构）。

PostgreSQL 为单一事实源（ADR-005）。已落地五表（迁移 0001 单基线）：
  source           领域包 sources 的镜像（启动时 upsert）
  intel_item       RawItem 落库，content_sha1 唯一约束（ADR-007 幂等键）
  event            事件聚类与核实状态机（ADR-003）
  verification_log 事件状态跃迁历史
  feedback         消费页人类反馈

仍未交付：competitor_profile 类资产表（未建）。

模块：
  db.py          ConnectionPool 单例
  source_sync.py 领域包 sources → source 表 upsert
  repository.py  IntelRepository: save / list_by_source / get
  errors.py      入库异常包装

不引入 ORM；查询用原生 SQL，模型用 dataclass（与 collect 层一致）。
"""
