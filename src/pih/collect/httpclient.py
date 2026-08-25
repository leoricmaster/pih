"""HTTP 客户端封装（架构 §4 采集层 / §8 可靠性）。

统一：声明式 UA、超时、指数退避重试×3（网络错误/5xx 重试，4xx 不重试）、
按源节流（每请求前 sleep，默认 2s，Crawl-Delay 站点可覆盖）。

节流覆盖 robots 检查请求——SPK-1 §3.2.1 遗留 Minor「robots 交错间隔未纳节流」的修复：
调用方对 robots 检查与内容抓取统一走本客户端的节流。
"""
from __future__ import annotations

import time

import httpx

from .robots import UA

DEFAULT_GAP = 2.0  # 默认请求间隔秒（SPK-1：三源均 2s）
DEFAULT_TIMEOUT = 15.0
MAX_RETRIES = 3  # 架构 §8：适配器重试 ×3


class HttpClient:
    """带节流与重试的 HTTP 客户端。

    Args:
        gap_seconds: 同源请求最小间隔（默认 2s；KHL 类 Crawl-Delay 站点传 10）
        timeout: 单请求超时秒
        max_retries: 最大重试次数（指数退避：1s, 2s, 4s）
    """

    def __init__(
        self,
        gap_seconds: float = DEFAULT_GAP,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.gap_seconds = gap_seconds
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(
            headers={"User-Agent": UA},
            timeout=timeout,
            follow_redirects=True,
        )
        self._last_request_at: dict[str, float] = {}  # host → 上次请求时间

    def _throttle(self, host: str) -> None:
        """按 host 节流：距上次请求不足 gap_seconds 则 sleep 补齐。"""
        last = self._last_request_at.get(host)
        if last is not None:
            elapsed = time.monotonic() - last
            if elapsed < self.gap_seconds:
                time.sleep(self.gap_seconds - elapsed)
        self._last_request_at[host] = time.monotonic()

    def get(self, url: str) -> httpx.Response:
        """带节流与重试的 GET。

        网络错误/5xx → 指数退避重试（最多 max_retries 次）；
        4xx → 不重试直接返回（客户端错误，重试无益）。
        """
        from urllib.parse import urlsplit

        host = urlsplit(url).netloc
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle(host)
            try:
                resp = self._client.get(url)
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(2**attempt)  # 1s, 2s, 4s
                    continue
                raise
            if resp.status_code >= 500 and attempt < self.max_retries:
                time.sleep(2**attempt)
                continue
            return resp
        # 理论不可达（重试耗尽在循环内 raise 或 return），兜底
        raise last_exc if last_exc else RuntimeError(f"重试耗尽：{url}")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
