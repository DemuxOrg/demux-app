"""Checks run inside `write_app` before an app is stored (build spec §7.3).

1. Static rules on the HTML text (size, `function render`, no URLs, no forbidden APIs).
2. Headless smoke test (Playwright Chromium, all network blocked): load shell + app, post
   the data twice, then once more with `{}` on a fresh page. Fails on console errors,
   uncaught exceptions, an empty page, a non-idempotent render, or (when there is data)
   a page showing none of the string values of the first 5 records.

Returns a list of problems; empty means the app passes.
"""

import asyncio
import re
from typing import Any

from app.agent.shell import build_srcdoc

MAX_APP_CHARS = 150_000

_ALLOWED_URLS = (
    "http://www.w3.org/2000/svg",
    "http://www.w3.org/1999/xlink",
    "http://www.w3.org/1999/xhtml",
)

_STATIC_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"<\s*(html|head|body)\b", re.I), "no <html>, <head> or <body> tags"),
    (re.compile(r"\bfetch\s*\("), "fetch() is forbidden"),
    (re.compile(r"XMLHttpRequest"), "XMLHttpRequest is forbidden"),
    (re.compile(r"WebSocket"), "WebSocket is forbidden"),
    (re.compile(r"EventSource"), "EventSource is forbidden"),
    (re.compile(r"sendBeacon"), "navigator.sendBeacon is forbidden"),
    (re.compile(r"localStorage|sessionStorage|indexedDB"), "browser storage is forbidden"),
    (re.compile(r"document\s*\.\s*cookie"), "document.cookie is forbidden"),
    (re.compile(r"window\s*\.\s*open\b"), "window.open is forbidden (use demux.openLink)"),
    (
        re.compile(r"\b(window|document|self|top|parent)\s*\.\s*location\b"),
        "navigation (location) is forbidden",
    ),
    (re.compile(r"(?<![\w.$])location\s*(\.|=|\[)"), "navigation (location) is forbidden"),
    # `window.parent`/`self.top`, or bare `parent.`/`top.` reaching for a window member.
    # A plain local variable named `top` (`top.appendChild(...)`) is fine.
    (
        re.compile(
            r"\b(window|self|globalThis)\s*\.\s*(top|parent)\b"
            r"|(?<![\w.$])(top|parent)\s*\.\s*"
            r"(postMessage|document|window|frames|opener|parent|top|eval|open)\b"
        ),
        "access to the parent page (window.parent / window.top) is forbidden",
    ),
    (re.compile(r"<\s*form\b", re.I), "<form> is forbidden (use buttons and JS handlers)"),
    (re.compile(r"<\s*iframe\b", re.I), "<iframe> is forbidden"),
    (re.compile(r"\bimport\s*\("), "dynamic import() is forbidden"),
    (re.compile(r"<\s*script[^>]*\bsrc\s*=", re.I), "external scripts are forbidden"),
    (re.compile(r"<\s*link\b", re.I), "<link> is forbidden (inline your CSS)"),
    (re.compile(r"@import", re.I), "CSS @import is forbidden"),
    (
        re.compile(r"(?<![\w.$])(alert|confirm|prompt)\s*\("),
        "alert/confirm/prompt are forbidden",
    ),
    (re.compile(r"""(["'(=]\s*)//[\w-]+\.[\w.-]+"""), "protocol-relative URLs are forbidden"),
]
_URL = re.compile(r"(https?:)?//[^\s\"'<>)]*", re.I)
_HTTP = re.compile(r"https?://[^\s\"'<>)]*", re.I)


def static_problems(html: str) -> list[str]:
    problems: list[str] = []
    if len(html) > MAX_APP_CHARS:
        problems.append(f"app is {len(html)} chars; the limit is {MAX_APP_CHARS}")
    if not re.search(r"function\s+render\s*\(|\b(window|globalThis|self)\s*\.\s*render\s*=", html):
        problems.append("the app must define a global `function render(data)`")
    for m in _HTTP.finditer(html):
        if not m.group(0).startswith(_ALLOWED_URLS):
            problems.append(
                "external URLs are forbidden (found one starting "
                f"'{m.group(0)[:30]}'); use inline SVG or data: URIs"
            )
            break
    for pattern, message in _STATIC_RULES:
        if pattern.search(html) and message not in problems:
            problems.append(message)
    return problems


def _strings_of_first_records(data: dict[str, Any], n: int = 5) -> list[str]:
    out: list[str] = []
    count = 0
    for records in data.values():
        if not isinstance(records, dict):
            continue
        for rec in records.values():
            if count >= n:
                return out
            count += 1
            for k, v in rec.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, str) and len(v.strip()) >= 3:
                    out.append(v.strip())
                elif isinstance(v, list):
                    out += [x.strip() for x in v if isinstance(x, str) and len(x.strip()) >= 3]
    return out


_COLLECT_JS = """
() => {
  window.__demux = [];
  window.addEventListener('message', (ev) => {
    if (ev.data && typeof ev.data.type === 'string' && ev.data.type !== 'demux:data') {
      window.__demux.push(ev.data);
    }
  });
}
"""

_POST_JS = """
async (data) => {
  window.postMessage({type: 'demux:data', data: data}, '*');
  await new Promise(r => setTimeout(r, 250));
  return document.body ? document.body.innerText : '';
}
"""


async def _run_page(browser: Any, html: str, data: dict[str, Any], twice: bool) -> dict[str, Any]:
    context = await browser.new_context(java_script_enabled=True)
    requests: list[str] = []

    async def block(route: Any) -> None:
        requests.append(route.request.url)
        await route.abort()

    await context.route("**/*", block)
    page = await context.new_page()
    errors: list[str] = []
    page.on(
        "console",
        lambda msg: (
            errors.append(f"console error: {msg.text[:200]}") if msg.type == "error" else None
        ),
    )
    page.on("pageerror", lambda exc: errors.append(f"uncaught exception: {str(exc)[:200]}"))
    try:
        await page.set_content(build_srcdoc(html), wait_until="load", timeout=10_000)
        await page.evaluate(_COLLECT_JS)
        text1 = await page.evaluate(_POST_JS, data)
        text2 = await page.evaluate(_POST_JS, data) if twice else text1
        bridge = await page.evaluate("() => window.__demux")
    finally:
        await context.close()
    for msg in bridge:
        if msg.get("type") == "demux:error":
            errors.append(f"render error: {str(msg.get('message'))[:200]}")
    return {"errors": errors, "text1": text1 or "", "text2": text2 or "", "requests": requests}


async def smoke_problems(html: str, data: dict[str, Any]) -> list[str]:
    from playwright.async_api import async_playwright

    problems: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            main = await _run_page(browser, html, data, twice=True)
            empty = await _run_page(browser, html, {}, twice=False)
        finally:
            await browser.close()

    seen: set[str] = set()
    for e in main["errors"]:
        if e not in seen:
            seen.add(e)
            problems.append(f"with the current data: {e}")
    for e in empty["errors"]:
        if e not in seen:
            seen.add(e)
            problems.append(f"with empty data {{}}: {e}")
    if main["requests"] or empty["requests"]:
        problems.append("the app tried to make a network request; none are allowed")
    if not main["text2"].strip():
        problems.append("the page shows no visible text after render(data)")
    if not empty["text1"].strip():
        problems.append("the page shows no visible text with empty data (show an empty state)")
    if main["text1"].strip() != main["text2"].strip():
        problems.append(
            "render(data) is not idempotent: calling it twice changed the page "
            "(clear the container and redraw from scratch)"
        )
    strings = _strings_of_first_records(data)
    if strings:
        text = main["text2"].lower()
        if not any(s.lower() in text for s in strings):
            problems.append(
                "the page shows none of the values of the first records; render the records"
            )
    return problems


async def render_text(html: str, data: dict[str, Any]) -> tuple[str, list[str]]:
    """Render an app once in the headless shell; return (visible text, errors). Eval use."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            out = await _run_page(browser, html, data, twice=False)
        finally:
            await browser.close()
    return out["text1"], out["errors"]


_lock = asyncio.Semaphore(2)


async def check_app(html: str, data: dict[str, Any]) -> list[str]:
    problems = static_problems(html)
    if problems:
        return problems
    async with _lock:
        return await smoke_problems(html, data)
