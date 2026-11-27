"""Does the prompt already say how the workspace should look? (app/agent/look.py)"""

import pytest

from app.agent.context import MemoryPersister, RunContext, WorkspaceState
from app.agent.flows import collect_look
from app.agent.look import LOOK_DECIDE, look_from_prompt
from app.agent.prompts import interface_input
from app.mail.fake import FakeMailbox
from tests.helpers import SMALL_MAILBOX, dt


@pytest.mark.parametrize(
    ("prompt", "named"),
    [
        ("track bills in teal", True),
        ("invoices with a blue theme", True),
        ("purple accents", True),
        ("my orders, dark mode please", True),
        ("a minimal look for my job applications", True),
        ("warm colours for my travel bookings", True),
        ("Blue Bottle coffee orders", False),
        ("red flags in my contracts", False),
        ("black friday orders", False),
        ("green energy bills", False),
        ("track what looks like spam", False),
        ("unpaid invoices and who I owe", False),
    ],
)
def test_look_from_prompt(prompt, named):
    assert look_from_prompt(prompt) is named


def _ctx(setup: dict) -> tuple[RunContext, MemoryPersister]:
    p = MemoryPersister()
    st = WorkspaceState(prompt="p")
    p.state = st
    p.setup.update(setup)
    ctx = RunContext(
        state=st,
        mailbox=FakeMailbox.from_file(SMALL_MAILBOX, now=dt("2026-10-30T00:00:00Z")),
        persister=p,
        run_id="t",
    )
    return ctx, p


async def test_the_designer_gets_the_chosen_look():
    ctx, _ = _ctx({"look_state": "answered", "look": "Navy and gold"})
    await collect_look(ctx)
    assert ctx.state.config["look"] == "Navy and gold"
    text = interface_input("n", "p", "g", {}, ctx.state.config)
    assert "<look>\nNavy and gold\n</look>" in text


@pytest.mark.parametrize(
    "setup",
    [
        {"look_state": "answered", "look": LOOK_DECIDE},
        {"look_state": "from_prompt"},
        {"look_state": "asking"},  # never answered (no wait in tests): times out
    ],
)
async def test_no_look_constraint(setup):
    ctx, p = _ctx(setup)
    await collect_look(ctx)
    assert "look" not in ctx.state.config
    assert p.setup["look_state"] != "asking"
