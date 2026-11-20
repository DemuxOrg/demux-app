"""Fallback app used when the app phase fails: one table per record type.

It follows the same contract as generated apps and passes the same checks, so a build
always ends with something the user can look at (and fix by chat).
"""

DEFAULT_APP = r"""
<style>
  .dx-type{margin-bottom:32px}
  .dx-type h2{display:flex;align-items:baseline;gap:8px}
  .dx-type h2 .muted{font-size:13px;font-weight:400;letter-spacing:0}
  .dx-src{white-space:nowrap;text-align:right}
  .dx-q{width:min(320px,100%)}
</style>
<div class="toolbar">
  <input class="input dx-q" id="dx-q" placeholder="Filter…" aria-label="Filter">
</div>
<div id="dx-root"></div>
<script>
var dxQuery = '';
var dxData = {};
document.getElementById('dx-q').addEventListener('input', function (e) {
  dxQuery = e.target.value.toLowerCase();
  render(dxData);
});
function dxText(v) {
  if (v === null || v === undefined || v === '') return '—';
  if (Array.isArray(v)) return v.join(', ');
  return String(v);
}
function dxLabel(k) {
  var t = String(k).replace(/_/g, ' ');
  return t.charAt(0).toUpperCase() + t.slice(1);
}
function dxTone(v) {
  var s = String(v).toLowerCase();
  var ok = /\b(paid|approved|delivered|done|complete|completed|accepted|confirmed|received)\b/;
  if (ok.test(s)) return 'ok';
  if (/\b(overdue|rejected|failed|cancell?ed|declined)\b/.test(s)) return 'bad';
  if (/\b(delayed|waiting|pending|on hold|late)\b/.test(s)) return 'warn';
  if (/\b(in transit|shipped|sent|scheduled|in progress|booked)\b/.test(s)) return 'info';
  return '';
}
function dxCell(td, col, v) {
  var text = dxText(v);
  if (/status|stage|state/i.test(col) && text !== '—') {
    var b = document.createElement('span');
    b.className = ('badge ' + dxTone(text)).trim();
    b.textContent = text;
    td.appendChild(b);
    return;
  }
  if (typeof v === 'number') td.className = 'num';
  td.textContent = text;
}
function render(data) {
  dxData = data || {};
  var root = document.getElementById('dx-root');
  root.textContent = '';
  var types = Object.keys(dxData).filter(function (t) { return t.charAt(0) !== '_'; });
  if (!types.length) {
    var empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'No records yet. New matching emails will appear here.';
    root.appendChild(empty);
    return;
  }
  types.forEach(function (type) {
    var recs = dxData[type] || {};
    var ids = Object.keys(recs);
    var cols = [];
    ids.forEach(function (id) {
      Object.keys(recs[id]).forEach(function (k) {
        if (k.charAt(0) !== '_' && cols.indexOf(k) < 0) cols.push(k);
      });
    });
    var section = document.createElement('section');
    section.className = 'dx-type';
    var h = document.createElement('h2');
    h.textContent = dxLabel(type);
    var count = document.createElement('span');
    count.className = 'muted';
    count.textContent = ids.length + (ids.length === 1 ? ' record' : ' records');
    h.appendChild(count);
    section.appendChild(h);
    var table = document.createElement('table');
    table.className = 'table';
    var head = table.createTHead().insertRow();
    cols.concat(['']).forEach(function (c) {
      var th = document.createElement('th');
      th.textContent = c ? dxLabel(c) : '';
      head.appendChild(th);
    });
    var body = table.createTBody();
    ids.forEach(function (id) {
      var rec = recs[id];
      var hay = cols.map(function (c) { return dxText(rec[c]); }).join(' ').toLowerCase();
      if (dxQuery && hay.indexOf(dxQuery) < 0) return;
      var tr = body.insertRow();
      cols.forEach(function (c) { dxCell(tr.insertCell(), c, rec[c]); });
      var cell = tr.insertCell();
      cell.className = 'dx-src';
      var src = rec._sources || [];
      if (src.length) {
        var b = document.createElement('button');
        b.className = 'link';
        b.textContent = 'Open email';
        b.onclick = function () { demux.openSource(src[src.length - 1].thread_id); };
        cell.appendChild(b);
      }
    });
    section.appendChild(table);
    root.appendChild(section);
  });
}
</script>
"""
