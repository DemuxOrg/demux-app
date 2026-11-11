# client-pipeline-board (clients, holdout=false)
Intent: freelance designer wants a board (stages) of client conversations. Outcome: ok.

Record types (ONE):
- client_conversation / client / lead (synonyms deal, opportunity, prospect) - source: THREAD (one card per email thread). Prompt says "client conversations... board".
  Required fields: client_name (string, found), stage (enum, found), quoted_amount (money, found for some threads, missing for others - still support=found at schema level since present in the corpus), last_contact / last_activity_date (date, found).
  Optional: project_description, company, contact_email.
  stage enum expected 4-6 values, e.g. new_enquiry, proposal_sent, negotiating/waiting_on_client, won/signed, lost/declined. Messy wording planted: "Where do I sign?", "approved by finance", "will think abt it", "let me run it past my brother", "sorry for the silence", "Maybe next year", "went with another studio", "all clear from the board", "Paid. Let's go!", "Yes please I'll pay up front".

TRAPS:
1. Status wording messy -> 2-6 clean enum values (main trap).
2. Missing data: several enquiries with no price (Ben poster initially, Pereira, Ravi); price discussed in-thread only for some. Amounts in EUR.
3. Noise lookalikes: Typeface Weekly newsletter (mentions 'client proposal'), a plumber asking for web dev (declined, but IS a client-conversation -> relevant, lost/declined), LinkedIn, conferences.
4. Key identifier: a few threads have only first names / casual senders (Ben).
Source must be thread (not extracted).
Forbidden: record types like invoice, payment, task; fields like email_body. Forbidden: 'project' separate record type.
Noise: ~9 of 33 (n_news2, n_li, n_conf, n_shop, n_cal, n_pod, n_sec, Typeface Weekly; the intro forward and plumber are relevant).
