"""存储层（架构 §4 STORE / §7 数据架构）。

PostgreSQL 为单一事实源（ADR-005）：intel_item / entity / source / event /
verification_log / domain_pack / competitor_profile / feature_matrix / param_matrix。
pgvector 承载摘要向量 + PG 中文全文检索承担 BM25 侧；MinIO 存原文快照。

本 Sprint 仅占位；表结构与迁移工具（alembic）留到建第一张业务表的 Sprint。
"""
