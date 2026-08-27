"""存储层（架构 §4 STORE / §7 数据架构）。

PostgreSQL 为单一事实源（ADR-005）。Sprint 3 落地最小切片：
  source      领域包 sources 的镜像（启动时 upsert）
  intel_item  RawItem 落库，content_sha1 唯一约束（ADR-007 幂等键）

event / verification_log / competitor_profile 等表留 process Sprint。

模块：
  db.py          ConnectionPool 单例
  source_sync.py 领域包 sources → source 表 upsert
  repository.py  IntelRepository: save / list_by_source / get
  errors.py      入库异常包装

不引入 ORM；查询用原生 SQL，模型用 dataclass（与 collect 层一致）。
"""
