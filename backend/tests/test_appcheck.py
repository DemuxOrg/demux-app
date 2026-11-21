"""App checks: each static rule, and the headless smoke test."""

import pytest

from app.agent.appcheck import check_app, static_problems
from app.agent.default_app import DEFAULT_APP
from tests.helpers import GOOD_APP

DATA = {
    "loan": {
        "dune-1": {
            "title": "Dune",
            "status": "borrowed",
            "_sources": [{"message_id": "a", "thread_id": "18c0aa00bb11cc22"}],
        }
    }
}


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
        ("window.top.postMessage(1,'*')", "parent"),
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


@pytest.mark.parametrize(
    "snippet",
    [
        "<style>.x{color:#fff}</style>",
        "<style>.x{border:1px solid #E6EBF2}</style>",
        "<style>:root{--brand:#6a3df0}</style>",
        '<div style="background: rgb(0,0,0)">x</div>',
        "<style>.x{background:linear-gradient(90deg,var(--dmx-accent),hsl(0 0% 0%))}</style>",
        "<script>el.style.color = 'red'</script>",
        "<script>el.style.borderColor='lightgray'</script>",
        '<svg><rect fill="#abc"/></svg>',
        "<script>x.setAttribute('stroke','black')</script>",
        "<script>var accent = '#6A3DF0';</script>",
        "<script>var tones = { color: 'green' };</script>",
    ],
)
def test_static_rejects_raw_colours(snippet):
    problems = static_problems(GOOD_APP + snippet)
    assert any("raw colour" in p for p in problems), problems


def test_static_allows_variables_ids_and_hashes_in_text():
    html = GOOD_APP + (
        "<style>.x{color:var(--dmx-cat-green);fill:none;border-color:transparent;"
        "transition:background-color .15s;text-decoration:underline}"
        "#feed{display:none} #dx-root .a{color:var(--dmx-ink)}</style>"
        '<svg><path fill="currentColor" stroke="none" style="fill:var(--dmx-series-2)"/></svg>'
        "<script>document.getElementById('add-btn'); var t = 'Invoice #0987';"
        " var label = 'Black Friday';</script>"
    )
    assert static_problems(html) == []
    assert static_problems(DEFAULT_APP) == []


def test_static_allows_svg_namespace_and_field_names():
    html = (
        GOOD_APP
        + "<script>document.createElementNS('http://www.w3.org/2000/svg','svg'); var x = rec.location.trim(); r.parent;"
        + "const top = document.createElement('div'); top.appendChild(x);</script>"
    )
    assert static_problems(html) == []


def test_render_required():
    assert any("function App" in p for p in static_problems("<p>hi</p>"))
    assigned = GOOD_APP.replace("function render(", "window.render = function (")
    assert assigned != GOOD_APP and static_problems(assigned) == []


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


# ------------------------------------------------------------------ kit apps (v2)

KIT_APP = """
<script type="text/jsx">
function App({ data }) {
  const loans = records(data, "loan");
  return (
    <Page title="Loans">
      <DataTable records={loans} columns={["title", "status"]} />
    </Page>
  );
}
</script>
"""


def test_kit_app_passes_static_rules():
    assert static_problems(KIT_APP) == []
    assert static_problems(DEFAULT_APP) == []


@pytest.mark.parametrize(
    "app,problem",
    [
        (KIT_APP.replace("function App(", "function Main("), "function App"),
        (KIT_APP.replace("<Page", "<div dangerouslySetInnerHTML={{__html: x}} /><Page"),
         "dangerouslySetInnerHTML"),
        (KIT_APP + "<style>.x{margin:0}</style>", "<style>"),
        (KIT_APP.replace("function App", "import x from 'y';\nfunction App"), "import"),
        (KIT_APP.replace("<Page", '<Page style={{ color: "red" }}'), "raw colour"),
    ],
)  # fmt: skip
def test_kit_app_static_rules(app, problem):
    assert any(problem in p for p in static_problems(app)), static_problems(app)


async def test_kit_apps_render_in_the_headless_check():
    from app.agent.gallery import GALLERY_APP, sample_data

    assert await check_app(KIT_APP, DATA) == []
    assert await check_app(GALLERY_APP, sample_data()) == []
    broken = KIT_APP.replace("<DataTable", "<DataTable {")
    problems = await check_app(broken, DATA)
    assert any("does not compile" in p for p in problems), problems
    crashing = KIT_APP.replace('records(data, "loan")', "data.loan.missing.x")
    problems = await check_app(crashing, DATA)
    assert any("render error" in p for p in problems), problems
