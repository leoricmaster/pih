"""metrics.log_query 单测。

验 JSON 一行 + 字段齐全 + 空 filters 合法。
"""
from __future__ import annotations

import json
import logging

from pih.consume.metrics import log_query


def _capture(caplog):
    """捕获 pih.metrics logger 输出。"""
    caplog.set_level(logging.INFO, logger="pih.metrics")
    return caplog


def test_log_query_outputs_json_line(caplog):
    _capture(caplog)
    log_query("web", {"subject": "三一", "event_type": "新品发布"}, 5)

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].message)

    assert payload["event"] == "query"
    assert payload["channel"] == "web"
    assert payload["filters"] == {"subject": "三一", "event_type": "新品发布"}
    assert payload["count"] == 5
    assert "ts" in payload


def test_log_query_api_channel(caplog):
    _capture(caplog)
    log_query("api", {"id": 42}, 1)

    payload = json.loads(caplog.records[0].message)
    assert payload["channel"] == "api"
    assert payload["filters"] == {"id": 42}
    assert payload["count"] == 1


def test_log_query_empty_filters(caplog):
    _capture(caplog)
    log_query("web", {}, 0)

    payload = json.loads(caplog.records[0].message)
    assert payload["filters"] == {}
    assert payload["count"] == 0


def test_log_query_chinese_not_escaped(caplog):
    """ensure_ascii=False——中文应原样输出而非 \\u 转义。"""
    _capture(caplog)
    log_query("web", {"subject": "三一"}, 1)

    assert "三一" in caplog.records[0].message
    assert "\\u" not in caplog.records[0].message
