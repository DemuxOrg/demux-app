"""The fixed shell around every generated app: CSP, fonts, base stylesheet, bridge script.

The same shell is used by the headless app check and by the frontend iframe (served by
`GET /api/v1/app-shell`), so what passes the check is what the user sees.
"""

import base64
from functools import cache
from pathlib import Path

CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; font-src data:; form-action 'none'; base-uri 'none'"
)

FONTS_DIR = Path(__file__).parent / "fonts"


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


# Demux tokens for generated apps (frontend/theme.md §10.3). White surfaces, one accent
# (violet) for selected/updated state, status colours only for status. No dark mode, no
# gradients. The short names (--bg, --fg, --accent, …) are kept as aliases so apps
# written before the rebrand keep working.
BASE_CSS = """
:root{
--dmx-font:"Instrument Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
--dmx-ink:#0C1A2E;--dmx-ink-2:#33445C;--dmx-ink-3:#5B6B80;
--dmx-surface:#FFFFFF;--dmx-surface-2:#F4F7FB;--dmx-line:#E6EBF2;--dmx-line-soft:#EDF1F6;
--dmx-tag:#F1F4F8;
--dmx-accent:#6A3DF0;--dmx-accent-hover:#5A2FDC;--dmx-accent-soft:#EEE9FE;
--dmx-accent-ink:#4B24C9;--dmx-accent-line:#C9BCFB;--dmx-accent-tint:#FBFAFF;
--dmx-success-bg:#E4F5EA;--dmx-success:#1D6B37;--dmx-danger-bg:#FDECEA;--dmx-danger:#A8321F;
--dmx-warning-bg:#FFF1E2;--dmx-warning:#8F4405;--dmx-info-bg:#E6F0FD;--dmx-info:#1F5FB8;
--dmx-neutral-bg:#EEF2F7;--dmx-neutral:#33445C;
--dmx-cat-blue:#5EA7F4;--dmx-cat-lavender:#9A8BF7;--dmx-cat-pink:#E0679A;
--dmx-cat-green:#2FB36B;--dmx-cat-amber:#F5A524;--dmx-cat-purple:#9A7BF7;
--dmx-r-tag:6px;--dmx-r-card:12px;--dmx-r-col:16px;--dmx-r-pill:999px;
--bg:var(--dmx-surface);--fg:var(--dmx-ink);--muted:var(--dmx-ink-3);--border:var(--dmx-line);
--card:var(--dmx-surface-2);--accent:var(--dmx-accent);--accent-fg:#FFFFFF;
--ok:var(--dmx-success);--warn:var(--dmx-warning);--bad:var(--dmx-danger);
--radius:var(--dmx-r-card);
font-family:var(--dmx-font);font-size:14px;color-scheme:light;
-webkit-font-smoothing:antialiased}
*{box-sizing:border-box}
body{margin:0;padding:24px;background:var(--dmx-surface);color:var(--dmx-ink);line-height:1.45}
::selection{background:var(--dmx-accent-soft);color:var(--dmx-accent-ink)}
:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(106,61,240,.22)}
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
.btn:hover{background:var(--dmx-accent-soft);color:var(--dmx-accent-ink);border-color:#DCD2FD}
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
box-shadow:0 0 0 3px rgba(106,61,240,.22)}
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
box-shadow:0 0 0 3px rgba(106,61,240,.08)}
.empty{padding:48px 16px;text-align:center;color:var(--dmx-ink-3)}
"""

BRIDGE_JS = """
(function(){
  var parentWin = window.parent;
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
    if (!d || d.type !== 'demux:data') return;
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


@cache
def shell_head() -> str:
    return (
        '<meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<style>{_font_faces()}{BASE_CSS}</style>"
        f"<script>{BRIDGE_JS}</script>"
    )


def build_srcdoc(app_html: str) -> str:
    return f"<!doctype html><html><head>{shell_head()}</head><body>{app_html}</body></html>"
