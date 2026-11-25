# Access: who can sign up and use Demux

Demux is for paying customers. Nobody can create an account, or use the app, unless
their **login email** has access:

| Access | How someone gets it | Ends |
|---|---|---|
| **Admin** | Their email is in `ADMIN_EMAILS` (or `users.is_admin`) | Never |
| **Trial** | They started the 14-day free trial on the landing page (Stripe subscription `trialing`). They get in **right away** | If they cancel. Otherwise Stripe charges €12 on day 14 and it becomes a subscription |
| **Subscription** | That subscription is `active`, or `past_due` (Stripe is retrying a failed payment) | When Stripe cancels it (`canceled`, `unpaid`, …) |
| **Free access** | An admin adds the email in **/admin/access** (beta users, friends) | Never, or the date chosen; or when revoked |

The rule lives in one place, `backend/app/services/access.py`, and is used for:

1. **Sign-up.** Before better-auth writes a user row, the frontend server asks the API
   (`POST /api/v1/internal/signup-check`, authorized by `INTERNAL_API_SECRET`). No access,
   no account: the form says "There's no Demux subscription for this email" and links to
   the landing page. If the email is unknown, the API asks Stripe once (the webhook can be
   a few seconds behind a fresh checkout). If the API can't answer, sign-up is refused.
   Since `users.email` is unique, each paid email gets exactly one account.
2. **Every app request.** `/workspaces/*` answers 402 `subscription_required` without
   access. The app then shows "Your Demux access has ended" with a Subscribe button and
   "I've subscribed, check again". `/me` stays open so the app can show why.
3. **The worker.** Scheduled syncs skip users without access, so a lapsed subscription
   stops LLM spend. Nothing is deleted: the workspaces come back when they subscribe.

## How the app knows who paid

The landing page (www.usedemux.com, repo `DemuxUI`) owns checkout. The app has **its own
Stripe webhook endpoint** on the same Stripe account:

```
Stripe ──webhook──▶ api.usedemux.com/api/v1/billing/stripe/webhook
                      → reads that customer + subscriptions from Stripe
                      → upserts billing_customers (email, status, trial dates)
```

Every event is only a hint: the API re-reads the customer from Stripe, so duplicated,
late or out-of-order events are harmless. **/admin/access → Sync from Stripe** re-reads
every customer (first deploy, or after the endpoint was down).

## Setting it up in production

**Which keys?** The webhook signing secret must be new: every Stripe endpoint has its own,
so the landing page's `whsec_…` will not verify the app's events. For the API key, the
landing page's `sk_live_…` would work, but use a new **restricted** key: the app only reads,
so a leaked app key can't charge, refund or delete anything, and you can rotate it without
touching the landing page.

1. **Restricted key** (Stripe dashboard, live mode → Developers → API keys → Create
   restricted key): name it `Demux app (read only)`, give **Customers: Read** and
   **Subscriptions: Read**, leave everything else at None. Copy the `rk_live_…` value.
2. **Webhook endpoint** (Developers → Webhooks → Add endpoint, called "Add destination"
   in newer dashboards): URL `https://api.usedemux.com/api/v1/billing/stripe/webhook`, events
   `checkout.session.completed`, `customer.created`, `customer.updated`, `customer.deleted`,
   `customer.subscription.created`, `customer.subscription.updated`,
   `customer.subscription.deleted`, `customer.subscription.paused`,
   `customer.subscription.resumed`. Open the endpoint and reveal its signing secret
   (`whsec_…`).
3. **Shared secret**: `openssl rand -base64 48`, used on the API and the frontend.
4. **Scaleway, API container**: `STRIPE_SECRET_KEY` (step 1), `STRIPE_WEBHOOK_SECRET`
   (step 2), `INTERNAL_API_SECRET` (step 3), `ADMIN_EMAILS` (comma-separated). Put the three
   secrets under *Secrets*, not plain environment variables.
5. **Scaleway, worker container**: `ADMIN_EMAILS` (same value; the worker uses it to decide
   whose workspaces keep syncing).
6. **Scaleway, frontend container**: `INTERNAL_API_SECRET` (same value as step 3). It calls
   the API at `NEXT_PUBLIC_API_URL`; set `BACKEND_INTERNAL_URL` only to use a private address.
7. **Landing page (Vercel)**: see `DemuxUI/docs/stripe.md` (the €12 price, the trial,
   the customer portal). `NEXT_PUBLIC_DEMUX_APP_URL` is optional (defaults to
   `https://app.usedemux.com`).
8. Set all of the above **before** the code is deployed (merge to `main`): until then,
   sign-up is closed and only `ADMIN_EMAILS` can use the app.
9. After the deploy: open **/admin/access** (the red "Stripe is not connected" note must be
   gone), press **Sync from Stripe**, and check the customers list. Then in Stripe, open the
   endpoint and check that recent deliveries are `200`.

### Existing accounts

The migration changes no data. After deploy, any existing account without a subscription,
trial or free access sees the "access has ended" screen at its next request. Before
deploying, check **/admin/users** (the Access column) and give free access in
**/admin/access** to anyone who should keep using Demux.

## Local development

`make setup` / `make up` generate `INTERNAL_API_SECRET` (and copy it into
`frontend/.env.local`). Without Stripe keys, only `ADMIN_EMAILS` and free access can sign
up: put your own email in `ADMIN_EMAILS` in `.env`. To test Stripe locally:

```bash
stripe listen --forward-to localhost:8000/api/v1/billing/stripe/webhook
```

and put the printed `whsec_…` in `STRIPE_WEBHOOK_SECRET`, with a test-mode key in
`STRIPE_SECRET_KEY`.
