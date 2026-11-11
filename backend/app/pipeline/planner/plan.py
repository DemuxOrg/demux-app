"""The planner entry point (stage: planning)."""

from app.pipeline.planner.models import PlanResult, Thread


def plan(prompt: str, threads: list[Thread]) -> PlanResult:
    """Turn the user's `prompt` and the retrieved `threads` into a validated schema.

    Clean -> sample -> call the LLM -> parse -> validate. If validation fails, retry once
    with the errors appended as a user message; if still invalid, `schema` is None.
    Records attempts, token usage, latency and every raw response.
    """
    raise NotImplementedError
