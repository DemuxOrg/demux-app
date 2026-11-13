"""Fallback app used when the app phase fails: one table per record type.

It follows the same contract as generated apps and passes the same checks, so a build
always ends with something the user can look at (and fix by chat).
"""

DEFAULT_APP = r"""
<style>
  .dx-type{margin-bottom:24px}
  .dx-type h2{text-transform:capitalize}
  .dx-src{white-space:nowrap}
</style>
<div class="toolbar"><input class="input" id="dx-q" placeholder="Filter…"></div>
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
    h.textContent = type.replace(/_/g, ' ') + ' (' + ids.length + ')';
    section.appendChild(h);
    var table = document.createElement('table');
    table.className = 'table';
    var head = table.createTHead().insertRow();
    cols.concat(['']).forEach(function (c) {
      var th = document.createElement('th');
      th.textContent = c.replace(/_/g, ' ');
      head.appendChild(th);
    });
    var body = table.createTBody();
    ids.forEach(function (id) {
      var rec = recs[id];
      var hay = cols.map(function (c) { return dxText(rec[c]); }).join(' ').toLowerCase();
      if (dxQuery && hay.indexOf(dxQuery) < 0) return;
      var tr = body.insertRow();
      cols.forEach(function (c) { tr.insertCell().textContent = dxText(rec[c]); });
      var cell = tr.insertCell();
      cell.className = 'dx-src';
      var src = rec._sources || [];
      if (src.length) {
        var b = document.createElement('button');
        b.className = 'link';
        b.textContent = 'open email';
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
