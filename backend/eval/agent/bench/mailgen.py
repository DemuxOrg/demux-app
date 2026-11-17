"""Deterministic synthetic mailboxes for the cost / latency benchmark.

Three personas (orders, bills, jobs). Each mailbox has `n_relevant` threads the workspace
should track, `n_noise` threads it should not (promotions from the same senders, and
unrelated mail), all dated in the 85 days before `t0`. `n_future` extra messages are dated
after `t0`, one every 10 minutes, so a sync at `t0 + k*10min` sees exactly `k` new messages:
new relevant threads, follow-ups in existing threads, and noise.

No LLM is used: everything is templated, so the same seed gives the same mailbox.
"""

import hashlib
import random
from datetime import datetime, timedelta

ME = "Alex Morgan <alex@rivermail.example>"
ME_ADDR = "alex@rivermail.example"

PROMPTS = {
    "orders": "Track my online orders: what I bought, from which shop, how much it cost, "
    "and whether it has shipped or been delivered.",
    "bills": "Show me the invoices I receive from suppliers: the amount, the due date, and "
    "whether I've paid them yet.",
    "jobs": "Keep track of my job applications: the company, the role, what stage each one "
    "is at and what the next step is.",
}

SHOPS = [
    "Oakline Furniture", "Shutterbay", "Peak Outdoors", "Lumen Books", "Verde Garden",
    "Northwind Audio", "Kettle & Co", "Brightside Bikes", "Paperfold", "Tidewater Tea",
    "Atlas Luggage", "Marlow Kitchen", "Fernhill Pets", "Quartz Watches", "Harbor Hardware",
]  # fmt: skip
ITEMS = [
    ("standing desk, walnut top", 749), ("35mm prime lens", 389), ("3-layer rain jacket", 159),
    ("hardcover box set", 64), ("raised planter bed", 89), ("wireless headphones", 219),
    ("cast-iron teapot", 48), ("commuter bike lights", 37), ("A5 dotted notebooks x3", 21),
    ("oolong sampler", 26), ("cabin suitcase 40L", 132), ("chef's knife 20cm", 95),
    ("orthopaedic dog bed", 71), ("field watch, steel", 245), ("cordless drill set", 118),
    ("linen duvet cover", 84), ("espresso grinder", 310), ("yoga mat 6mm", 42),
]  # fmt: skip
SUPPLIERS = [
    "Greenleaf Packaging", "Calder Print Works", "Bluepeak Hosting", "Marini Logistics",
    "Stonebridge Accounting", "Fennel Catering", "Orbit Telecom", "Hollis Office Supply",
    "Juniper Cleaning", "Redwood Insurance", "Pixelgrain Studio", "Corvid Security",
    "Summit Energy", "Tallow & Wick", "Ashgrove Legal",
]  # fmt: skip
SERVICES = [
    "kraft bags 250g x2000", "brochure print run", "managed hosting, monthly",
    "pallet delivery", "bookkeeping, monthly", "event catering", "business fibre line",
    "office consumables", "weekly cleaning", "liability cover, quarterly",
    "product photography", "alarm monitoring", "electricity, monthly", "candle stock",
    "contract review",
]  # fmt: skip
COMPANIES = [
    "Halden Robotics", "Brightwater Health", "Corran Analytics", "Mistral Games",
    "Opaline Bank", "Tessera Maps", "Wrenfield Energy", "Lattice Learning", "Sable Aero",
    "Juno Retail", "Kestrel Security", "Maplewood Media", "Nimbus Payments", "Orchard Labs",
    "Pinecrest Mobility",
]  # fmt: skip
ROLES = [
    "Senior Backend Engineer", "Data Analyst", "Product Designer", "Platform Engineer",
    "Engineering Manager", "Machine Learning Engineer", "Technical Writer", "QA Lead",
    "Frontend Engineer", "Solutions Architect",
]  # fmt: skip
FIRST = ["Ines", "Tom", "Sofia", "Callum", "Mei", "Farid", "Nadia", "Leon", "Priya", "Jonas"]
LAST = ["Moreau", "Becker", "Marini", "Reed", "Tanaka", "Haddad", "Okafor", "Wright", "Nair"]

FOOTERS = [
    "This email and any attachments are confidential and intended solely for the addressee. "
    "If you have received it in error, please notify the sender and delete it. We process "
    "personal data in line with our privacy notice, available on our website.",
    "You are receiving this message because you have an account with us. To change which "
    "emails you receive, visit your account preferences. Please do not reply to this "
    "automated message; replies are not monitored.",
    "Need help? Our support team is available Monday to Friday, 9:00 to 17:30. Have your "
    "reference number ready so we can find your details quickly. Registered office: "
    "12 Canal Street. Company no. 08123456. VAT no. GB 123 4567 89.",
    "Returns are accepted within 30 days of delivery for unused items in their original "
    "packaging. Delivery estimates are indicative and may change during busy periods. "
    "Prices include VAT where applicable.",
]
NOISE_UNRELATED = [
    ("Calendar <calendar@rivermail.example>", "Reminder: dentist on Thursday 10:30",
     "This is a reminder for your appointment on Thursday at 10:30. Reply C to confirm."),
    ("Ridgeway Gym <hello@ridgewaygym.example>", "Your class schedule for next week",
     "Spin on Monday 18:00, yoga on Wednesday 07:30. Book in the app to keep your spot."),
    ("Marta <marta.k@rivermail.example>", "Dinner on Saturday?",
     "Are you two free on Saturday? We found a new place near the canal. Let me know!"),
    ("Citylink Transit <no-reply@citylink.example>", "Service changes this weekend",
     "Line 4 will run a reduced timetable on Saturday and Sunday due to track works."),
    ("Photo Cloud <no-reply@photocloud.example>", "Your storage is 80% full",
     "You have used 80% of your storage. Upgrade your plan or free up space."),
    ("Dev Weekly <editor@devweekly.example>", "Dev Weekly #212: what's new in tooling",
     "This week: faster builds, a look at structured logging, and five articles to read."),
]  # fmt: skip


def _id(*parts: object) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:16]


def _domain(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum()) + ".example"


FILLER = [
    "You might also like: customers who viewed this item also looked at our seasonal range, "
    "now back in stock in all sizes and colours while supplies last.",
    "How to reach us: reply to this email, call the number on our website, or use the chat "
    "in your account. Typical response time is one working day.",
    "Terms: all services are provided under our standard terms and conditions, a copy of "
    "which is available on request. Late payments may incur a statutory interest charge.",
    "Tip: add our address to your contacts so that updates about your account do not end up "
    "in your spam folder. You can manage notification settings at any time.",
    "Sustainability note: we offset the carbon emissions of every delivery and use recycled "
    "packaging wherever possible. Read our yearly impact report online.",
    "Security reminder: we will never ask for your password or full card number by email. "
    "If a message looks suspicious, forward it to our security team.",
    "Your feedback matters: tell us how we did in a two-minute survey and enter the monthly "
    "prize draw. Winners are contacted by email.",
    "Opening hours over the holiday period may differ. Orders and requests received after "
    "the cut-off date will be handled on the next working day.",
]


def _body(rng: random.Random, text: str, sender: str) -> str:
    """Realistic lengths: 30% short (~0.6k chars), 40% medium (~1.6k), 30% long (~3.5k+).

    Real transactional mail carries long footers and promotional blocks; the pipeline
    caps a new message at 3,000 characters, so the long ones hit that cap."""
    extra = rng.sample(FOOTERS, rng.randint(1, 3))
    roll = rng.random()
    target = 0 if roll < 0.3 else rng.randint(1300, 1900) if roll < 0.7 else rng.randint(3200, 4200)
    body = f"Hi Alex,\n\n{text}\n\nKind regards,\n{sender}\n\n" + "\n\n".join(extra)
    while len(body) < target:
        body += "\n\n" + rng.choice(FILLER)
    return body


def _msg(tid: str, n: int, sender: str, date: datetime, subject: str, body: str, att=()) -> dict:
    return {
        "message_id": _id(tid, n),
        "sender": sender,
        "to": [ME_ADDR],
        "date": date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "subject": subject,
        "body": body,
        "attachments": list(att),
    }


def _stages(persona: str, rng: random.Random, i: int) -> tuple[str, list[tuple[str, str, tuple]]]:
    """Sender and the full message sequence (subject, text, attachments) of one thread."""
    if persona == "orders":
        shop = rng.choice(SHOPS)
        item, price = rng.choice(ITEMS)
        ref = f"{''.join(w[0] for w in shop.split())[:2].upper()}-{50000 + i * 37 % 49999}"
        total = price + rng.choice([0, 0, 4.9, 6.5])
        sender = f"{shop} <orders@{_domain(shop)}>"
        return sender, [
            (f"Order confirmation {ref}",
             f"Thanks for your order {ref}.\n\n1 x {item}\nTotal: EUR {total:.2f} (incl. VAT)\n"
             f"Payment: card ending {rng.randint(1000, 9999)}\nEstimated delivery: "
             f"{rng.randint(3, 9)} working days.", ()),
            (f"Your order {ref} has shipped",
             f"Good news: order {ref} ({item}) left our warehouse today.\nCarrier: ParcelPost, "
             f"tracking PP{rng.randint(10**7, 10**8 - 1)}.\nExpected delivery in "
             f"{rng.randint(1, 4)} days.", ()),
            (f"Delivered: order {ref}",
             f"Your order {ref} was delivered today and signed for at the front door. "
             f"We hope you enjoy your {item.split(',')[0]}.", ()),
        ]  # fmt: skip
    if persona == "bills":
        sup = rng.choice(SUPPLIERS)
        service = rng.choice(SERVICES)
        ref = f"{''.join(w[0] for w in sup.split())[:2].upper()}-{2000 + i * 13 % 7999}"
        amount = rng.choice([120, 245, 380, 560, 980, 1340, 2150]) + rng.choice([0, 0.5, 9.9])
        due = rng.randint(1, 28)
        person = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        sender = f"{sup} Accounts <accounts@{_domain(sup)}>"
        return sender, [
            (f"Invoice {ref} - {service}",
             f"Please find attached invoice {ref} for {service}.\n\nTotal: EUR {amount:.2f} "
             f"(incl. VAT)\nPayment terms: 30 days, due on the {due}th of next month\n"
             f"Bank transfer reference: {ref}", (f"{ref}.pdf",)),
            (f"Reminder: invoice {ref} is due soon",
             f"A friendly reminder from {person}: invoice {ref} (EUR {amount:.2f}) falls due "
             f"shortly. If you have already paid, please ignore this message.", ()),
            (f"Payment received for invoice {ref}",
             f"We have received your payment of EUR {amount:.2f} for invoice {ref}. "
             f"Thank you, the invoice is now settled.", ()),
        ]  # fmt: skip
    company = rng.choice(COMPANIES)
    role = rng.choice(ROLES)
    person = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    sender = f"{person} ({company} Talent) <careers@{_domain(company)}>"
    outcome = rng.choice(["offer", "reject", "reject", "next"])
    last = {
        "offer": (f"Offer: {role} at {company}",
                  f"We are delighted to offer you the {role} position. Salary: EUR "
                  f"{rng.randint(62, 110)},000 per year. Please reply by Friday to accept.",
                  ("offer_letter.pdf",)),
        "reject": (f"Update on your application for {role}",
                   f"Thank you for your time. After careful consideration we will not be "
                   f"moving forward with your application for {role} at {company}.", ()),
        "next": (f"Next step: final round for {role}",
                 f"You did well. We would like to invite you to a final on-site round for "
                 f"{role} next week; a take-home exercise will follow by email.", ()),
    }[outcome]  # fmt: skip
    return sender, [
        (f"We received your application: {role}",
         f"Thank you for applying for the {role} role at {company}. Our team is reviewing "
         f"your application and will be in touch within two weeks.", ()),
        (f"Interview invitation: {role} at {company}",
         f"We would like to invite you to a 45-minute video interview for {role} with "
         f"{person}. Please pick a slot on {rng.choice(['Tuesday', 'Wednesday', 'Friday'])} "
         f"afternoon.", ()),
        last,
    ]  # fmt: skip


def _noise(persona: str, rng: random.Random) -> tuple[str, str, str]:
    """A noise mail: half promotions from relevant-looking senders, half unrelated."""
    if rng.random() < 0.5:
        name = rng.choice({"orders": SHOPS, "bills": SUPPLIERS, "jobs": COMPANIES}[persona])
        dom = _domain(name)
        if persona == "orders":
            return (
                f"{name} <news@{dom}>",
                f"{rng.choice([20, 30, 40])}% off this weekend only",
                "Our seasonal sale is here. Order before Sunday midnight and get free "
                "delivery on everything. New arrivals have just landed in store.",
            )
        if persona == "bills":
            return (
                f"{name} <news@{dom}>",
                "Our new price list and autumn newsletter",
                "We have updated our services and price list for next quarter. Invoices "
                "can now be downloaded from the customer portal at any time.",
            )
        return (f"{name} <jobs-alerts@{dom}>", "New jobs matching your profile",
                "5 new roles match your saved search, including engineer and analyst "
                "positions. Apply in one click from your candidate profile.")  # fmt: skip
    return rng.choice(NOISE_UNRELATED)


def generate(
    persona: str, n_relevant: int, n_noise: int, t0: datetime, n_future: int = 30, seed: int = 1
) -> list[dict]:
    rng = random.Random(f"{persona}-{n_relevant}-{n_noise}-{seed}")
    threads: dict[str, dict] = {}
    pending: list[tuple[str, str, list, int]] = []  # threads with later stages still to come

    def stamp(days_ago: float) -> datetime:
        return (t0 - timedelta(days=days_ago)).replace(microsecond=0)

    for i in range(n_relevant):
        tid = _id(persona, "rel", i, seed)
        sender, stages = _stages(persona, rng, i)
        shown = rng.choice([1, 1, 2, 2, 3])
        start = rng.uniform(4, 85)
        msgs = []
        for n in range(shown):
            subject, text, att = stages[n]
            when = stamp(max(0.05, start - n * rng.uniform(0.8, 3.0)))
            subject = subject if n == 0 or persona != "jobs" else subject
            msgs.append(_msg(tid, n, sender, when, subject, _body(rng, text, sender), att))
        threads[tid] = {"thread_id": tid, "messages": msgs}
        if shown < len(stages):
            pending.append((tid, sender, stages, shown))

    for i in range(n_noise):
        tid = _id(persona, "noise", i, seed)
        sender, subject, text = _noise(persona, rng)
        when = stamp(rng.uniform(0.1, 85))
        body = _body(rng, text, sender)
        threads[tid] = {"thread_id": tid, "messages": [_msg(tid, 0, sender, when, subject, body)]}

    rng.shuffle(pending)
    for k in range(n_future):
        when = t0 + timedelta(minutes=10 * (k + 1))
        roll = rng.random()
        if roll < 0.3 and pending:
            tid, sender, stages, n = pending.pop()
            subject, text, att = stages[n]
            threads[tid]["messages"].append(
                _msg(tid, n, sender, when, subject, _body(rng, text, sender), att)
            )
        elif roll < 0.8:
            tid = _id(persona, "future", k, seed)
            sender, stages = _stages(persona, rng, 10_000 + k)
            subject, text, att = stages[0]
            body = _body(rng, text, sender)
            threads[tid] = {
                "thread_id": tid,
                "messages": [_msg(tid, 0, sender, when, subject, body, att)],
            }
        else:
            tid = _id(persona, "future-noise", k, seed)
            sender, subject, text = _noise(persona, rng)
            body = _body(rng, text, sender)
            threads[tid] = {
                "thread_id": tid,
                "messages": [_msg(tid, 0, sender, when, subject, body)],
            }
    return list(threads.values())
