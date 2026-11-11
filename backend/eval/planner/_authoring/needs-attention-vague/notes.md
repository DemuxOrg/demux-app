# needs-attention-vague (other, holdout=false) - needs_clarification
Prompt 'What needs my attention?' has no domain, no entity and no fields. A good planner returns outcome=needs_clarification (asks what kind of items / which part of work). expected.yaml should contain only outcome + optional notes.
Not acceptable: guessing an 'action_item' schema for the whole inbox with confidence. (The inbox-urgency-kanban case is the contrast: there the prompt explicitly asks for urgency columns.)
Threads: mixed inbox on purpose (work, family, health, tax, hosting, shopping) so no single domain emerges; ~30 threads, ~13 are noise newsletters/notifications.
Traps: tempting to infer 'urgent emails' from overdue invoice, parking fine, tax docs - but the intent is not specified.
Paraphrases are equally vague ('What should I be looking at right now?', 'Is there anything important I'm missing?').
