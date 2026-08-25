"""pytest 全局夹具。

测试分层：
- unit/      纯函数，无 IO，不依赖容器
- contract/  domain_packs/*.yaml 对 schema 校验
- integration/ 需 docker-compose up，用 @pytest.mark.integration 隔离
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DOMAIN_PACKS_DIR = REPO_ROOT / "domain_packs"


def pytest_collection_modifyitems(items):
    """自动给 integration/ 下的测试加 mark，省得手写装饰器。"""
    integration_dir = REPO_ROOT / "tests" / "integration"
    for item in items:
        if integration_dir in Path(item.fspath).resolve().parents:
            item.add_marker("integration")


__all__ = ["DOMAIN_PACKS_DIR", "REPO_ROOT"]
