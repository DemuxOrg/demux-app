# Planner benchmark — file formats

A **case** is one directory `eval/planner/cases/<id>/` (real cases: `eval/planner/real/<slug>/`,
same layout). `<id>` is a lowercase kebab-case slug, e.g. `invoices-unpaid`.

```
cases/<id>/request.yaml    the prompt (+ metadata)
cases/<id>/threads.json    the threads that retrieval returned (mocked)
cases/<id>/expected.yaml   ground truth (written by a labeller, never by the case author)
```

## request.yaml

```yaml
id: invoices-unpaid          # equals the directory name
prompt: "Show me my unpaid invoices with amount and due date"
paraphrases:                 # exactly 2: same intent, different wording
  - "Which invoices haven't I paid yet? I need amounts and due dates"
  - "Track outstanding invoices: how much and when they're due"
domain: finance              # finance | logistics | hiring | subscriptions | real_estate | support | clients | other
holdout: false               # true for 3 of the 12 cases; excluded while iterating
```

## threads.json

A JSON list of threads. Datetimes are ISO 8601 with timezone.

```json
[
  {
    "thread_id": "t001",
    "messages": [
      {
        "message_id": "t001-m1",
        "sender": "Ana Ruiz <ana@acme-supplies.example>",
        "to": ["me@example.com"],
        "date": "2026-03-04T09:15:00+00:00",
        "subject": "Invoice 2041 - due 15 March",
        "body": "Hi, please find invoice 2041 for 1,250.00 EUR attached...",
        "attachments": ["invoice-2041.pdf"]
      }
    ]
  }
]
```

- `thread_id` unique per file; `message_id` unique per file; messages ordered oldest to newest.
- Use reserved domains (`example.com`, `*.example`) for all addresses.
- Realistic and messy: replies with quoted text, forwards, signatures, one-line answers.

## expected.yaml

```yaml
outcome: ok                  # ok | needs_clarification | unsupported
record_types:
  - name: invoice
    synonyms: [bill, unpaid_invoice]
    source: extracted        # thread | extracted
    required_fields:
      - {name: amount,   synonyms: [total, invoice_amount], type: money,  support: found}
      - {name: due_date, synonyms: [due, deadline],         type: date,   support: found}
      - {name: vendor,   synonyms: [supplier, from],        type: string, support: found}
    optional_fields: [invoice_number, status, currency]   # allowed; not counted as over-generation
    forbidden_fields: [sender_email_signature]            # counted as errors if present
forbidden_record_types: [vendor_contact]
notes: "one invoice has no number; one reminder has no amount"
```

- `type` is one of `string, number, money, date, boolean, enum`; `support` is `found` or `not_found`.
- For `needs_clarification` / `unsupported` cases: only `outcome` (and optional `notes`).
- Names are snake_case. Synonyms are alternative names a reasonable planner might choose.
