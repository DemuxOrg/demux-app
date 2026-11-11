# support-needs-reply (support, HOLDOUT=true)
Intent: shop owner wants customer emails still awaiting HIS reply, with waiting time. Outcome: ok.

Record types (ONE): support_request / customer_inquiry (synonyms ticket, customer_email, open_request) - source: THREAD (state depends on the thread's last message).
Required fields:
- customer_name (string, found)  [synonyms: from, sender]
- status (enum, found): needs_reply / waiting_on_customer / resolved (optionally also 'info_only'). 3-4 values. Key logic: last message from customer w/o reply = needs_reply; last message from shop = waiting_on_customer or resolved. Wording messy: "All good now", "Thanks!", "No action needed", "Waiting for the quote", "Ok. Please do, I'm waiting."
- received_date / last_message_date (date, found) and/or waiting_days (number, derived). Prompt asks "how long they've been waiting" -> either a date or days-waiting is fine.
- subject / issue_summary (string, found).
Optional: order_number (string).

TRAPS:
1. Key identifier missing: order_number absent in several (question about paint, discount code, gregory's market-stall purchase, bulk order, shipping to Ireland).
2. Noise that looks relevant: HelpHero ad ('support inbox overflowing'), mailbox weekly stats from MailDesk, out-of-office autoreply, ShopRate review alert, supplier invoice, plus generic newsletters. None is a customer email.
3. Status derivable from direction of last message, not a text label.
4. Several threads where shop already replied or customer thanked (resolved) must not count as 'needs_reply' - good schema must have a status enum rather than a flat list.
Forbidden record types: customer (as separate type), order, product. Forbidden fields: full email body.
Noise: ~9 of 31.
