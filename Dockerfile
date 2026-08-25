# intel-pipeline 应用容器（架构 §3）
# dev 模式：挂载 src/ 热重载，默认不启动长期进程（Sprint 1 无业务服务）
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# uv：与本地一致的依赖管理
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 先装依赖（利用层缓存：requirements 变化时才重装）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 源码与领域包（dev 模式由 compose 用 volume 覆盖）
COPY src/ ./src/
COPY domain_packs/ ./domain_packs/

# 激活 venv：让 python/pytest 直接可用
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src

# dev 模式默认 sleep，不启动长期进程；后续 Sprint 在此启动调度器/查询服务
CMD ["sleep", "infinity"]
