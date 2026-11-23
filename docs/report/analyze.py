"""Turn benchmark results into the report's figures, tables and numbers.

    cd backend
    uv run --with matplotlib python ../docs/report/analyze.py eval/agent/runs/bench-main/results.jsonl

Writes `docs/report/figures/*.pdf`, `docs/report/generated/*.tex` and copies the results
to `docs/report/data/results.jsonl`. Everything in the cost section of the report is
computed here, so re-running the benchmark and this script updates the report.
"""

import json
import math
import shutil
import statistics as st
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).parent
FIG = HERE / "figures"
GEN = HERE / "generated"

# Real Gmail runs made by the signed-in user on 2026-11-16, read from the `runs` table
# (metadata only: kind, seconds, tokens, cost, and the thread counts in the event labels).
REAL_BUILDS = [
    {"threads": 60, "wall_s": 22.3, "in": 263019, "out": 5999, "cost": 0.136356},
    {"threads": 56, "wall_s": 19.0, "in": 191233, "out": 4813, "cost": 0.100492},
]
REAL_SYNCS = [
    {"k": 1, "wall_s": 2.2, "in": 8165, "out": 130, "cost": 0.004064},
    {"k": 1, "wall_s": 3.5, "in": 15196, "out": 269, "cost": 0.007645},
]
REAL_EDIT = {"wall_s": 14.1, "in": 102595, "out": 3502, "cost": 0.056673}

# Email volume assumed for the upkeep estimate: new emails per day matching the queries.
UPKEEP = {"low": 2, "mid": 10, "high": 50}
SYNC_SLOTS_PER_DAY = 144  # one sync every 10 minutes

INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#ffffff"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
TIERS = ["low", "mid", "high"]
TIER_NAME = {"low": "Low", "mid": "Mid", "high": "High"}

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8.5,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK2,
        "axes.titlesize": 9.5,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK2,
        "ytick.labelcolor": INK2,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "legend.frameon": False,
        "pdf.fonttype": 42,
    }
)


def pct(values: list[float], p: float) -> float:
    """Percentile by linear interpolation."""
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    i = (len(s) - 1) * p / 100
    lo, hi = math.floor(i), math.ceil(i)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def med(values: list[float]) -> float:
    return st.median(values)


def fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Least-squares line y = a + b x."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx if sxx else 0.0
    return my - b * mx, b


def money(v: float) -> str:
    if v >= 10:
        return f"\\${v:.1f}"
    if v >= 1:
        return f"\\${v:.2f}"
    if v >= 0.1:
        return f"\\${v:.2f}"
    if v >= 0.01:
        return f"\\${v:.3f}"
    return f"\\${v:.4f}"


def k_tokens(v: float) -> str:
    return f"{v / 1000:.0f}k" if v >= 10_000 else f"{v / 1000:.1f}k"


def write(name: str, text: str) -> None:
    (GEN / name).write_text(text.strip() + "\n")


def save(fig, name: str) -> None:
    fig.savefig(FIG / name, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


def main() -> None:
    src = Path(sys.argv[1])
    rows = [json.loads(line) for line in src.read_text().splitlines() if line.strip()]
    # Runs refused because the provider account ran out of credits never started: they
    # say nothing about the agent, so they are left out (and counted in the report).
    no_credit = [r for r in rows if r["error"] and "(402)" in r["error"]]
    rows = [r for r in rows if r not in no_credit]
    FIG.mkdir(exist_ok=True)
    GEN.mkdir(exist_ok=True)
    (HERE / "data").mkdir(exist_ok=True)
    shutil.copy(src, HERE / "data" / "results.jsonl")

    macros: dict[str, str] = {}
    builds = [r for r in rows if r["kind"] == "build"]
    ok_builds = [r for r in builds if not r["error"]]
    tier_builds = {t: [r for r in ok_builds if r.get("tier") == t] for t in TIERS}
    scen_builds = [r for r in ok_builds if r["exp"] == "scenario"]
    syncs = [r for r in rows if r["exp"] == "sync" and not r["error"]]
    scen_syncs = [r for r in rows if r["exp"] == "scenario" and r["kind"] == "sync"]
    edits = [r for r in rows if r["kind"] == "edit"]
    ok_edits = [r for r in edits if not r["error"]]

    # ------------------------------------------------------------ build table
    lines = []
    for t in TIERS:
        rs = tier_builds[t]
        if not rs:
            continue
        cost = [r["cost"] for r in rs]
        wall = [r["wall_s"] for r in rs]
        lines.append(
            f"{TIER_NAME[t]} & {len(rs)} & {med([r['threads_processed'] for r in rs]):.0f} & "
            f"{med([r['messages_processed'] for r in rs]):.0f} & "
            f"{k_tokens(med([r['in'] for r in rs]))} & {k_tokens(med([r['out'] for r in rs]))} & "
            f"{money(med(cost))} & {money(min(cost))}--{money(max(cost))} & "
            f"{med(wall):.0f}\\,s & {min(wall):.0f}--{max(wall):.0f}\\,s \\\\"
        )
        macros[f"build{t}cost"] = money(med(cost))
        macros[f"build{t}costmin"] = money(min(cost))
        macros[f"build{t}costmax"] = money(max(cost))
        macros[f"build{t}wall"] = f"{med(wall):.0f}"
        macros[f"build{t}threads"] = f"{med([r['threads_processed'] for r in rs]):.0f}"
    if scen_builds:
        cost = [r["cost"] for r in scen_builds]
        wall = [r["wall_s"] for r in scen_builds]
        lines.append("\\midrule")
        lines.append(
            f"Eval scenarios & {len(scen_builds)} & "
            f"{med([r['threads_processed'] for r in scen_builds]):.0f} & "
            f"{med([r['messages_processed'] for r in scen_builds]):.0f} & "
            f"{k_tokens(med([r['in'] for r in scen_builds]))} & "
            f"{k_tokens(med([r['out'] for r in scen_builds]))} & "
            f"{money(med(cost))} & {money(min(cost))}--{money(max(cost))} & "
            f"{med(wall):.0f}\\,s & {min(wall):.0f}--{max(wall):.0f}\\,s \\\\"
        )
    lines.append("\\midrule")
    for r in REAL_BUILDS:
        lines.append(
            f"Real Gmail & 1 & {r['threads']} & n/a & {k_tokens(r['in'])} & {k_tokens(r['out'])} & "
            f"{money(r['cost'])} & & {r['wall_s']:.0f}\\,s & \\\\"
        )
    write("tab_build.tex", "\n".join(lines))

    # ------------------------------------------------------------ cost model (per thread)
    syn = [r for t in TIERS for r in tier_builds[t]]
    a, b = fit([r["threads_processed"] for r in syn], [r["cost"] for r in syn])
    macros["fitfixed"] = money(max(a, 0))
    macros["fitperthread"] = money(b)
    macros["fitperthreadcents"] = f"{b * 100:.2f}"
    cap_cost = a + b * 80
    macros["fitcap"] = money(cap_cost)

    # ------------------------------------------------------------ phase table
    lines = []
    for t in TIERS:
        rs = tier_builds[t]
        if not rs:
            continue
        total = med([r["cost"] for r in rs])
        cells = []
        for ph in ("design", "process", "app"):
            c = med([r["phases"].get(ph, {}).get("cost", 0.0) for r in rs])
            calls = med([r["phases"].get(ph, {}).get("calls", 0) for r in rs])
            cells.append(f"{money(c)} ({c / total * 100:.0f}\\%) & {calls:.0f}")
        lines.append(f"{TIER_NAME[t]} & " + " & ".join(cells) + " \\\\")
    write("tab_phase.tex", "\n".join(lines))

    # ------------------------------------------------------------ latency
    all_wall = [r["wall_s"] for r in ok_builds]
    groups = [(TIER_NAME[t] + " volume", [r["wall_s"] for r in tier_builds[t]]) for t in TIERS]
    groups.append(("Eval scenarios", [r["wall_s"] for r in scen_builds]))
    lines = []
    for name, w in [*groups, ("All builds", all_wall)]:
        if not w:
            continue
        if name == "All builds":
            lines.append("\\midrule")
        lines.append(
            f"{name} & {len(w)} & {min(w):.1f} & {pct(w, 10):.1f} & {pct(w, 50):.1f} & "
            f"{pct(w, 90):.1f} & {pct(w, 95):.1f} & {max(w):.1f} \\\\"
        )
    write("tab_latency.tex", "\n".join(lines))
    macros["nbuilds"] = str(len(ok_builds))
    macros["nbuildsall"] = str(len(builds))
    macros["nbuildfail"] = str(len(builds) - len(ok_builds))
    macros["latmedian"] = f"{pct(all_wall, 50):.0f}"
    macros["latpninety"] = f"{pct(all_wall, 90):.0f}"
    macros["latpninetyfive"] = f"{pct(all_wall, 95):.0f}"
    macros["latmin"] = f"{min(all_wall):.0f}"
    macros["latmax"] = f"{max(all_wall):.0f}"
    under30 = sum(1 for w in all_wall if w <= 30)
    under60 = sum(1 for w in all_wall if w <= 60)
    macros["latunderthirty"] = f"{under30 / len(all_wall) * 100:.0f}"
    macros["latundersixty"] = f"{under60 / len(all_wall) * 100:.0f}"
    macros["latundersixtyn"] = str(under60)
    design = [r["design_s"] for r in ok_builds if r.get("design_s")]
    macros["designmedian"] = f"{med(design):.0f}"
    macros["designshare"] = (
        f"{med([r['design_s'] / r['wall_s'] for r in ok_builds if r.get('design_s')]) * 100:.0f}"
    )
    macros["defaultapp"] = str(sum(1 for r in ok_builds if r["default_app"]))
    macros["retries"] = str(sum(r["llm_retries"] for r in rows))
    macros["fallbacks"] = str(sum(r["fallback_calls"] for r in rows))
    macros["nruns"] = str(len(rows))
    macros["nnocredit"] = str(len(no_credit))
    macros["nfailed"] = str(sum(1 for r in rows if r["error"]))
    macros["llmcalls"] = str(sum(r["llm_calls"] for r in rows))

    # histogram of build time
    fig, ax = plt.subplots(figsize=(6.3, 2.7))
    top = max(60, math.ceil(max(all_wall) / 5) * 5 + 5)
    bins = list(range(0, int(top) + 1, 2))
    counts, _, _ = ax.hist(all_wall, bins=bins, color=BLUE, edgecolor=SURFACE, linewidth=1.2)
    ymax = max(counts) * 1.28
    for p, label in ((50, "median"), (90, "90th percentile")):
        v = pct(all_wall, p)
        ax.axvline(v, color=INK2, linewidth=0.9, linestyle=(0, (3, 2)))
        ax.text(
            v + 0.5, ymax * 0.97, f"{label}\n{v:.0f} s", va="top", ha="left", color=INK, fontsize=8
        )
    ax.axvline(60, color=ORANGE, linewidth=1.0)
    ax.text(59.5, ymax * 0.97, "target\n60 s", va="top", ha="right", color=INK, fontsize=8)
    ax.set_ylim(0, ymax)
    ax.set_xlim(0, top)
    ax.set_xlabel("Build time, seconds (2-second bins)")
    ax.set_ylabel("Number of builds")
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax.grid(axis="x", visible=False)
    save(fig, "fig_latency_hist.pdf")

    # per-group dots
    fig, ax = plt.subplots(figsize=(6.3, 2.5))
    names = []
    shown = [(n, w) for n, w in groups if w] + [("Real Gmail", [r["wall_s"] for r in REAL_BUILDS])]
    for i, (name, w) in enumerate(reversed(shown)):
        color = ORANGE if name == "Real Gmail" else BLUE
        offs = [((j * 7919) % 11 - 5) / 28 for j in range(len(w))]
        ax.scatter(
            w, [i + o for o in offs], s=22, color=color, edgecolor=SURFACE, linewidth=0.8, zorder=3
        )
        m = med(w)
        ax.plot([m, m], [i - 0.33, i + 0.33], color=INK, linewidth=1.4, zorder=4)
        ax.text(
            max(w) + 1.2, i, f"median {m:.0f} s  (n={len(w)})", va="center", color=INK2, fontsize=8
        )
        names.append(name)
    ax.set_yticks(range(len(names)), names)
    ax.set_xlim(0, max(top, 60))
    ax.set_ylim(-0.6, len(names) - 0.4)
    ax.set_xlabel("Build time, seconds (one dot per build, bar = median)")
    ax.grid(axis="y", visible=False)
    save(fig, "fig_latency_groups.pdf")

    # ------------------------------------------------------------ cost vs threads
    fig, ax = plt.subplots(figsize=(6.3, 3.0))
    ax.scatter(
        [r["threads_processed"] for r in syn],
        [r["cost"] for r in syn],
        s=24, color=BLUE, edgecolor=SURFACE, linewidth=0.8, zorder=3, label="Synthetic mailboxes",
    )  # fmt: skip
    ax.scatter(
        [r["threads"] for r in REAL_BUILDS],
        [r["cost"] for r in REAL_BUILDS],
        s=46, color=ORANGE, marker="D", edgecolor=SURFACE, linewidth=0.8, zorder=4,
        label="Real Gmail (2 builds)",
    )  # fmt: skip
    xs = [0, 84]
    ax.plot(xs, [a + b * x for x in xs], color=INK2, linewidth=1.0, linestyle=(0, (4, 2)), zorder=2)
    ax.text(
        22,
        0.018,
        f"dashed line: ${max(a, 0):.3f} + {b * 100:.2f} cents per thread",
        color=INK2,
        fontsize=8,
    )
    ax.axvline(80, color=AXIS, linewidth=0.9)
    ax.text(79.3, 0.004, "80-thread cap", ha="right", va="bottom", color=INK2, fontsize=8)
    ax.set_xlim(0, 86)
    ax.set_ylim(0, max(r["cost"] for r in syn) * 1.15)
    ax.set_xlabel("Threads read by the build")
    ax.set_ylabel("Cost of the build, USD")
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:.2f}")
    ax.legend(loc="upper left", fontsize=8, handletextpad=0.3)
    save(fig, "fig_cost_threads.pdf")

    # ------------------------------------------------------------ phase cost bars
    fig, ax = plt.subplots(figsize=(6.3, 2.0))
    phases = [
        ("design", "Design", BLUE),
        ("process", "Reading emails", ORANGE),
        ("app", "Interface", AQUA),
    ]
    present = [t for t in TIERS if tier_builds[t]]
    for i, t in enumerate(reversed(present)):
        left = 0.0
        for key, _name, color in phases:
            c = med([r["phases"].get(key, {}).get("cost", 0.0) for r in tier_builds[t]])
            ax.barh(i, c, left=left, height=0.5, color=color, edgecolor=SURFACE, linewidth=1.6)
            if c > 0.03:
                ax.text(
                    left + c / 2,
                    i,
                    f"${c:.3f}",
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=7.5,
                )
            left += c
        ax.text(left + 0.003, i, f"${left:.3f}", va="center", color=INK, fontsize=8)
    ax.set_yticks(range(len(present)), [TIER_NAME[t] + " volume" for t in reversed(present)])
    ax.set_xlabel("Median cost per build, USD")
    ax.xaxis.set_major_formatter(lambda v, _: f"${v:.2f}")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, ax.get_xlim()[1] * 1.1)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in phases]
    ax.legend(
        handles,
        [n for _, n, _ in phases],
        ncol=3,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        fontsize=8,
    )
    save(fig, "fig_phase_cost.pdf")

    # ------------------------------------------------------------ sync
    by: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in syncs:
        by[(r["tier"], r["k"])].append(r)
    ks = sorted({k for _, k in by})
    lines = []
    sync_fit: dict[str, tuple[float, float]] = {}
    for t in TIERS:
        rs_t = [r for r in syncs if r["tier"] == t]
        if not rs_t:
            continue
        sync_fit[t] = fit([r["messages_processed"] for r in rs_t], [r["cost"] for r in rs_t])
        recs = med([r["records"] for r in rs_t])
        cells = []
        for k in ks:
            rs = by.get((t, k), [])
            cells.append(
                f"{money(med([r['cost'] for r in rs]))} & {med([r['wall_s'] for r in rs]):.0f}\\,s"
                if rs
                else "&"
            )
        lines.append(f"{TIER_NAME[t]} & {recs:.0f} & " + " & ".join(cells) + " \\\\")
    write("tab_sync.tex", "\n".join(lines))
    write("tab_sync_head.tex", " & ".join(f"\\multicolumn{{2}}{{c}}{{{k} new}}" for k in ks))
    macros["synccols"] = "".join("rr" for _ in ks)

    if not ks:
        ks = [0]
    fig, ax = plt.subplots(figsize=(6.3, 2.9))
    for t, color in zip(TIERS, (BLUE, ORANGE, AQUA), strict=True):
        pts = [(k, med([r["cost"] for r in by[(t, k)]])) for k in ks if by.get((t, k))]
        if not pts:
            continue
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, linewidth=1.8, marker="o", markersize=5,
                markeredgecolor=SURFACE, markeredgewidth=0.9, label=f"{TIER_NAME[t]} volume workspace")  # fmt: skip
        ax.text(pts[-1][0] + 0.6, pts[-1][1], TIER_NAME[t], color=INK, va="center", fontsize=8)
    ax.scatter([r["k"] for r in REAL_SYNCS], [r["cost"] for r in REAL_SYNCS], s=40, marker="D", color=INK2,
               edgecolor=SURFACE, linewidth=0.8, zorder=4, label="Real Gmail (2 syncs)")  # fmt: skip
    ax.set_xlabel("New emails in the sync")
    ax.set_ylabel("Cost of the sync, USD (median)")
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:.2f}")
    ax.set_xlim(0, max(ks) + 3)
    ax.set_ylim(0, None)
    ax.legend(loc="upper left", fontsize=8)
    save(fig, "fig_sync_cost.pdf")

    if syncs:
        # sync latency
        sw = [r["wall_s"] for r in syncs]
        macros["syncn"] = str(len(syncs))
        macros["syncwallmedian"] = f"{pct(sw, 50):.0f}"
        macros["syncwallp"] = f"{pct(sw, 90):.0f}"
        one = [r for r in syncs if r["k"] == 1]
        macros["synconecostmin"] = money(min(r["cost"] for r in one))
        macros["synconecostmax"] = money(max(r["cost"] for r in one))
        macros["synconewall"] = f"{med([r['wall_s'] for r in one]):.0f}"

    # ------------------------------------------------------------ upkeep estimate
    lines = []
    for t in TIERS:
        if t not in sync_fit:
            continue
        fixed, per_msg = sync_fit[t]
        fixed = max(fixed, 0.0)
        n = UPKEEP[t]
        slots = SYNC_SLOTS_PER_DAY * (1 - (1 - 1 / SYNC_SLOTS_PER_DAY) ** n)
        spread = 30 * (slots * fixed + n * per_msg)  # emails arrive at random times
        together = 30 * (fixed + n * per_msg)  # all of a day's emails land in one sync
        apart = 30 * n * (fixed + per_msg)  # every email in its own sync
        lines.append(
            f"{TIER_NAME[t]} & {n} & {med([r['records'] for r in syncs if r['tier'] == t]):.0f} & "
            f"{money(fixed)} & {money(per_msg)} & {slots:.1f} & "
            f"\\textbf{{{money(spread)}}} & {money(together)}--{money(apart)} \\\\"
        )
        macros[f"upkeep{t}"] = money(spread)
        macros[f"upkeep{t}lo"] = money(together)
        macros[f"upkeep{t}hi"] = money(apart)
        macros[f"upkeep{t}n"] = str(n)
        macros[f"syncfixed{t}"] = money(fixed)
        macros[f"syncper{t}"] = money(per_msg)
    write("tab_upkeep.tex", "\n".join(lines))

    # ------------------------------------------------------------ edits and scenario syncs
    lines = []
    if ok_edits:
        c, w = [r["cost"] for r in ok_edits], [r["wall_s"] for r in ok_edits]
        lines.append(
            f"Edit by chat (eval scenarios) & {len(ok_edits)} & {money(med(c))} & {money(min(c))}--{money(max(c))} & "
            f"{med(w):.0f}\\,s & {min(w):.0f}--{max(w):.0f}\\,s \\\\"
        )
        macros["editcost"] = money(med(c))
        macros["editwall"] = f"{med(w):.0f}"
        macros["editn"] = str(len(ok_edits))
        macros["editfail"] = str(len(edits) - len(ok_edits))
    lines.append(
        f"Edit by chat (real Gmail) & 1 & {money(REAL_EDIT['cost'])} & & {REAL_EDIT['wall_s']:.0f}\\,s & \\\\"
    )
    ss = [r for r in scen_syncs if not r["error"] and r["llm_calls"]]
    if ss:
        c, w = [r["cost"] for r in ss], [r["wall_s"] for r in ss]
        lines.append(
            f"Sync with new mail (eval scenarios) & {len(ss)} & {money(med(c))} & {money(min(c))}--{money(max(c))} & "
            f"{med(w):.0f}\\,s & {min(w):.0f}--{max(w):.0f}\\,s \\\\"
        )
    for r in REAL_SYNCS:
        lines.append(
            f"Sync, 1 new email (real Gmail) & 1 & {money(r['cost'])} & & {r['wall_s']:.0f}\\,s & \\\\"
        )
    lines.append("Sync with no new mail & & \\$0 & & under 1\\,s & \\\\")
    write("tab_other.tex", "\n".join(lines))

    # ------------------------------------------------------------ thinking on / off
    lines = []
    off = [r for r in tier_builds["mid"]]
    on = []
    if len(sys.argv) > 2:
        extra = [json.loads(x) for x in Path(sys.argv[2]).read_text().splitlines() if x.strip()]
        shutil.copy(sys.argv[2], HERE / "data" / "results_thinking_low.jsonl")
        on = [
            r for r in extra if r["kind"] == "build" and not r["error"] and r.get("tier") == "mid"
        ]
        macros["thinkfail"] = str(sum(1 for r in extra if r["error"]))
    for name, rs in (("Thinking off (default)", off), ("Thinking on, low effort", on)):
        if not rs:
            continue
        w, c = [r["wall_s"] for r in rs], [r["cost"] for r in rs]
        lines.append(
            f"{name} & {len(rs)} & {med(w):.0f}\\,s & {max(w):.0f}\\,s & {money(med(c))} & "
            f"{k_tokens(med([r['out'] for r in rs]))} \\\\"
        )
    if on:
        macros["thinkwall"] = f"{med([r['wall_s'] for r in on]):.0f}"
        macros["thinkmax"] = f"{max(r['wall_s'] for r in on):.0f}"
        macros["thinkcost"] = money(med([r["cost"] for r in on]))
    write("tab_thinking.tex", "\n".join(lines))

    # ------------------------------------------------------------ totals, headline
    total = sum(r["cost"] for r in rows)
    write("benchcost.tex", money(total))
    macros["benchcost"] = money(total)
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=HERE
        ).stdout.strip()
    except OSError:
        commit = ""
    write("commit.tex", commit or "unknown")
    macros["commit"] = commit or "unknown"
    expected = [
        f"{p}{t}{x}" for t in TIERS for p, x in (("build", "cost"), ("build", "wall"), ("upkeep", ""),
                                                  ("syncfixed", ""), ("syncper", ""))
    ] + ["editcost", "thinkwall", "thinkmax", "thinkcost", "syncwallmedian", "synconewall"]  # fmt: skip
    for name in expected:
        macros.setdefault(name, "n/a")
    write(
        "numbers.tex",
        "\n".join(f"\\newcommand{{\\N{k}}}{{{v}}}" for k, v in sorted(macros.items())),
    )

    def tier_line(t: str) -> str:
        return f"{macros.get(f'build{t}cost', 'n/a')} & {macros.get(f'upkeep{t}', 'n/a')}"

    write(
        "headline.tex",
        "\\begin{center}\\small\\renewcommand{\\arraystretch}{1.35}\n"
        "\\begin{tabularx}{\\linewidth}{@{}P{5.2cm}LLL@{}}\n\\toprule\n"
        "& \\textbf{Low volume} & \\textbf{Mid volume} & \\textbf{High volume} \\\\\n\\midrule\n"
        f"Build a workspace (one-off) & {macros.get('buildlowcost', '')} & {macros.get('buildmidcost', '')} & "
        f"{macros.get('buildhighcost', '')} \\\\\n"
        f"Keep it updated (per month) & {macros.get('upkeeplow', '')} & {macros.get('upkeepmid', '')} & "
        f"{macros.get('upkeephigh', '')} \\\\\n"
        f"Build time (median) & {macros.get('buildlowwall', '')}\\,s & {macros.get('buildmidwall', '')}\\,s & "
        f"{macros.get('buildhighwall', '')}\\,s \\\\\n"
        "\\bottomrule\n\\end{tabularx}\\end{center}",
    )
    print(json.dumps(macros, indent=1))


if __name__ == "__main__":
    main()
