# vendor-invoices-payable (finance, holdout=false)
Intent: bakery owner wants (1) suppliers and (2) their unpaid bills with amount, due date and PO.
Outcome: ok. Two extracted record types, no thread-sourced.

Record types:
- vendor (synonyms supplier, company) - extracted. Required: name (string, found), contact_email (string, found; optional-ish). Optional: phone not present - do not demand it.
- invoice (synonyms bill) - extracted. Required: vendor (string, found), amount (money, found), due_date (date, found), status (enum, found). Optional: invoice_number, currency.
  Enum values expected (2-6): unpaid / paid / overdue / disputed (maybe partially_paid or credit_issued). Messy wording planted: "settled", "ignore the reminder", "paid on the 2nd", "paying tomorrow", "disputing line 3", "corrected invoice replaces 5602", "pay whenever".

TRAPS:
1. po_number (PO / purchase order) requested in prompt but absent from ALL threads -> planner must keep it as a field with support=not_found (on invoice).
2. Key identifier missing: some invoices have no invoice number (hand-written Kestrel deep clean, eggs bill from Sunny Lane Farm); energy bills use an account ref and are direct debit (no due date, collected date).
3. Status wording messy and spread across replies (reminders, 'already paid', credit note, dispute, corrected invoice 5602A superseding 5602).
4. Noise that looks relevant: phishing 'FINAL NOTICE invoice unpaid', Billwise invoicing-software ad, bank statement, home energy bill (personal flat, Brightline Home, vs business bill from Brightline Business), Fuelstop receipt, survey.
Mixed currency: all GBP. Amounts present in most.
Forbidden: record types like payment, email, reminder, accountant (Marta is not a vendor). Forbidden fields: email body text, attachment names.
Noise threads: ~8 of 30.
