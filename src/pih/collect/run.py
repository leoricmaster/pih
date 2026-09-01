"""采集编排与 enabled 门控（TASK-1.01.01 AC2「成功才允许启用」/ TASK-1.01.02 采集入库入口）。

collect_source 是调度器（Backlog TASK-4.01.01，待实现）将消费的正式采集入口：
仅运行 enabled: true 的信源；未启用 → SourceDisabledError（附启用流程指引）。
probe（probe.py）不受门控约束——它是启用前的验证手段。

可选 repository 参数——传入则落库，不传则只产出 RawItem（仅 stdout 摘要，不落库）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .base import SourceConfig, get_adapter
from .httpclient import HttpClient
from .rawitem import RawItem
from .snapshot import SnapshotStore

if TYPE_CHECKING:
    from pih.store.repository import IntelRepository, SaveOutcome

DEFAULT_MAX_ITEMS = 10  # 首跑防爆量：列表通常 10–30 条，节流 2s/请求


class SourceDisabledError(Exception):
    """信源未启用（enabled: false）即尝试正式采集。"""


def collect_source(
    source: SourceConfig,
    http: HttpClient,
    snapshots: SnapshotStore,
    max_items: int = DEFAULT_MAX_ITEMS,
    repository: IntelRepository | None = None,
) -> tuple[list[RawItem], list[SaveOutcome]]:
    """正式采集单源：门控 → 列表页 → 前 max_items 条详情（快照随 fetch_detail 存档）。

    Args:
        repository: 若给定，每条 RawItem 落库，返回 outcomes；None 则不落库（outcomes 为空）。

    Raises:
        SourceDisabledError: source.enabled 为 false。
    """
    if not source.enabled:
        raise SourceDisabledError(
            f"信源 '{source.id}' 未启用（enabled: false）。"
            f"启用流程：运行 pih probe-source {source.id} 试抓取，"
            f"通过后在领域包 YAML 中将该源 enabled 置 true（人是最终环节，工具不改 YAML）。"
        )
    adapter = get_adapter(source, http=http, snapshots=snapshots)
    urls = adapter.fetch_list(source)
    items: list[RawItem] = []
    for url in urls[:max_items]:
        item = adapter.fetch_detail(url, source)
        if item is not None:
            items.append(item)

    outcomes: list[SaveOutcome] = []
    if repository is not None and items:
        outcomes = repository.save_batch(items)
    return items, outcomes

