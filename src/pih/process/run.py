"""ProcessRunner：库中 pending 条目 → LangGraph 图 → 写回。

职责：
- list_pending 取条目（reliability 随行）；
- 逐条构造初始 state（text 在场契约：prepare_text 产物）；
- 图结果映射 ProcessResult 写回——extracted（Admiralty 拼装
  reliability + credibility）/ filtered_out / needs_manual；
- extracted 条目挂事件聚类（TASK-1.02.01，在线增量）；
- 汇总统计与 token 用量（成本可观测，架构 §9.2；token 记在
  ProcessResult.meta，run() 聚合进 RunnerStats）。

错误边界：单条写库失败不阻塞其余条目（架构 §8 容错口径）；
事件聚类失败不阻塞主流程——log warning，可由 `pih cluster --backfill` 补；
LLM 配置缺失在构造阶段快速失败（AC8，先于取条目，不产生半写状态）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pih.process.event import EventService
from pih.process.extraction import is_placeholder_subject
from pih.process.graph import ChatFn, ItemState, build_graph
from pih.process.textprep import prepare_text
from pih.store.event_repository import EventRepository
from pih.store.repository import (
    STATUS_EXTRACTED,
    STATUS_FILTERED_OUT,
    STATUS_NEEDS_MANUAL,
    IntelRecord,
    IntelRepository,
    ProcessResult,
)


@dataclass
class RunnerStats:
    """单次批处理统计（CLI 输出与测试断言口径一致）。"""

    total: int = 0
    extracted: int = 0
    filtered_out: int = 0
    needs_manual: int = 0
    failed: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    details: list[str] = field(default_factory=list)

    def summary_line(self) -> str:
        return (
            f"处理 {self.total} 条 → 抽取成功 {self.extracted} / "
            f"粗筛丢弃 {self.filtered_out} / 待人工 {self.needs_manual} / "
            f"失败 {self.failed}"
        )

    def token_line(self) -> str:
        return (
            f"token 用量：prompt {self.prompt_tokens:,} / "
            f"completion {self.completion_tokens:,}"
        )


def assemble_admiralty(reliability: str, credibility: str) -> str:
    """Admiralty 码 = 来源可靠性（信源继承）+ 信息可信度（LLM 评级）。

    架构 §6.2：如 B2 = B（source.reliability）× 2（抽取输出信息可信度）。
    """
    return f"{reliability}{credibility}"


class ProcessRunner:
    """离线批处理入口（pih process 背后）。"""

    def __init__(
        self,
        repository: IntelRepository,
        pack: dict,
        chat: ChatFn | None = None,
        event_repo: EventRepository | None = None,
    ):
        # chat=None 时构造真实客户端：LLM 配置缺失在此抛 LLMConfigError
        # （AC8 快速失败，先于取条目，不产生半写状态）。
        self._graph = build_graph(pack, chat=chat)
        self._repo = repository
        self._pack = pack
        # 事件聚类 store 层：默认从 IntelRepository 的 pool 构造（测试可注入 fake）
        if event_repo is None:
            event_repo = EventRepository(repository._pool)
        self._events = EventService(event_repo, repository, pack)

    def run(self, source_id: str | None = None, limit: int = 20) -> RunnerStats:
        records = self._repo.list_pending(source_id=source_id, limit=limit)
        stats = RunnerStats(total=len(records))
        for rec in records:
            result, detail = self._process_one(rec)
            stats.details.append(detail)
            if result.meta:
                stats.prompt_tokens += result.meta.get("prompt_tokens", 0)
                stats.completion_tokens += result.meta.get("completion_tokens", 0)
            try:
                self._repo.write_process_result(rec.id, result)
            except Exception as exc:  # noqa: BLE001 单条写库失败不阻塞其余条目
                stats.failed += 1
                stats.details.append(f"[{rec.id}] ✗ 写库失败：{exc}")
                continue
            if result.status == STATUS_EXTRACTED:
                stats.extracted += 1
                # 事件聚类（TASK-1.02.01）：extracted 写库成功后挂事件。
                # 失败不阻塞——warning 入 stats.details，可由 cluster --backfill 补。
                try:
                    outcome = self._events.cluster(rec.id)
                    if outcome is not None:
                        stats.details.append(f"[{rec.id}] ⋄ 挂入事件 #{outcome.event_id}")
                except Exception as exc:  # noqa: BLE001 聚类失败不阻塞主流程
                    stats.details.append(f"[{rec.id}] ⚠ 事件聚类失败：{exc}")
            elif result.status == STATUS_FILTERED_OUT:
                stats.filtered_out += 1
            else:
                stats.needs_manual += 1
        return stats

    def _process_one(self, rec: IntelRecord) -> tuple[ProcessResult, str]:
        """单条：构态 → 图 → 映射 ProcessResult + 人读详情行。"""
        state: ItemState = {"intel_id": rec.id, "text": prepare_text(rec.raw_html)}
        try:
            final = self._graph.invoke(state)
        except Exception as exc:  # noqa: BLE001 图级意外异常（含配置类）→ 待人工
            return (
                ProcessResult(status=STATUS_NEEDS_MANUAL, error=f"graph:{exc}"),
                f"[{rec.id}] ✗ 图执行异常：{exc}",
            )

        meta = {
            "api_retries": final.get("api_retries", 0),
            "validate_rounds": final.get("validate_rounds", 0),
            "node_timings_ms": final.get("node_timings_ms", {}),
            "prompt_tokens": final.get("prompt_tokens", 0),
            "completion_tokens": final.get("completion_tokens", 0),
        }

        if not final.get("kept", True):
            reason = "粗筛判定与领域无关"
            return (
                ProcessResult(status=STATUS_FILTERED_OUT, error=reason, meta=meta),
                f"[{rec.id}] ⊘ filtered_out（{reason}）",
            )

        extraction = final.get("extraction")
        if extraction is None:
            reason = final.get("failure") or "schema 校验未通过"
            return (
                ProcessResult(status=STATUS_NEEDS_MANUAL, error=reason, meta=meta),
                f"[{rec.id}] ✗ needs_manual（{reason}）",
            )

        admiralty = assemble_admiralty(rec.source_reliability or "?", extraction.credibility)
        if is_placeholder_subject(extraction.subject):
            # 后验质量门（TASK-1.02.01 AC3）：主体占位值不算抽取成功——结构化字段保留
            # 供人工复核，状态降 needs_manual（列表不稀释正常情报）
            reason = f"后验质量门：主体为占位值「{extraction.subject}」"
            return (
                ProcessResult(
                    status=STATUS_NEEDS_MANUAL,
                    subject=extraction.subject,
                    event_type=extraction.event_type,
                    facts=extraction.facts,
                    inferences=extraction.inferences,
                    tags=extraction.tags,
                    quant_params=extraction.quant_params,
                    admiralty_code=admiralty,
                    error=reason,
                    meta=meta,
                ),
                f"[{rec.id}] ⚠ needs_manual（{reason}）",
            )
        return (
            ProcessResult(
                status=STATUS_EXTRACTED,
                subject=extraction.subject,
                event_type=extraction.event_type,
                facts=extraction.facts,
                inferences=extraction.inferences,
                tags=extraction.tags,
                quant_params=extraction.quant_params,
                admiralty_code=admiralty,
                meta=meta,
            ),
            (
                f"[{rec.id}] ✓ extracted [{admiralty}] "
                f"{extraction.subject} / {extraction.event_type}"
            ),
        )
