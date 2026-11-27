"""App checks: each static rule, and the headless smoke test."""

import pytest

from app.agent.appcheck import check_app, static_problems
from app.agent.default_app import DEFAULT_APP
from app.agent.shell import app_runtime, build_srcdoc, studio_app
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


# ------------------------------------------------------------------ studio apps (v3)

STUDIO_APP = studio_app("""
function App({ data }) {
  const loans = records(data, "loan");
  const [open, setOpen] = useState(null);
  return (
    <div className="min-h-screen bg-[#0b0f19] p-8 font-serif text-slate-100">
      <style>{`@keyframes rise{from{opacity:0}to{opacity:1}}`}</style>
      <h1 className="text-4xl" style={{ color: "#c7d2fe" }}>Loans</h1>
      {loans.length === 0 && <p>No loans yet.</p>}
      {loans.map((l) => (
        <button key={l.id} onClick={() => setOpen(l.id)} className={cx("block", open === l.id && "text-indigo-300")}>
          <Icon name="book-open" /> {l.title} · {l.status}
        </button>
      ))}
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={loans.map((l) => ({ name: l.title, n: 1 }))}><Bar dataKey="n" fill="#a5b4fc" /></BarChart>
      </ResponsiveContainer>
    </div>
  );
}
""")


def test_studio_runtime_is_detected():
    assert app_runtime(STUDIO_APP) == "v3"
    assert app_runtime(KIT_APP) == "v2" and app_runtime(GOOD_APP) == "v1"
    assert app_runtime(DEFAULT_APP) == "v3"


def test_studio_apps_may_style_themselves():
    assert static_problems(STUDIO_APP) == []


@pytest.mark.parametrize(
    "change,problem",
    [
        (("function App(", "function Main("), "function App"),
        (("<h1", "<h1 dangerouslySetInnerHTML={{__html: x}}"), "dangerouslySetInnerHTML"),
        (("function App", "import x from 'y';\nfunction App"), "import"),
        (("const loans", "fetch('/x');\n  const loans"), "fetch"),
        (('"min-h-screen', '"bg-[url(https://evil.example/x.png)] min-h-screen'), "external URLs"),
        (("const loans", "localStorage.x = 1;\n  const loans"), "storage"),
    ],
)
def test_studio_apps_keep_the_security_rules(change, problem):
    app = STUDIO_APP.replace(*change)
    assert any(problem in p for p in static_problems(app)), static_problems(app)


async def test_studio_apps_render_in_the_headless_check():
    assert await check_app(STUDIO_APP, DATA) == []
    broken = STUDIO_APP.replace("<h1", "<h1 {")
    assert any("does not compile" in p for p in await check_app(broken, DATA))


async def test_studio_shell_styles_tailwind_classes_and_embeds_fonts():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(build_srcdoc(STUDIO_APP), wait_until="load")
        await page.evaluate("(d) => window.postMessage({type: 'demux:data', data: d}, '*')", DATA)
        await page.wait_for_timeout(400)
        styles = await page.evaluate(
            """() => {
              const h1 = document.querySelector('h1');
              const root = document.querySelector('#demux-root > div');
              return [getComputedStyle(root).backgroundColor, getComputedStyle(h1).fontFamily,
                      getComputedStyle(h1).fontSize, document.fonts.check('16px Fraunces')];
            }"""
        )
        await browser.close()
    assert styles[0] == "rgb(11, 15, 25)"  # bg-[#0b0f19]
    family = styles[1].split(",")[0].strip('"')
    assert family == "Fraunces" and styles[2] == "36px"  # font-serif text-4xl
    assert styles[3] is True


LIVE_APP = studio_app("""
function App({ data }) {
  const loans = records(data, "loan");
  return (
    <div>
      <CountUp value={loans.length} className="total" />
      {loans.map((l) => (
        <p key={l.id} data-id={l.id} className={cx("row", changedClass("loan", l.id))}>{l.title}</p>
      ))}
    </div>
  );
}
""")


async def _live_page(p, reduced: bool = False):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(reduced_motion="reduce" if reduced else "no-preference")
    page = await ctx.new_page()
    await page.set_content(build_srcdoc(LIVE_APP), wait_until="load")
    return browser, page


SEND = "([d, c]) => window.postMessage({type: 'demux:data', data: d, changed: c}, '*')"
CLASSES = "() => Object.fromEntries([...document.querySelectorAll('.row')].map(e => [e.dataset.id, e.className]))"


async def test_changed_records_are_marked_then_cleared():
    """The page sends the keys it just changed; exactly those rows get demux-new /
    demux-updated, and the marks clear after ~1.6 s (theme.md §10.3)."""
    from playwright.async_api import async_playwright

    first = {"loan": {"a": {"title": "A"}, "b": {"title": "B"}}}
    second = {"loan": {"a": {"title": "A2"}, "b": {"title": "B"}, "c": {"title": "C"}}}
    async with async_playwright() as p:
        browser, page = await _live_page(p)
        await page.evaluate(SEND, [first, ["loan/a", "loan/b"]])  # first data: no marks
        await page.wait_for_timeout(300)
        assert all("demux" not in c for c in (await page.evaluate(CLASSES)).values())
        await page.evaluate(SEND, [second, ["loan/a", "loan/c"]])
        await page.wait_for_timeout(150)
        classes = await page.evaluate(CLASSES)
        total = await page.text_content(".total")
        await page.wait_for_timeout(1900)
        later = await page.evaluate(CLASSES)
        final_total = await page.text_content(".total")
        await browser.close()
    assert "demux-updated" in classes["a"] and "demux-new" in classes["c"]
    assert "demux" not in classes["b"]
    assert total is not None and final_total == "3"
    assert all("demux" not in c for c in later.values())


async def test_reduced_motion_marks_nothing():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser, page = await _live_page(p, reduced=True)
        await page.evaluate(SEND, [{"loan": {"a": {"title": "A"}}}, []])
        await page.wait_for_timeout(200)
        await page.evaluate(
            SEND, [{"loan": {"a": {"title": "A"}, "b": {"title": "B"}}}, ["loan/b"]]
        )
        await page.wait_for_timeout(150)
        classes = await page.evaluate(CLASSES)
        total = await page.text_content(".total")
        await browser.close()
    assert all("demux" not in c for c in classes.values()) and total == "2"


async def test_count_up_passes_through_in_between_values():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser, page = await _live_page(p)
        many = {"loan": {str(i): {"title": str(i)} for i in range(40)}}
        await page.evaluate(SEND, [{"loan": {}}, []])
        await page.wait_for_timeout(200)
        await page.evaluate(SEND, [many, []])
        await page.wait_for_timeout(120)
        midway = int(await page.text_content(".total"))
        await page.wait_for_timeout(600)
        done = int(await page.text_content(".total"))
        await browser.close()
    assert 0 < midway < 40 and done == 40


async def test_preview_app_passes_the_checks():
    assert await check_app(DEFAULT_APP, DATA) == []
