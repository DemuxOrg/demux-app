# tool-subscriptions-renewals (subscriptions, holdout=false)
Intent: agency owner wants inventory of business software subscriptions: price, renewal date, user. Outcome: ok. One extracted record type.

Record types (ONE): subscription (synonyms tool, service, recurring_payment, plan) - extracted.
Required fields:
- service_name (string, found)
- cost / price (money, found)
- renewal_date / next_billing_date (date, found for most; missing for Mailrocket invoice, Plotline free plan, FrameStock annual)
- billing_period / frequency (enum, optional or found): monthly / annual
- status (enum, found, 2-5 values): active, trial, cancelled (still active until period end), payment_failed/past_due, expiring/auto-renew off. Messy wording planted: "stays active until X and won't renew", "trial ends in 3 days", "cancelled ... keep access until end of billing period", "couldn't charge your card", "Auto-renew is OFF", "free plan".
- user / team_member (string, support=NOT_FOUND): requested ("who on the team actually uses it"). Emails by Mara/Jonas say 'only Jonas and I use Pixelforge' and 'I haven't opened Taskwise' - ambiguous, partial. EXPECTED labeller choice: not_found since no systematic assignment. (Borderline: partial evidence for 2 tools - note for comparison. Author's answer: not_found.)
TRAPS:
1. user/who-uses-it requested, essentially absent -> not_found.
2. Renewal date missing for some; price in different currencies (USD, GBP).
3. Status wording messy (cancel/trial/failed).
4. Noise lookalikes: StreamBox and FitHub (personal subscriptions - recurring but not business tools; borderline, author treats as noise but acceptable), coffee machine one-off receipt, QuickMart receipt, shop promo, Plotline discount offer (marketing for a free plan), digest.
Forbidden record types: invoice, payment, vendor. Forbidden fields: card_number, email_body.
Noise: ~9 of 31.
