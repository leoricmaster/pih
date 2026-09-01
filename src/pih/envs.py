"""分层环境加载（env 漂移治理，2026-08-31）。

背景：.env 早期从模板复制后从未随 .env.example 演进，跨多轮迭代
漂移 3 代（PG_DSN 缺失 / LLM_* 改名无人读 / PIH_API_TOKEN 缺失），且多机
切换放大漂移面。治理：拆两层——

  .env.defaults  入库，非秘密默认值（clone 即得）
  .env           gitignore，只写秘密与本机覆盖（约 2-5 行）

加载优先级（高 → 低）：真实环境变量 > .env > .env.defaults。
实现即语义：先 load .env，再以 override=False load defaults——
defaults 只能填空缺，永不覆盖已设值，天然满足优先级。

用法（替代裸 load_dotenv()）：
  from pih.envs import load_env
  load_env()
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

DEFAULTS_FILENAME = ".env.defaults"
OVERRIDE_FILENAME = ".env"


def load_env(cwd: Path | None = None) -> None:
    """分层加载 .env + .env.defaults（cwd 默认取当前目录）。

    入口在进程启动早期调用一次即可；重复调用幂等（dotenv 对同文件
    同值不产生副作用，defaults 的 override=False 也不会翻转已设值）。
    """
    base = cwd or Path.cwd()
    load_dotenv(base / OVERRIDE_FILENAME)
    load_dotenv(base / DEFAULTS_FILENAME, override=False)
