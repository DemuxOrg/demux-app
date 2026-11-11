"""The planner entry point (stage: planning)."""

from pydantic import ValidationError

from app.core.logging import logger
from app.pipeline.email_clean import clean_thread
from app.pipeline.planner.llm import LLMConfig, complete
from app.pipeline.planner.models import PlanResult, Schema, Thread, Usage
from app.pipeline.planner.prompts import SYSTEM_PROMPT, render_user_prompt
from app.pipeline.planner.validate import validate
from app.pipeline.sampling import sample_threads


def plan(prompt: str, threads: list[Thread], config: LLMConfig | None = None) -> PlanResult:
    """Turn the user's `prompt` and the retrieved `threads` into a validated schema.

    Clean -> sample -> call the LLM -> parse -> validate. If validation fails, retry once
    with the errors appended as a user message; if still invalid, `schema` is None.
    Records attempts, token usage, latency and every raw response. `config` defaults to the
    app settings (the benchmark overrides it).
    """
    config = config or LLMConfig.from_settings()
    sampled = sample_threads([clean_thread(t) for t in threads])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": render_user_prompt(prompt, sampled)},
    ]

    usage = Usage()
    latency_ms = 0
    raw: list[str] = []
    errors: list[str] = []
    schema: Schema | None = None
    valid_first_try = False

    for attempt in (1, 2):
        resp = complete(messages, config)
        raw.append(resp.content)
        usage.input_tokens += resp.usage.input_tokens
        usage.output_tokens += resp.usage.output_tokens
        latency_ms += resp.latency_ms
        try:
            parsed = Schema.model_validate_json(resp.content)
            errors = validate(parsed)
        except ValidationError as exc:
            parsed = None
            errors = [
                f"response is not a valid Schema: {err['loc']} {err['msg']}" for err in exc.errors()
            ]
        logger.info("planner attempt=%d mode=%s errors=%d", attempt, resp.mode, len(errors))
        if not errors:
            schema = parsed
            valid_first_try = attempt == 1
            break
        if attempt == 1:
            messages = messages + [
                {"role": "assistant", "content": resp.content},
                {
                    "role": "user",
                    "content": "The schema is invalid. Fix these errors and return the full "
                    "corrected JSON schema object:\n- " + "\n- ".join(errors),
                },
            ]

    return PlanResult(
        schema=schema,
        valid_first_try=valid_first_try,
        attempts=len(raw),
        errors=errors,
        usage=usage,
        latency_ms=latency_ms,
        raw_responses=raw,
    )
