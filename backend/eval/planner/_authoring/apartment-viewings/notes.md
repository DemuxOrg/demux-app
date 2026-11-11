# apartment-viewings (real_estate, HOLDOUT=true)
Intent: renter wants (1) flats he has enquired about and (2) viewings, and deposit info. Outcome: ok.

Record types (TWO, both extracted):
- property / listing / apartment (synonyms flat, rental) - Required: address (string, found - but missing/vague in some: 'the studio near the station', 'the 2 bed on the hill', 'top of Marlow Road'; Highfield Rise street is given), monthly_rent (money, found), status (enum, found): enquired, viewing_booked, viewed, applied/deposit_paid, unavailable/rejected (3-6). Optional: bedrooms, agent_name, agent_contact.
  deposit (money) - FOUND, not a not_found trap: deposits exist in several threads (311/1,557 GBP; one month; 5 weeks; 1,707). Make sure the labeller marks it found. It's expressed variously (one week's rent, 5 weeks) -> data is messy but present.
- viewing (synonyms appointment, showing) - Required: property (string, found), date_time (date, found), status (enum, found): scheduled, cancelled, rescheduled, completed. Optional: agent.

TRAPS:
1. Key identifier (address) missing/vague in some messages.
2. Messy status wording: 'Booked in', 'rented to someone else this morning', 'I need to postpone', 'move to the afternoon', 'let me check with the owner', 'holding deposit', 'References are being processed'.
3. Noise lookalikes: HomeFinder alert emails (lists of properties never enquired about), LoanLoop mortgage ad, Swift Movers quote, current lease end notice for 42 Aldwick Road (own current home, not a prospect), flat-share offer (declined), plus generic.
4. Deposit expressed in weeks/months, not always as money.
Forbidden record types: agent (as type), landlord, email. Forbidden: search_alert as type.
Noise: ~10 of 31.
