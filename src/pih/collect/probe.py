"""信源试抓取（Backlog TASK-1.01.01 AC2——信源注册与试抓取的运营者入口）。

probe 面向「未启用」信源：robots → 列表页 → 前 N 条详情 → 快照存档，
产出结构化 ProbeReport 供 CLI 呈现。与 collect（run.py）的区别：
probe 不受 enabled 门控约束——它正是启用前的验证手段。

细粒度编排（不复用 fetch_list/fetch_detail 的粗粒度入口），使失败原因可辨：
robots 拒绝 / 列表页非 200 / 解析 0 链接 / 详情未产出各自落 note。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from .base import SourceConfig, get_adapter
from .encoding import decode_full
from .httpclient import HttpClient
from .robots import RobotsResult, fetch_robots_ok
from .snapshot import SnapshotMeta, SnapshotStore


@dataclass
class DetailProbeResult:
    """单条详情页试抓取结果。"""

    url: str
    ok: bool
    title: str = ""
    snapshot_id: str = ""
    note: str = ""


@dataclass
class ProbeReport:
    """单源试抓取报告（CLI 呈现的事实源）。"""

    source_id: str
    robots_allowed: bool
    robots_note: str
    robots_invalid: bool = False
    robots_detail: str = ""
    list_ok: bool = False
    list_note: str = ""
    detail_results: list[DetailProbeResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """成功判定：至少一条详情产出（内含 robots 通过 + 列表可解析 + 快照存档）。"""
        return any(r.ok for r in self.detail_results)


class NullSnapshotStore:
    """--no-snapshot 模式的空快照库：不落 MinIO。

    RawItem.snapshot_id 本就是内容指纹（与存储解耦），Null 实现只跳过写入。
    """

    def archive(self, source_id: str, raw_bytes: bytes, meta: SnapshotMeta) -> str:
        return meta.content_sha1

    def exists(self, source_id: str, content_sha1: str) -> bool:
        return False


def _robots_note(robots: RobotsResult) -> str:
    note = robots.note
    if robots.invalid_robots:
        note += "【告警】无效 robots（软 200），按未声明处理，建议人工复核站点行为"
    return note


def probe_source(
    source: SourceConfig,
    http: HttpClient,
    snapshots: SnapshotStore | NullSnapshotStore,
    details: int = 1,
) -> ProbeReport:
    """对单源执行试抓取并产出报告。

    Args:
        source: 目标信源（通常 enabled: false，probe 即启用前验证）
        http: HttpClient（节流/重试已内置）
        snapshots: SnapshotStore；--no-snapshot 场景传 NullSnapshotStore()
        details: 试抓详情条数（默认 1）
    """
    adapter = get_adapter(source, http=http, snapshots=snapshots)  # type: ignore[arg-type]
    robots = fetch_robots_ok(source.list_url, client=http._client)
    report = ProbeReport(
        source_id=source.id,
        robots_allowed=robots.allowed,
        robots_note=_robots_note(robots),
        robots_invalid=robots.invalid_robots,
        robots_detail=robots.detail,
    )
    if not robots.allowed:
        report.list_note = "robots 不允许抓取，未发起列表页请求"
        return report

    try:
        resp = http.get(source.list_url)
    except httpx.HTTPError as exc:
        report.list_note = f"列表页获取失败：{type(exc).__name__}（重试耗尽）"
        return report
    if resp.status_code != 200:
        report.list_note = f"列表页 HTTP {resp.status_code}（4xx 不重试）"
        return report

    text, _ = decode_full(resp.content, resp.headers.get("Content-Type", ""))
    urls = adapter.extract_detail_urls(text, source.list_url)
    if not urls:
        report.list_note = "列表页 200 但解析出 0 条详情链接（站点结构变更或非列表页）"
        return report
    report.list_ok = True
    report.list_note = f"列表页 200，解析出 {len(urls)} 条详情链接"

    for url in urls[:details]:
        try:
            item = adapter.fetch_detail(url, source)
        except Exception as exc:  # 边界工具：快照写入失败等任何异常都记报告不中断
            report.detail_results.append(
                DetailProbeResult(url, False, note=f"抓取异常：{type(exc).__name__}: {exc}")
            )
            continue
        if item is None:
            report.detail_results.append(
                DetailProbeResult(
                    url, False, note="详情页未产出（robots 拒绝 / 非 200 / 软 200 模板页）"
                )
            )
        else:
            report.detail_results.append(
                DetailProbeResult(
                    url, True, title=item.title, snapshot_id=item.snapshot_id,
                    note="详情页产出，快照已存档",
                )
            )
    return report
