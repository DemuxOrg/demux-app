"""Kit gallery: every block on sample data, through the real shell (dev tool and test
fixture). Neutral domain (a library), like the prompt examples.

    uv run python -m app.agent.gallery out.html [palette]

Open out.html in a browser to review the kit's look in a palette.
"""

# ruff: noqa: E501  (the embedded app is JSX, not Python)

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.agent.shell import build_srcdoc


def _d(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def sample_data() -> dict[str, Any]:
    rows = [
        ("dune", "Dune", "Frank Herbert", "Central", -20, 2, "borrowed", None),
        ("piranesi", "Piranesi", "Susanna Clarke", "Central", -30, -3, "overdue", 1.5),
        ("circe", "Circe", "Madeline Miller", "Riverside", -10, 11, "renewed", None),
        ("klara", "Klara and the Sun", "Kazuo Ishiguro", "Riverside", -45, -15, "returned", None),
        ("hail-mary", "Project Hail Mary", "Andy Weir", "Central", -5, 16, "borrowed", None),
        ("normal-people", "Normal People", "Sally Rooney", "North", -60, -32, "returned", 3.0),
        ("the-overstory", "The Overstory", "Richard Powers", "North", -2, 19, "borrowed", None),
    ]
    loans = {
        slug: {
            "title": title,
            "author": author,
            "branch": branch,
            "checked_out": _d(out),
            "due_date": _d(due),
            "status": status,
            "fine_amount": fine,
            "fine_currency": "EUR" if fine is not None else None,
            "_sources": [{"message_id": f"m-{slug}", "thread_id": "18c0aa00bb11cc22"}],
            "_updated_at": f"{_d(-1)}T09:00:00Z",
        }
        for slug, title, author, branch, out, due, status, fine in rows
    }
    return {"loan": loans}


GALLERY_APP = r"""
<script type="text/jsx">
function App({ data }) {
  const loans = records(data, "loan");
  const { filtered, bar } = useFilters(loans, { search: ["title", "author"], facets: ["branch", "status"] });
  const overdue = loans.filter((l) => l.status === "overdue").length;
  const card = { title: "title", subtitle: "author", meta: [{ field: "due_date", label: "Due", format: "relative" }, "branch"], badge: "status" };
  return (
    <Page title="Library loans" description="Every block of the kit on sample data">
      <StatRow stats={[
        { label: "On loan", value: loans.filter((l) => l.status !== "returned").length },
        { label: "Overdue", value: overdue, tone: overdue ? "danger" : "neutral", hint: overdue ? "Return these first" : undefined },
        { label: "Fines", value: sumBy(loans, "fine_amount"), format: "money", currency: "EUR" },
        { label: "Branches", value: uniq(loans, "branch").length },
      ]} />
      <ViewTabs toolbar={bar} views={[
        { id: "board", label: "Board", content: <Board records={filtered} groupBy="status" columns={["borrowed", "renewed", "overdue", "returned"]} card={card} /> },
        { id: "table", label: "Table", content: <DataTable records={filtered} columns={["title", "author", "branch", { field: "due_date", format: "date" }, "status", "fine_amount"]} /> },
        { id: "timeline", label: "Due dates", content: <Timeline records={filtered} date="due_date" title="title" subtitle="author" badge="status" /> },
        { id: "calendar", label: "Calendar", content: <Calendar records={filtered} date="due_date" title="title" badge="status" /> },
        { id: "gallery", label: "Cards", content: <Gallery records={filtered} card={card} /> },
        { id: "list", label: "List", content: <ListDetail records={filtered} item={{ title: "title", subtitle: "author", badge: "status" }} /> },
      ]} />
      <Dashboard charts={[
        { type: "bar", title: "Loans per branch", data: countBy(loans, "branch") },
        { type: "donut", title: "By status", data: countBy(loans, "status") },
        { type: "line", title: "Checked out per month", data: byMonth(loans, "checked_out") },
        { type: "hbar", title: "Fines per branch", data: aggregate(loans, { by: "branch", value: "fine_amount" }), format: "money", currency: "EUR" },
      ]} />
    </Page>
  );
}
</script>
"""


def gallery_page(palette: str = "violet", app_html: str = GALLERY_APP) -> str:
    """A standalone page: the shell, the app, and the sample data posted on load."""
    post = (
        "<script>window.addEventListener('load',function(){window.postMessage("
        "{type:'demux:data',data:"
        + json.dumps(sample_data()).replace("</", "<\\/")
        + "},'*')});</script>"
    )
    return build_srcdoc(app_html, palette).replace("</body>", post + "</body>")


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "gallery.html")
    out.write_text(gallery_page(sys.argv[2] if len(sys.argv) > 2 else "violet"), encoding="utf-8")
    print(f"wrote {out}")
