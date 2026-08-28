"""北极星指标计数——结构化日志（Sprint 5a）。

按 Web/API 出口分别计数，一行 JSON。本 Sprint 仅落日志，不读不聚合。
DB 表形态留调度器 Sprint 引入可观测性时再补。
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("pih.metrics")


def log_query(channel: str, filters: dict[str, Any], count: int) -> None:
    """记录一次查询——channel=web|api，filters 为非空字段 dict，count 为返回条数。"""
    logger.info(
        json.dumps(
            {
                "event": "query",
                "channel": channel,
                "filters": filters,
                "count": count,
                "ts": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
        )
    )
