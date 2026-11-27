"""Fallback app used when the interface designer fails: a searchable list per record type.

It is a studio app (v3) and passes the same checks as designed apps, so a build always ends
with something the user can look at (and have redesigned by chat).
"""

# ruff: noqa: E501  (the embedded app is JSX, not Python)

from app.agent.shell import studio_app

DEFAULT_APP = studio_app(r"""
const label = (s) => String(s).replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
const show = (v) => (v == null || v === "" ? "—" : Array.isArray(v) ? v.join(", ") : String(v));

function TypeList({ data, type }) {
  const [q, setQ] = useState("");
  const list = records(data, type);
  const fields = [...new Set(list.flatMap((r) => Object.keys(r).filter((k) => k !== "id" && !k.startsWith("_"))))].slice(0, 6);
  const shown = list.filter((r) => !q || JSON.stringify(r).toLowerCase().includes(q.toLowerCase()));
  return (
    <section className="rounded-2xl bg-white ring-1 ring-slate-200 shadow-sm">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-4">
        <h2 className="text-base font-semibold text-slate-900">{label(type)}</h2>
        <span className="text-sm text-slate-500 tabular-nums">{list.length}</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" className="ml-auto h-9 w-48 rounded-full bg-slate-100 px-4 text-sm outline-none focus:ring-2 focus:ring-slate-300" />
      </div>
      <ul className="divide-y divide-slate-100">
        {shown.map((r) => (
          <li key={r.id} className="flex flex-wrap items-start gap-x-6 gap-y-1 px-5 py-3 text-sm">
            {fields.map((f) => (
              <div key={f} className="min-w-[8rem]">
                <div className="text-xs text-slate-500">{label(f)}</div>
                <div className="text-slate-900">{show(r[f])}</div>
              </div>
            ))}
            <button onClick={() => openEmail(r)} className="ml-auto inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-slate-600 hover:bg-slate-100">
              <Icon name="mail" size={14} /> Open email
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function App({ data }) {
  const names = types(data);
  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8 font-sans sm:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        {names.length === 0 ? (
          <div className="py-24 text-center">
            <p className="text-lg font-medium text-slate-900">No records yet</p>
            <p className="mt-1 text-sm text-slate-500">They appear here as matching emails are read.</p>
          </div>
        ) : (
          names.map((t) => <TypeList key={t} data={data} type={t} />)
        )}
      </div>
    </div>
  );
}
""")
