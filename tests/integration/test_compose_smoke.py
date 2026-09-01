"""集成 smoke 测试（T6 / AC4）。

需 `docker compose up` 后运行：
    uv run pytest tests/integration -v
conftest 已自动给 integration/ 下测试加 @pytest.mark.integration 标记。

验证：PG 可连 + pgvector 扩展可建、MinIO 可连 + bucket 可建、app 容器可 import pih。
这些探测通过 docker compose exec 走，不引入 psycopg 等 DB 依赖（store 层已另行落地直连测试）。
"""
from __future__ import annotations

import os
import subprocess

import pytest

pytestmark = pytest.mark.integration

COMPOSE = ["docker", "compose"]
PG_ENV = os.environ.get("POSTGRES_USER", "pih")
MINIO_USER = os.environ.get("MINIO_ROOT_USER", "pih")
MINIO_PASS = os.environ.get("MINIO_ROOT_PASSWORD", "pih12345")


def _compose_exec(service: str, cmd: list[str], *, check: bool = True) -> str:
    """docker compose exec -T <service> <cmd>，返回 stdout。"""
    result = subprocess.run(
        COMPOSE + ["exec", "-T", service] + cmd,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        pytest.fail(f"exec {service} 失败（rc={result.returncode}）：{result.stderr}")
    return result.stdout


class TestPostgres:
    def test_pg_responds(self):
        out = _compose_exec("postgres", ["psql", "-U", PG_ENV, "-d", "pih", "-c", "SELECT 1;"])
        assert "1" in out

    def test_pgvector_extension_creatable(self):
        """pgvector 扩展可创建（架构 §7 混合检索依赖）。"""
        sql = (
            "CREATE EXTENSION IF NOT EXISTS vector; "
            "SELECT extname FROM pg_extension WHERE extname='vector';"
        )
        out = _compose_exec("postgres", ["psql", "-U", PG_ENV, "-d", "pih", "-c", sql])
        assert "vector" in out


class TestMinIO:
    def test_minio_ready(self):
        out = _compose_exec("minio", ["mc", "ready", "local"])
        assert "ready" in out.lower()

    def test_minio_bucket_creatable(self):
        """MinIO bucket 可建（架构 §5.3 原文快照依赖）。"""
        _compose_exec(
            "minio",
            ["mc", "alias", "set", "localtest", "http://localhost:9000", MINIO_USER, MINIO_PASS],
        )
        out = _compose_exec(
            "minio",
            ["mc", "mb", "localtest/pih-smoke-test", "--ignore-existing"],
        )
        assert "Bucket" in out or "created" in out.lower() or "" == out.strip()
        _compose_exec("minio", ["mc", "rb", "localtest/pih-smoke-test", "--force"], check=False)


class TestAppContainer:
    def test_app_imports_pih(self):
        """app 容器能 import pih 包（src-layout + compose volume 挂载正确）。"""
        out = _compose_exec("app", ["python", "-c", "import pih; print(pih.__version__)"])
        assert "0.1.0" in out

    def test_app_can_validate_domain_pack(self):
        """app 容器内能加载并校验真实领域包（端到端通路验证）。"""
        script = (
            "from pih.domainpacks.loader import load; "
            "p=load('/app/domain_packs/construction_machinery/pack.yaml'); "
            "print(p['meta']['domain_id'])"
        )
        out = _compose_exec("app", ["python", "-c", script])
        assert "construction_machinery" in out
