# web-clients-projects-signoffs (clients, holdout=false)
Intent: freelancer wants clients, their current projects (with value), and approvals pending. Outcome: ok.

Record types (THREE, all extracted):
- client (synonyms customer) - Required: name (string, found; organisation e.g. Lund Bakery, Qureshi Dental, Whitmore Yoga, Okoye Builders, Aubert Vins, Plattand Co), contact_email (string, found). Optional: contact_person.
- project (synonyms job, website) - Required: name / title (string, found), client (string, found), status (enum, found): not_started/quoted, in_progress, waiting_on_client, live/completed (3-5). deadline/target_date (date, found for Qureshi 'first week of June'; optional). budget / project_value (money): support = MIXED. Two projects have a quote in thread (Qureshi 4,800 EUR; Aubert 9,500 EUR). THIS IS NOT the clean absent-trap; author's expectation: budget/value is found (money, found for some projects, absent for most). A labeller could reasonably mark found. If the independent labeller marks not_found, flag as disagreement; author's answer = found.
- approval (synonyms sign_off, pending_approval) - Required: project (string, found), item (string, found: homepage layout, sitemap, ordering wireframe, copy, staging site, gallery, product template, contact form), status (enum, found): pending, approved, changes_requested (3). Optional: requested_date, approver.

TRAPS:
1. Messy approval wording: "Looks good to me!", "👍 otherwise", "Go for it!!", "J'adore! Approved.", "Fine", "I'll review with the team and let you know", "Changes please", "agree with Chidi, bigger images", "Looks fine but please add opening hours. Then I'm ok", "Will do soon".
2. Key identifier missing: project name rarely stated (client + deliverable only); Plattand Co blog redesign has no project start; some replies are one-liners ("Fine", "Looks good to me!").
3. Noise lookalikes: ProofPilot approvals ad, NameHarbor domain renewal (for his own domain), accountant mail, GitHub/Docs notifications.
4. One thread is invoice reminder (relevant to client but not a record type; forbidden: invoice).
Forbidden record types: invoice, email, task. Forbidden: separate 'contact' type.
Noise: ~8 of 31.
