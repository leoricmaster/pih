"""pytest 全局夹具。

测试分层：
- unit/      纯函数，无 IO，不依赖容器
- contract/  domain_packs/*.yaml 对 schema 校验
- integration/ 需 docker-compose up，用 @pytest.mark.integration 隔离

环境漂移检查（env 治理，2026-08-31）：
session 级 autouse fixture 对账三方键集——代码实际引用的 env 键、
.env.defaults、.env。代码引用但两层 env 均未定义 → 直接 fail（新机
clone 后缺配置的静默故障变成显式失败）；.env 独有且代码从不引用 →
warn（死键，多为改名遗留，如 Sprint 1 时代的 LLM_*）。
"""
import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

DOMAIN_PACKS_DIR = REPO_ROOT / "domain_packs"

# 收集代码 env 引用的文件范围（src / migrations / compose）
_ENV_REF_GLOBS = ("src/**/*.py", "migrations/**/*.py", "docker-compose.yml")
_ENV_KEY_RE = re.compile(
    r"""(?:environ\.get|os\.getenv)\(\s*["']([A-Z][A-Z0-9_]+)["']|"""
    r"""\$\{([A-Z][A-Z0-9_]+)(?::-)"""
)


def _code_env_keys() -> set[str]:
    """扫 src+migrations+compose，收集代码实际引用的 env 键名。"""
    keys: set[str] = set()
    for pattern in _ENV_REF_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if ".venv" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for match in _ENV_KEY_RE.finditer(text):
                keys.add(match.group(1) or match.group(2))
    return keys


def _dotenv_keys(path: Path) -> set[str]:
    """解析 dotenv 文件的键集（跳过注释与空行，不触值）。"""
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


@pytest.fixture(autouse=True, scope="session")
def _check_env_drift():
    """环境漂移对账：缺失键 fail，死键 warn。"""
    defaults_keys = _dotenv_keys(REPO_ROOT / ".env.defaults")
    override_keys = _dotenv_keys(REPO_ROOT / ".env")
    defined = defaults_keys | override_keys

    code_keys = _code_env_keys()
    missing = sorted(code_keys - defined - set(os.environ))
    if missing:
        pytest.fail(
            f"环境漂移：代码引用但 .env.defaults/.env 均未定义（新机 clone 会静默故障）："
            f"{', '.join(missing)}——补进 .env.defaults（非秘密默认值）或 .env（秘密）"
        )

    dead = sorted(override_keys - code_keys - defaults_keys)
    if dead:
        print(
            f"\n[env 漂移警告] .env 中以下键无任何代码引用（可能是改名遗留，请清理）："
            f"{', '.join(dead)}"
        )


def pytest_collection_modifyitems(items):
    """自动给 integration/ 下的测试加 mark，省得手写装饰器。"""
    integration_dir = REPO_ROOT / "tests" / "integration"
    for item in items:
        if integration_dir in Path(item.fspath).resolve().parents:
            item.add_marker("integration")


__all__ = ["DOMAIN_PACKS_DIR", "REPO_ROOT"]
