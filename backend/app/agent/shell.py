"""The fixed shell around every generated app: CSP, base stylesheet, bridge script.

The same shell is used by the headless app check and by the frontend iframe (served by
`GET /api/v1/app-shell`), so what passes the check is what the user sees.
"""

CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; font-src data:; form-action 'none'; base-uri 'none'"
)

BASE_CSS = """
:root{--bg:#ffffff;--fg:#111827;--muted:#6b7280;--border:#e5e7eb;--card:#f9fafb;
--accent:#2563eb;--accent-fg:#ffffff;--ok:#16a34a;--warn:#d97706;--bad:#dc2626;
--radius:8px;font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,
"Helvetica Neue",Arial,sans-serif;font-size:14px;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#0b0f17;--fg:#e5e7eb;--muted:#9ca3af;
--border:#1f2937;--card:#111827;--accent:#3b82f6}}
*{box-sizing:border-box}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);line-height:1.45}
h1,h2,h3{margin:0 0 8px;line-height:1.25}h1{font-size:20px}h2{font-size:16px}h3{font-size:14px}
.muted{color:var(--muted)}
.table{width:100%;border-collapse:collapse}
.table th,.table td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--border);
vertical-align:top}
.table th{font-weight:600;color:var(--muted);font-size:12px;text-transform:uppercase;
letter-spacing:.03em;cursor:default}
.table tr:hover td{background:var(--card)}
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
padding:12px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;
background:var(--border);color:var(--fg)}
.badge.ok{background:#dcfce7;color:#166534}.badge.warn{background:#fef3c7;color:#92400e}
.badge.bad{background:#fee2e2;color:#991b1b}
.btn{display:inline-flex;align-items:center;gap:4px;padding:6px 10px;border-radius:6px;
border:1px solid var(--border);background:var(--bg);color:var(--fg);cursor:pointer;
font:inherit}
.btn:hover{border-color:var(--accent)}.btn.primary{background:var(--accent);
color:var(--accent-fg);border-color:var(--accent)}
.link{color:var(--accent);cursor:pointer;background:none;border:none;padding:0;font:inherit}
.input,select{padding:6px 10px;border-radius:6px;border:1px solid var(--border);
background:var(--bg);color:var(--fg);font:inherit}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
.board{display:flex;gap:12px;align-items:flex-start;overflow-x:auto}
.column{flex:0 0 260px;background:var(--card);border:1px solid var(--border);
border-radius:var(--radius);padding:8px}
.column>h3{padding:4px 4px 8px}.column .card{background:var(--bg);margin-bottom:8px}
.stat{display:inline-block;margin-right:24px}.stat b{display:block;font-size:20px}
.empty{padding:40px;text-align:center;color:var(--muted)}
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


def shell_head() -> str:
    return (
        '<meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<style>{BASE_CSS}</style>"
        f"<script>{BRIDGE_JS}</script>"
    )


def build_srcdoc(app_html: str) -> str:
    return f"<!doctype html><html><head>{shell_head()}</head><body>{app_html}</body></html>"
