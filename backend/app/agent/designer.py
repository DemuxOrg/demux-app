"""The interface designer (docs/UI_GENERATION_PLAN.md §11).

The UI model (`UI_MODEL`, GLM-5.2 by default) designs the experience and the interface of
every workspace and writes it as a studio (v3) app with its own look. The main agent never
writes interface code: a build hands the designer the facts (request, the user's answers,
the guide, a data sample); an edit hands it the current app and what to change.

One plain chat, no tools, so any model can do it: the answer is one ```jsx block. The app
is checked (appcheck) and the problems go back to the model until it passes or
`max_attempts` is reached. Every call is metered (MeteredLLM, in the caller's phase) and
added to the run's usage, like any other call.
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from app.agent import prompts
from app.agent.appcheck import check_app
from app.agent.context import RunContext
from app.agent.llm import CallOptions, ChatModel, cost_usd, usage_phase
from app.agent.shell import studio_app

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"```[ \t]*([A-Za-z]*)[^\n]*\n(.*?)(?:```|\Z)", re.S)
_SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)
_THINK = re.compile(r"<think>.*?(?:</think>|\Z)", re.S | re.I)
# Imports of what the runtime already provides as globals: harmless, so they are dropped
# rather than sent back as a problem (models add them out of habit).
_GLOBAL_IMPORT = re.compile(
    r"""^[ \t]*import\b[^;\n]*?from\s*["'](?:react|react-dom|react-dom/client|recharts|"""
    r"""lucide-react|clsx)["'];?[ \t]*\n""",
    re.M,
)
_EXPORT_DEFAULT_FN = re.compile(r"^([ \t]*)export\s+default\s+function\b", re.M)
_EXPORT_DEFAULT_NAME = re.compile(r"^[ \t]*export\s+default\s+\w+\s*;?[ \t]*$\n?", re.M)


def extract_app(answer: str | None) -> str | None:
    """The app's JSX from the model's answer, reasoning removed: the largest fenced code
    block (else a <script>, else the whole answer if it defines App), with the habits a
    model brings from normal React projects (imports of the globals, `export default`)
    removed."""
    # Some providers put the model's reasoning, drafts included, inline in the answer.
    text = _THINK.sub("", answer or "")
    blocks = [m.group(2) for m in _FENCE.finditer(text) if "App" in m.group(2)]
    if not blocks:
        blocks = [m.group(1) for m in _SCRIPT.finditer(text) if "App" in m.group(1)]
    if not blocks and re.search(r"function\s+App\s*\(", text):
        blocks = [text]
    if not blocks:
        return None
    code = max(blocks, key=len)
    code = _GLOBAL_IMPORT.sub("", code)
    code = _EXPORT_DEFAULT_FN.sub(r"\1function", code)
    code = _EXPORT_DEFAULT_NAME.sub("", code)
    return code.strip() or None


@dataclass
class Designer:
    llm: ChatModel
    model: str
    options: CallOptions = CallOptions()
    max_attempts: int = 3

    async def design(self, ctx: RunContext, problems: list[str] | None = None) -> list[str]:
        """Design the workspace's app from its facts and save it. With `problems` (the
        current app fails with the real data), the designer fixes the current app instead.
        Returns [] once saved, else the last problems (the app is left unchanged)."""
        s = ctx.state
        if problems and s.app_html:
            brief = prompts.interface_change_input(
                s.name, s.prompt, s.guide, s.data, s.config,
                current_app=s.app_html,
                change="The current app fails these checks with the data above. Fix them:\n- "
                + "\n- ".join(problems),
            )  # fmt: skip
        else:
            brief = prompts.interface_input(s.name, s.prompt, s.guide, s.data, s.config)
        return await self._write(ctx, brief, "Designing the interface")

    async def change(self, ctx: RunContext, change: str, user_message: str = "") -> list[str]:
        """Change the current app as asked (an edit). Same return as design()."""
        s = ctx.state
        brief = prompts.interface_change_input(
            s.name, s.prompt, s.guide, s.data, s.config,
            current_app=s.app_html, change=change, user_message=user_message,
        )  # fmt: skip
        return await self._write(ctx, brief, "Redesigning the interface")

    async def _write(self, ctx: RunContext, brief: str, label: str) -> list[str]:
        await _event(ctx, label)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": prompts.INTERFACE},
            {"role": "user", "content": brief},
        ]
        problems: list[str] = []
        for attempt in range(1, self.max_attempts + 1):
            with usage_phase(ctx.phase):
                reply = await self.llm.chat(self.model, messages, [], options=self.options)
            cost = (
                reply.cost_usd
                if reply.cost_usd is not None
                else cost_usd(
                    reply.model or self.model,
                    reply.input_tokens,
                    reply.output_tokens,
                    reply.cached_input_tokens,
                )
            )
            await ctx.persister.add_usage(reply.input_tokens, reply.output_tokens, cost)
            logger.info(
                "designer run=%s attempt=%s in=%s out=%s ms=%s truncated=%s",
                ctx.run_id,
                attempt,
                reply.input_tokens,
                reply.output_tokens,
                reply.latency_ms,
                reply.truncated,
            )
            code = extract_app(reply.content)
            if reply.truncated:
                problems = [
                    "your answer was cut off at the length limit: write a shorter app "
                    "(well under 700 lines) and return all of it"
                ]
            elif code is None:
                problems = [
                    "no app found: answer with exactly one ```jsx code block defining "
                    "function App({ data })"
                ]
            else:
                html = studio_app(code)
                problems = await check_app(html, ctx.state.data)
                if not problems:
                    ctx.state.app_html = html
                    ctx.app_written = True
                    await ctx.persister.save_app(ctx.state)
                    await _event(ctx, "Interface ready")
                    return []
            if attempt < self.max_attempts:
                await _event(ctx, "Interface check failed, fixing")
                messages.append({"role": "assistant", "content": reply.content or ""})
                messages.append(
                    {
                        "role": "user",
                        "content": "The app was rejected:\n- "
                        + "\n- ".join(problems)
                        + "\n\nFix every problem and return the whole app again, in one "
                        "```jsx block.",
                    }
                )
        return problems


async def _event(ctx: RunContext, label: str) -> None:
    await ctx.persister.add_event(
        {"t": time.time(), "phase": ctx.phase, "tool": "designer", "label": label}
    )


def designer_from_settings(llm: ChatModel) -> Designer:
    from app.core.config import settings

    return Designer(
        llm=llm,
        model=settings.UI_MODEL,
        options=CallOptions(
            max_tokens=settings.UI_MAX_TOKENS,
            timeout_s=settings.UI_CALL_TIMEOUT_S,
            temperature=settings.UI_TEMPERATURE,
            reasoning_effort=settings.UI_REASONING_EFFORT,
            fallback_model=settings.UI_FALLBACK_MODEL,
        ),
        max_attempts=max(1, settings.UI_MAX_ATTEMPTS),
    )
