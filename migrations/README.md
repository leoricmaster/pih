# 数据库迁移（Alembic）

Sprint 3 起立迁移工具链。alembic 配置在 `alembic.ini`，迁移脚本在 `versions/`。

## DSN 来源

`migrations/env.py` 用 python-dotenv 从 cwd 的 `.env` 读 `PG_DSN`。`.env.example` 已给模板。

## 常用命令

```bash
# 升到最新
uv run alembic upgrade head

# 回到基线（删所有表）
uv run alembic downgrade base

# 查看当前版本
uv run alembic current

# 新建一个空迁移
uv run alembic revision -m "描述"
```

## 编写约定

- 迁移手写（不依赖 autogenerate），schema 跟着已实现能力走，不预置未实现的字段（见 Sprint 3 设计规格 §0/D3）；
- 每个迁移含 `upgrade` 与 `downgrade` 两段，downgrade 必须可逆；
- DDL 用 `op.execute` 写原生 SQL，不用 SQLAlchemy Table 定义（store 层不引入 ORM）。
