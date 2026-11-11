# inbox-urgency-kanban (other, holdout=false)
Intent: ops manager wants a general inbox kanban by urgency, with sender. Outcome: ok.

Record types (ONE): email_item / inbox_item / task (synonyms thread, message, action_item) - source: THREAD (every email thread is a card; it's a view of the inbox itself, not a domain entity).
Required fields:
- subject / summary (string, found)
- sender / from (string, found)
- urgency (enum, found): expected 3-5 values, e.g. urgent / this_week (soon) / later (low) / fyi. Prompt words: "on fire, can wait a few days, just for information".
- deadline / due_date (date, found for some, absent for many; "any deadline mentioned" is in paraphrase 2 only; keep as optional or found-with-gaps. Not a not_found trap).
Optional: requested_action, status (replied or not), sender_organisation.

TRAPS:
1. Messy urgency wording: "URGENT", "ASAP", "EOD", "NOW", "whenever", "no rush at all", "when you get a chance", "FYI", "by Thursday", "Urgent??" (which resolves to not so bad), "mandatory by end of month", "sometime this week", "whatever suits you".
2. Noise: ~8 newsletters/notifications (n_news1, n_news2, n_conf, n_li, n_zoom, n_air, n_tax, CloudHost auto invoice). In a kanban they belong in the 'fyi' column, so the schema should NOT exclude them via a filter field; they are legit fyi cards. Schema must not be domain-specific (no invoice/client types).
3. Key identifier missing: many items have no deadline; senders sometimes only first name.
Forbidden record types: contact, company, invoice, meeting (as separate types). Forbidden: splitting into one type per sender category. Forbidden fields: full body.
Noise (non-actionable): ~9 of 33.
