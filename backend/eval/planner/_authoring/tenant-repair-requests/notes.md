# tenant-repair-requests (real_estate, holdout=false)
Intent: landlord wants tenant repair issues with progress status. Outcome: ok.

Record types (ONE): repair_request / maintenance_request / issue (synonyms ticket, job) - source: THREAD (one card per reported issue/email thread; the status is tracked in the thread: tenant message -> plumber visit -> 'all sorted'). Prompt: "each repair issue and where it's at".
Required fields:
- issue / description (string, found)
- status (enum, found, 3-6 values): new/reported, awaiting_contractor/scheduled, waiting_on_parts, fixed/resolved. Messy wording planted: "I'll put it on the list", "Hal will come on...", "the hinge needs ordering", "all sorted", "Fixed it, thanks!", "Good as new", "Confirmed, works perfect", "Thank you."
- tenant_name (string, found)
- unit / property (string, found for most; MISSING in several: Jack's tap has '7B Millbrook House' but 'top floor' (Luis) initially lacks building, 'front door lock' (Raj) initially no flat, Nina's bins, Amara's mould flat only after follow-up). Planner should not make unit required-nonnull at extraction level but keep as found.
Optional: reported_date, contractor, urgency.
No not_found trap in this case (cost is not requested).

TRAPS:
1. Status wording messy -> clean enum.
2. Key identifier (unit/flat) missing in some messages.
3. Noise lookalikes: PropManager Pro ad about repair emails, Landlord Weekly newsletter, tenant rent payment mail (tenant but not repair), contractor quote for guttering (landlord-initiated, borderline), council tax, insurance, bins (communal issue - IS a repair-like request; borderline), washing machine (appliance - is a request).
Forbidden record types: tenant, contractor, invoice, property (as separate type). Forbidden fields: cost (not asked).
Noise: ~9 of 31.
