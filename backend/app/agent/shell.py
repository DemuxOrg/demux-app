"""The fixed shell around every generated app: CSP, fonts, bridge script, and per runtime
the libraries (and, for older apps, Demux's tokens and palettes).

Three runtimes (`app_runtime`):
- v3 (studio apps, frontend/theme.md §10.3): designed by the UI model with their own look.
  The app is a `<script type="text/jsx" data-runtime="v3">` defining `App({ data })`. The
  shell inlines the studio runtime (`kit/studio.js`: React, Recharts, icons, data helpers),
  Tailwind's browser build (`kit/tailwind.js`) and a few embedded fonts; no Demux tokens.
- v2 (kit apps): a `<script type="text/jsx">` that defines `App({ data })` with the
  component kit (`kit/`, built from app-kit/). The shell inlines the kit's CSS and JS; the
  kit compiles the JSX and renders App with React.
- v1 (apps written before the kit): plain HTML + JS defining `render(data)`, styled with
  the base classes below.

The same shell is used by the headless app check and by the frontend iframe (served by
`GET /api/v1/app-shell`), so what passes the check is what the user sees.
"""

import base64
import json
import re
from functools import cache
from pathlib import Path

from app.agent.palettes import CATEGORY, PALETTE_IDS, SERIES_OTHER, palette_css, valid_palette

CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; font-src data:; form-action 'none'; base-uri 'none'"
)

FONTS_DIR = Path(__file__).parent / "fonts"
KIT_DIR = Path(__file__).parent / "kit"


def _font_faces() -> str:
    """Instrument Sans latin 400/500/600 as base64 @font-face (CSP allows data: fonts only).

    Files from @fontsource/instrument-sans (SIL Open Font License, see fonts/OFL.txt).
    """
    faces = []
    for weight in (400, 500, 600):
        path = FONTS_DIR / f"instrument-sans-latin-{weight}-normal.woff2"
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        faces.append(
            "@font-face{font-family:'Instrument Sans';font-style:normal;"
            f"font-weight:{weight};font-display:swap;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
        )
    return "".join(faces)


# Demux tokens for generated apps (frontend/theme.md §10.3). White surfaces; one accent
# (from the workspace's palette, see palettes.py) for selected/updated state; status colours
# only for status. No dark mode, no gradients. The short names (--bg, --fg, --accent, …) are
# kept as aliases so apps written before the rebrand keep working.
TOKENS_CSS = (
    """
:root{
--dmx-font:"Instrument Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
--dmx-ink:#0C1A2E;--dmx-ink-2:#33445C;--dmx-ink-3:#5B6B80;
--dmx-surface:#FFFFFF;--dmx-surface-2:#F4F7FB;--dmx-line:#E6EBF2;--dmx-line-soft:#EDF1F6;
--dmx-tag:#F1F4F8;
--dmx-success-bg:#E4F5EA;--dmx-success:#1D6B37;--dmx-danger-bg:#FDECEA;--dmx-danger:#A8321F;
--dmx-warning-bg:#FFF1E2;--dmx-warning:#8F4405;--dmx-info-bg:#E6F0FD;--dmx-info:#1F5FB8;
--dmx-neutral-bg:#EEF2F7;--dmx-neutral:#33445C;
"""
    + "".join(f"--dmx-cat-{k}:{v};" for k, v in CATEGORY.items())
    + f"--dmx-series-other:{SERIES_OTHER};"
    + """
--dmx-r-tag:6px;--dmx-r-card:12px;--dmx-r-col:16px;--dmx-r-pill:999px;
--bg:var(--dmx-surface);--fg:var(--dmx-ink);--muted:var(--dmx-ink-3);--border:var(--dmx-line);
--card:var(--dmx-surface-2);--accent:var(--dmx-accent);--accent-fg:#FFFFFF;
--ok:var(--dmx-success);--warn:var(--dmx-warning);--bad:var(--dmx-danger);
--radius:var(--dmx-r-card);
font-family:var(--dmx-font);font-size:14px;color-scheme:light;
-webkit-font-smoothing:antialiased}
"""
    + palette_css()
)

# Base classes of v1 apps (v2 apps get the kit's stylesheet instead).
V1_CSS = """
*{box-sizing:border-box}
body{margin:0;padding:24px;background:var(--dmx-surface);color:var(--dmx-ink);line-height:1.45}
::selection{background:var(--dmx-accent-soft);color:var(--dmx-accent-ink)}
:focus-visible{outline:none;box-shadow:0 0 0 3px var(--dmx-accent-ring)}
h1,h2,h3{margin:0 0 10px;color:var(--dmx-ink);text-wrap:balance}
h1{font-size:24px;line-height:1.2;font-weight:600;letter-spacing:-.02em}
h2{font-size:18px;line-height:1.3;font-weight:600;letter-spacing:-.015em}
h3{font-size:15px;line-height:1.35;font-weight:600}
p{text-wrap:pretty}
.muted{color:var(--dmx-ink-3)}
.num,.stat b,.table td.num{font-variant-numeric:tabular-nums}
.table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
.table th,.table td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--dmx-line-soft);
vertical-align:top}
.table th{font-weight:500;color:var(--dmx-ink-3);font-size:13px;white-space:nowrap;
border-bottom-color:var(--dmx-line);cursor:default}
.table tbody tr{transition:background-color .15s cubic-bezier(.2,.8,.2,1)}
.table tbody tr:hover td{background:var(--dmx-surface-2)}
.card{background:var(--dmx-surface);border:1px solid var(--dmx-line);
border-radius:var(--dmx-r-card);padding:12px 14px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.badge{display:inline-flex;align-items:center;gap:6px;height:22px;padding:0 9px;
border-radius:var(--dmx-r-pill);font-size:12px;font-weight:500;white-space:nowrap;
background:var(--dmx-neutral-bg);color:var(--dmx-neutral)}
.badge.ok{background:var(--dmx-success-bg);color:var(--dmx-success)}
.badge.warn{background:var(--dmx-warning-bg);color:var(--dmx-warning)}
.badge.bad{background:var(--dmx-danger-bg);color:var(--dmx-danger)}
.badge.info{background:var(--dmx-info-bg);color:var(--dmx-info)}
.tag{display:inline-block;padding:3px 7px;border-radius:var(--dmx-r-tag);font-size:12px;
background:var(--dmx-tag);color:var(--dmx-ink-2)}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;
background:var(--dmx-cat-blue);flex:none}
.btn{display:inline-flex;align-items:center;gap:6px;height:36px;padding:0 14px;
border-radius:var(--dmx-r-pill);border:1px solid #E3E8F0;background:#F5F7FB;
color:var(--dmx-ink-2);cursor:pointer;font:inherit;font-weight:500;
transition:background-color .15s,color .15s,border-color .15s}
.btn:hover{background:var(--dmx-accent-soft);color:var(--dmx-accent-ink);
border-color:var(--dmx-accent-line)}
.btn.primary,.btn.active,.btn[aria-pressed=true]{background:var(--dmx-accent);color:#FFFFFF;
border-color:var(--dmx-accent)}
.btn.primary:hover{background:var(--dmx-accent-hover);color:#FFFFFF}
.btn:disabled{opacity:.4;cursor:not-allowed}
.link{color:var(--dmx-accent);cursor:pointer;background:none;border:none;padding:0;
font:inherit;font-weight:500}
.link:hover{color:var(--dmx-accent-ink);text-decoration:underline}
.input,select{height:36px;padding:0 12px;border-radius:var(--dmx-r-pill);
border:1px solid var(--dmx-line);background:var(--dmx-surface);color:var(--dmx-ink);
font:inherit;caret-color:var(--dmx-accent)}
.input::placeholder{color:var(--dmx-ink-3)}
.input:focus,select:focus{outline:none;border-color:var(--dmx-accent-line);
box-shadow:0 0 0 3px var(--dmx-accent-ring)}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:16px}
.board{display:flex;gap:12px;align-items:flex-start;overflow-x:auto;padding-bottom:4px}
.column{flex:0 0 272px;display:flex;flex-direction:column;gap:8px;
background:var(--dmx-surface-2);border-radius:var(--dmx-r-col);padding:12px}
.column>h3{display:flex;align-items:center;gap:8px;margin:0 2px 2px;font-size:13px;
font-weight:500;color:var(--dmx-ink-2)}
.column .card{margin:0}
.stat{display:inline-flex;flex-direction:column;gap:2px;margin-right:32px}
.stat b{font-size:24px;line-height:1.2;font-weight:500;letter-spacing:-.02em}
.stat span{font-size:13px;color:var(--dmx-ink-3)}
.updated{background:var(--dmx-accent-tint)!important;border-color:var(--dmx-accent-line)!important;
box-shadow:0 0 0 3px var(--dmx-accent-glow)}
.empty{padding:48px 16px;text-align:center;color:var(--dmx-ink-3)}
"""

BASE_CSS = TOKENS_CSS + V1_CSS

BRIDGE_JS = """
(function(){
  var parentWin = window.parent;
  var PALETTES = __PALETTES__;
  function send(msg){ try { parentWin.postMessage(msg, '*'); } catch (e) {} }
  window.demux = Object.freeze({
    openSource: function(threadId){ send({type:'demux:openSource', threadId: String(threadId)}); },
    openLink: function(url){ send({type:'demux:openLink', url: String(url)}); }
  });
  function draw(data){
    var fn = (typeof render === 'function') ? render : null;
    if (!fn) { send({type:'demux:error', message:'render(data) is not defined'}); return; }
    try { fn(data); send({type:'demux:rendered'}); }
    catch (e) {
      console.error(e);
      send({type:'demux:error', message: String((e && e.message) || e)});
    }
  }
  window.addEventListener('message', function(ev){
    if (ev.source !== parentWin) return;
    var d = ev.data;
    if (!d) return;
    if (d.type === 'demux:palette') {
      if (PALETTES.indexOf(d.palette) >= 0) {
        document.documentElement.setAttribute('data-palette', d.palette);
      }
      return;
    }
    if (d.type !== 'demux:data') return;
    draw(d.data);
  });
  window.addEventListener('error', function(ev){
    send({type:'demux:error', message: String(ev.message || 'Script error')});
  });
  window.addEventListener('unhandledrejection', function(ev){
    send({type:'demux:error', message: String((ev.reason && ev.reason.message) || ev.reason)});
  });
  window.addEventListener('load', function(){ send({type:'demux:ready'}); });
})();
"""


_JSX_SCRIPT = re.compile(r"""<script\b[^>]*\btype\s*=\s*["']text/jsx["']""", re.I)
_STUDIO_SCRIPT = re.compile(r"""<script\b[^>]*\bdata-runtime\s*=\s*["']v3["']""", re.I)


def app_runtime(app_html: str | None) -> str:
    """ "v3" for studio apps, "v2" for kit apps (a <script type="text/jsx">), else "v1"."""
    if not app_html:
        return "v1"
    if _STUDIO_SCRIPT.search(app_html):
        return "v3"
    return "v2" if _JSX_SCRIPT.search(app_html) else "v1"


def studio_app(jsx: str) -> str:
    """The stored HTML of a studio (v3) app from its JSX source."""
    return f'<script type="text/jsx" data-runtime="v3">\n{jsx.strip()}\n</script>'


# Embedded fonts of studio apps (kit/fonts, from @fontsource; SIL Open Font License):
# family, file, weight range, style. studio.md tells the UI model their Tailwind names.
STUDIO_FONTS = [
    ("Inter", "inter.woff2", "100 900", "normal"),
    ("Space Grotesk", "space-grotesk.woff2", "300 700", "normal"),
    ("Fraunces", "fraunces.woff2", "100 900", "normal"),
    ("JetBrains Mono", "jetbrains-mono.woff2", "100 800", "normal"),
    ("Instrument Serif", "instrument-serif.woff2", "400", "normal"),
    ("Instrument Serif", "instrument-serif-italic.woff2", "400", "italic"),
]

# Read by Tailwind's browser build. `dark:` follows a `dark` class only, so the user's
# system setting never flips an app the UI model designed in light colours.
STUDIO_THEME = """
@custom-variant dark (&:where(.dark, .dark *));
@theme {
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-display: "Space Grotesk", "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-serif: "Fraunces", ui-serif, Georgia, serif;
  --font-editorial: "Instrument Serif", "Fraunces", ui-serif, Georgia, serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}
"""


def _studio_font_faces() -> str:
    faces = []
    for family, file, weight, style in STUDIO_FONTS:
        b64 = base64.b64encode((KIT_DIR / "fonts" / file).read_bytes()).decode("ascii")
        faces.append(
            f"@font-face{{font-family:'{family}';font-style:{style};font-weight:{weight};"
            f"font-display:swap;src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
        )
    return "".join(faces)


def _inline_js(name: str) -> str:
    return (KIT_DIR / name).read_text(encoding="utf-8").replace("</script", "<\\/script")


@cache
def _kit() -> tuple[str, str]:
    """The built kit (app-kit/, `make kit`), safe to inline in <script> / <style>."""
    js = (KIT_DIR / "kit.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
    css = (KIT_DIR / "kit.css").read_text(encoding="utf-8").replace("</style", "<\\/style")
    return js, css


@cache
def kit_catalog() -> str:
    """The kit reference (v2 apps)."""
    return (KIT_DIR / "catalog.md").read_text(encoding="utf-8")


@cache
def studio_reference() -> str:
    """The studio runtime reference (v3) the UI model's prompt includes."""
    return (KIT_DIR / "studio.md").read_text(encoding="utf-8")


@cache
def shell_head(runtime: str = "v1") -> str:
    bridge = BRIDGE_JS.replace("__PALETTES__", json.dumps(list(PALETTE_IDS)))
    head = (
        '<meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
    )
    if runtime == "v3":
        return (
            head + f"<style>{_studio_font_faces()}</style>"
            f'<style type="text/tailwindcss">{STUDIO_THEME}</style>'
            f"<script>{bridge}</script><script>{_inline_js('tailwind.js')}</script>"
            f"<script>{_inline_js('studio.js')}</script>"
        )
    if runtime == "v2":
        js, css = _kit()
        return (
            head + f"<style>{_font_faces()}{TOKENS_CSS}{css}</style>"
            f"<script>{bridge}</script><script>{js}</script>"
        )
    return head + f"<style>{_font_faces()}{BASE_CSS}</style><script>{bridge}</script>"


def build_srcdoc(app_html: str, palette: str | None = None) -> str:
    """The full document, as the iframe gets it. The frontend builds the same string (with
    the head for the app's runtime) and sets the palette with a `demux:palette` message."""
    return (
        f'<!doctype html><html data-palette="{valid_palette(palette)}">'
        f"<head>{shell_head(app_runtime(app_html))}</head><body>{app_html}</body></html>"
    )
