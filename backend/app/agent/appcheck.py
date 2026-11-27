"""Checks run inside `write_app` before an app is stored (build spec §7.3).

1. Static rules on the HTML text (size, `App` for studio and kit apps or `render` for v1
   apps, no URLs, no forbidden APIs; no raw colours in kit and v1 apps, which follow the
   palette; studio apps (v3) bring their own look, so they may set colours and <style>).
2. Headless smoke test (Playwright Chromium, all network blocked): load shell + app, post
   the data twice, then once more with `{}` on a fresh page. Fails on console errors,
   uncaught exceptions, an empty page, a non-idempotent render, or (when there is data)
   a page showing none of the string values of the first 5 records.

Returns a list of problems; empty means the app passes.
"""

import asyncio
import re
from typing import Any

from app.agent.shell import app_runtime, build_srcdoc

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


# Raw colours (frontend/theme.md §10.3): generated code colours only through var(--dmx-*),
# so the palette the user picked always applies. Checked where code sets a colour (CSS
# declarations, style attributes, `.style.x = …`, SVG fill/stroke, a string that is only a
# hex code), not in plain text, where "invoice #0987" is common.
_HEX = re.compile(r"(?<![\w&#])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])")
_COLOR_FN = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\s*\(", re.I)
_NAMED = re.compile(
    r"\b(?:white|black|red|green|blue|yellow|orange|purple|pink|gr[ae]y|brown|navy|teal|"
    r"maroon|olive|lime|aqua|cyan|magenta|fuchsia|silver|gold|indigo|violet|crimson|tomato|"
    r"coral|salmon|beige|ivory|khaki|lavender|turquoise|plum|orchid|tan|"
    r"(?:dark|light|medium|pale)[a-z]+)\b",
    re.I,
)
_COLORISH = (
    "color", "background", "border", "outline", "fill", "stroke", "shadow", "caret",
    "accent", "decoration", "rule",
)  # fmt: skip
_VAR = re.compile(r"var\([^)]*\)")
_DECL = re.compile(r"([\w-]+)\s*:\s*([^;{}<>\n]+)")
_JS_STYLE = re.compile(r"""\.style\.(\w+)\s*=\s*(['"`])([^'"`]*)\2""")
_SVG_ATTR = re.compile(
    r"""\b(fill|stroke|stop-color|flood-color|lighting-color|color)\s*=\s*(['"])([^'"]*)\2""",
    re.I,
)
_SET_ATTR = re.compile(
    r"""setAttribute\(\s*(['"])(fill|stroke|stop-color|color)\1\s*,\s*(['"`])([^'"`]*)\3""",
    re.I,
)
_QUOTED_HEX = re.compile(r"""(['"`])\s*#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\s*\1""")


def _raw_colour(prop: str, value: str) -> str | None:
    """The colour literal in one property value, if any."""
    value = _VAR.sub("", value)
    if m := _HEX.search(value) or _COLOR_FN.search(value):
        return m.group(0)
    if any(k in prop.lower() for k in _COLORISH) and (m := _NAMED.search(value)):
        return m.group(0)
    return None


def colour_problem(html: str) -> str | None:
    found: str | None = None
    for m in _DECL.finditer(html):
        if found := _raw_colour(m.group(1), m.group(2)):
            break
    if not found:
        for m in _JS_STYLE.finditer(html):
            if found := _raw_colour(m.group(1), m.group(3)):
                break
    if not found:
        for m in _SVG_ATTR.finditer(html):
            if found := _raw_colour(m.group(1), m.group(3)):
                break
    if not found:
        for m in _SET_ATTR.finditer(html):
            if found := _raw_colour(m.group(2), m.group(4)):
                break
    if not found and (m := _QUOTED_HEX.search(html)):
        found = m.group(0)[1:-1].strip()
    if not found:
        return None
    return (
        f"raw colour values are forbidden (found '{found[:30]}'): colour only through the "
        "var(--dmx-*) variables, which follow the palette the user picked"
    )


# Kit apps (v2): JSX in <script type="text/jsx"> defining App; styling only via the kit.
_V2_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"dangerouslySetInnerHTML"),
        "dangerouslySetInnerHTML is forbidden (render values as JSX text)",
    ),
    (
        re.compile(r"<\s*style\b", re.I),
        "<style> is forbidden in kit apps: style only through kit components and props",
    ),
    (
        re.compile(r"^\s*(import|export)\s", re.M),
        "import/export are not available: every kit component and helper is a global",
    ),
    (re.compile(r"\binnerHTML\s*="), "innerHTML is forbidden (render values as JSX text)"),
]
_V2_APP = re.compile(r"function\s+App\s*\(|\b(?:const|let|var)\s+App\s*=")

# Studio apps (v3): the same JSX rules, except that they style themselves (a <style> in
# their JSX is fine; plain CSS outside JSX braces does not compile and fails the render).
_V3_RULES = [rule for rule in _V2_RULES if "<style>" not in rule[1]]


def static_problems(html: str) -> list[str]:
    problems: list[str] = []
    if len(html) > MAX_APP_CHARS:
        problems.append(f"app is {len(html)} chars; the limit is {MAX_APP_CHARS}")
    runtime = app_runtime(html)
    if runtime in ("v2", "v3"):
        if not _V2_APP.search(html):
            problems.append("the app must define `function App({ data })` in its JSX script")
        rules = _V3_RULES if runtime == "v3" else _V2_RULES
        problems += [message for pattern, message in rules if pattern.search(html)]
    elif not re.search(
        r"function\s+render\s*\(|\b(window|globalThis|self)\s*\.\s*render\s*=", html
    ):
        problems.append(
            'the app must be one <script type="text/jsx"> defining `function App({ data })` '
            "(or, for an old app, a global `function render(data)`)"
        )
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
    if runtime != "v3" and (colour := colour_problem(html)):
        problems.append(colour)
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
