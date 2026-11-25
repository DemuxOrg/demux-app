"""Agent evals started from /admin/evals.

An admin queues a run (scenarios, repeats). The worker claims it and starts
`python -m eval.agent --job <id>` as its own process, so the eval always runs the agent
code and prompts on disk (the long-lived worker may still hold older code). That process
calls `execute_eval`: it runs the scenario suite (`eval/agent/runner.py`) against the real
model on the synthetic mailboxes in `eval/agent/scenarios/`, writes progress after each
scenario, then the Demux score, its parts, the guardrails and the full report.

Cancelling marks the row; the worker then stops the process. LLM calls are metered like
any other (`llm_calls.phase = "eval"`), billed to the admin who started the run.
"""

import asyncio
import logging
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import ChatModel, LLMError, MeteredLLM, OpenAICompatibleLLM, usage_scope
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.eval import EvalRun, EvalRunStatus
from app.models.user import User

logger = logging.getLogger(__name__)

ACTIVE = (EvalRunStatus.QUEUED, EvalRunStatus.RUNNING)
BACKEND = Path(__file__).resolve().parents[2]
CANCEL_POLL_SECONDS = 5


class EvalCancelled(Exception):
    pass


def scenarios(root: Path | None = None) -> list[dict[str, Any]]:
    """The scenarios an admin can pick: id, prompt, number of steps, vague or not."""
    from eval.agent.runner import SCENARIOS, load_scenarios

    out = []
    for s, _ in load_scenarios(None, root or SCENARIOS):
        out.append(
            {
                "id": s["id"],
                "prompt": s["prompt"],
                "steps": len(s["steps"]),
                "vague": bool((s.get("clarify") or {}).get("should_ask")),
            }
        )
    return out


# ------------------------------------------------------------------ API side


async def create_eval(
    session: AsyncSession, admin: User, repeats: int, scenario_ids: list[str]
) -> EvalRun:
    known = {s["id"] for s in scenarios()}
    unknown = [i for i in scenario_ids if i not in known]
    if unknown:
        raise ValidationError(f"Unknown scenarios: {', '.join(unknown)}.")
    active = await session.scalar(
        select(func.count()).select_from(EvalRun).where(EvalRun.status.in_(ACTIVE))
    )
    if active:
        raise ConflictError("An eval is already running. Wait for it, or cancel it.")
    n = len(scenario_ids) or len(known)
    run = EvalRun(
        created_by=admin.id,
        status=EvalRunStatus.QUEUED,
        scenario_ids=list(scenario_ids),
        repeats=repeats,
        progress_total=n * repeats,
        build_model=settings.BUILD_MODEL,
        sync_model=settings.SYNC_MODEL,
    )
    session.add(run)
    await session.flush()
    return run


async def list_evals(session: AsyncSession, limit: int = 100) -> list[EvalRun]:
    return list(
        await session.scalars(select(EvalRun).order_by(EvalRun.created_at.desc()).limit(limit))
    )


async def get_eval(session: AsyncSession, eval_id: uuid.UUID) -> EvalRun:
    run = await session.get(EvalRun, eval_id)
    if run is None:
        raise NotFoundError("Eval not found.")
    return run


async def cancel_eval(session: AsyncSession, eval_id: uuid.UUID) -> EvalRun:
    run = await get_eval(session, eval_id)
    if run.status not in ACTIVE:
        raise ConflictError("This eval has already finished.")
    run.status = EvalRunStatus.CANCELLED
    run.error = "Cancelled."
    run.finished_at = datetime.now(UTC)
    await session.flush()
    return run


# ------------------------------------------------------------------ worker side


async def claim_next(session: AsyncSession) -> EvalRun | None:
    run = await session.scalar(
        select(EvalRun)
        .where(EvalRun.status == EvalRunStatus.QUEUED)
        .order_by(EvalRun.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if run is None:
        return None
    run.status = EvalRunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    await session.flush()
    return run


async def fail_stale(session: AsyncSession) -> None:
    await session.execute(
        update(EvalRun)
        .where(EvalRun.status == EvalRunStatus.RUNNING)
        .values(
            status=EvalRunStatus.FAILED,
            error="Interrupted (worker restarted).",
            finished_at=func.now(),
        )
    )


async def _status(session_factory, eval_id: uuid.UUID) -> EvalRunStatus | None:
    async with session_factory() as s:
        return await s.scalar(select(EvalRun.status).where(EvalRun.id == eval_id))


async def spawn(eval_id: uuid.UUID, *, session_factory) -> None:
    """Run a claimed eval in its own process; stop it if the eval is cancelled."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "eval.agent", "--job", str(eval_id), cwd=BACKEND
    )
    try:
        while True:
            try:
                await asyncio.wait_for(proc.wait(), timeout=CANCEL_POLL_SECONDS)
                break
            except TimeoutError:
                if await _status(session_factory, eval_id) == EvalRunStatus.CANCELLED:
                    logger.info("eval %s cancelled", eval_id)
                    return
    finally:
        if proc.returncode is None:  # cancelled, or the worker is stopping
            proc.kill()
            await proc.wait()
    # The process records its own outcome; a crash before it could leaves "running".
    async with session_factory() as s:
        await s.execute(
            update(EvalRun)
            .where(EvalRun.id == eval_id, EvalRun.status == EvalRunStatus.RUNNING)
            .values(
                status=EvalRunStatus.FAILED,
                error=f"internal_error: eval process exited with code {proc.returncode}",
                finished_at=func.now(),
            )
        )
        await s.commit()


def _round(v: Any) -> Any:
    """Floats in the stored report, to 4 decimals (it is read by people)."""
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_round(x) for x in v]
    return v


async def execute_eval(
    eval_id: uuid.UUID,
    *,
    session_factory,
    llm: ChatModel | None = None,
    root: Path | None = None,
) -> None:
    """Run a claimed eval in this process and record the outcome on its row."""
    from eval.agent.runner import SCENARIOS, code_version, run_suite

    root = root or SCENARIOS
    async with session_factory() as s:
        run = await s.get(EvalRun, eval_id)
        assert run is not None
        ids, repeats, admin_id = list(run.scenario_ids), run.repeats, run.created_by
        run.status = EvalRunStatus.RUNNING
        run.started_at = run.started_at or datetime.now(UTC)
        run.build_model, run.sync_model = settings.BUILD_MODEL, settings.SYNC_MODEL
        for k, v in code_version(root).items():
            setattr(run, k, v)
        await s.commit()

    cost = 0.0

    async def progress(result: dict[str, Any], done: int, total: int) -> None:
        nonlocal cost
        cost += sum(st["cost_usd"] for st in result["steps"])
        async with session_factory() as s:
            await s.execute(
                update(EvalRun)
                .where(EvalRun.id == eval_id)
                .values(
                    progress_done=done,
                    progress_total=total,
                    cost_usd=Decimal(str(round(cost, 6))),
                )
            )
            await s.commit()
        if await _status(session_factory, eval_id) == EvalRunStatus.CANCELLED:
            raise EvalCancelled()

    values: dict[str, Any] = {"finished_at": datetime.now(UTC)}
    try:
        if llm is None and not settings.llm_api_key:
            raise LLMError("No model API key: set LLM_API_KEY or HF_TOKEN for the worker.")
        with usage_scope(session_factory=session_factory, user_id=admin_id, phase="eval"):
            report = await run_suite(
                MeteredLLM(llm or OpenAICompatibleLLM()),
                ids or None,
                repeats,
                root=root,
                concurrency=settings.EVAL_CONCURRENCY,
                on_result=progress,
            )
        d = report["demux"]
        values |= {
            "status": EvalRunStatus.DONE,
            "score": d["score"],
            "spread": d["spread"],
            "parts": d["parts"],
            "guardrails": _round(report["metrics"]["guardrails"]),
            "report": _round(report),
            "cost_usd": Decimal(str(round(report["metrics"]["total_cost_usd"], 6))),
        }
    except EvalCancelled:
        return  # the row already says cancelled
    except (LLMError, ValueError) as e:
        values |= {"status": EvalRunStatus.FAILED, "error": str(e)[:500]}
    except Exception as e:  # noqa: BLE001 - always leave a final status
        logger.exception("eval %s crashed", eval_id)
        values |= {"status": EvalRunStatus.FAILED, "error": f"internal_error: {type(e).__name__}"}
    values["finished_at"] = datetime.now(UTC)
    async with session_factory() as s:
        await s.execute(
            update(EvalRun)
            .where(EvalRun.id == eval_id, EvalRun.status != EvalRunStatus.CANCELLED)
            .values(**values)
        )
        await s.commit()
    logger.info("eval %s status=%s score=%s", eval_id, values["status"], values.get("score"))
