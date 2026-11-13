"""App checks: each static rule, and the headless smoke test."""

import pytest

from app.agent.appcheck import check_app, static_problems
from app.agent.default_app import DEFAULT_APP
from tests.helpers import GOOD_APP

DATA = {"loan": {"dune-1": {"title": "Dune", "status": "borrowed", "_sources": [{"message_id": "a", "thread_id": "18c0aa00bb11cc22"}]}}}


@pytest.mark.parametrize(
    "snippet,problem",
    [
        ("<html></html>", "<html>"),
        ("fetch('/x')", "fetch"),
        ("new XMLHttpRequest()", "XMLHttpRequest"),
        ("new WebSocket('x')", "WebSocket"),
        ("localStorage.x=1", "storage"),
        ("document.cookie", "cookie"),
        ("window.open('x')", "window.open"),
        ("location.href='x'", "location"),
        ("window.location='x'", "location"),
        ("parent.document", "parent"),
        ("<form></form>", "<form>"),
        ("<iframe></iframe>", "<iframe>"),
        ("import('x')", "import"),
        ("<img src='https://evil.example/x.png'>", "external URLs"),
        ("<img src='//evil.example/x.png'>", "protocol-relative"),
        ("alert('x')", "alert"),
        ("<link rel=stylesheet>", "<link>"),
    ],
)
def test_static_rules(snippet, problem):
    problems = static_problems(GOOD_APP + snippet)
    assert any(problem in p for p in problems), problems


def test_static_allows_svg_namespace_and_field_names():
    html = GOOD_APP + "<script>document.createElementNS('http://www.w3.org/2000/svg','svg'); var x = rec.location.trim(); r.parent;</script>"
    assert static_problems(html) == []


def test_render_required():
    assert any("function render" in p for p in static_problems("<p>hi</p>"))


async def test_good_app_and_default_app_pass():
    assert await check_app(GOOD_APP, DATA) == []
    assert await check_app(DEFAULT_APP, DATA) == []


async def test_throwing_render_is_caught():
    html = "<div id=r></div><script>function render(d){ throw new Error('boom'); }</script>"
    problems = await check_app(html, DATA)
    assert any("boom" in p for p in problems)


async def test_empty_page_is_caught():
    html = "<div id=r></div><script>function render(d){}</script>"
    problems = await check_app(html, DATA)
    assert any("no visible text" in p for p in problems)


async def test_non_idempotent_render_is_caught():
    html = "<div id=r></div><script>function render(d){ var p=document.createElement('p'); p.textContent='Dune'; document.getElementById('r').appendChild(p); }</script>"
    problems = await check_app(html, DATA)
    assert any("idempotent" in p for p in problems)


async def test_missing_values_are_caught():
    html = "<div id=r></div><script>function render(d){ document.getElementById('r').textContent='Hello'; }</script>"
    problems = await check_app(html, DATA)
    assert any("none of the values" in p for p in problems)


async def test_crash_on_empty_data_is_caught():
    html = "<div id=r></div><script>function render(d){ document.getElementById('r').textContent = d.loan['dune-1'].title; }</script>"
    problems = await check_app(html, DATA)
    assert any("empty data" in p for p in problems)
