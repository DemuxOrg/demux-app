# shipments-tracking (logistics, HOLDOUT=true)
Intent: workshop owner tracks inbound international parts shipments. Outcome: ok. One extracted record type.

Record types (ONE): shipment (synonyms parcel, package, order, incoming_delivery) - source: extracted (the fact comes from several emails per shipment: supplier mail + carrier updates).
Required fields:
- supplier (string, found) [synonyms sender, vendor, from]
- expected_arrival / eta (date, found)
- tracking_number (string, found for most; MISSING in some: Mori Micro air mail has none; Falk first message says tracking will come later; Seoul Tech order 2231 confirmation without tracking)
- status (enum, found - not asked in prompt but 'still on its way' implies it): ordered, shipped, in_transit, delayed, exception, delivered. 3-6 values.
- import_duty / duty_amount (money, support = NOT_FOUND): prompt asks "what duty I'll have to pay" but NO thread mentions duty, tax or fees on parcels. Planner must keep field as not_found, not drop it. (Only 'duty' lookalike is the fake 2.99 'fee' phishing - noise.)
Optional: order_number, carrier, quantity/contents.

TRAPS:
1. Explicit requested field (import_duty) absent from ALL threads -> not_found.
2. Tracking number missing in some messages.
3. Status wording messy: "left our warehouse", "departed origin facility", "stuck at the airport", "moving again", "delayed", "exception - address problem", "out for delivery", "signed for by Reception", "delivered yesterday".
4. Noise that looks relevant: phishing 'package held pay fee', DeliverMax shipping ad, Amazing Books order (personal), food delivery, flight check-in, PL Components bulk discount mail is borderline supplier chatter (not a shipment).
Dedup: one shipment spans several threads (SZ-5501 has 4 mails; 9400... has 2). Fine for planner schema; not needed in schema.
Forbidden record types: supplier (as separate type), carrier_update, email. Forbidden fields: customer-facing fields.
Noise: ~8 of 31.
