# Planner prompt log

One entry per iteration of `SYSTEM_PROMPT` (general rules only; never case-specific wording).
Metrics are on the 9 non-holdout synthetic cases, 1 run each, Qwen/Qwen3.6-35B-A3B via deepinfra,
thinking off.

## 0 — first draft (rules from the plan, verbatim in spirit)
Result: outcome 0.78, record type recall 0.55, source 0.33, required-field recall 0.50,
over-generation 3.0, valid first try 0.89. Failures: vague and unprofitable-style prompts answered
`ok`; `thread` chosen where one entity spans threads; separate record types merged into one;
many extra fields.

## 1 — outcome criteria, source rule, sparing fields
Changes: criteria for needs_clarification/unsupported; prefer `extracted` when an item can recur
across threads; separate record types per listed kind of thing; fields named with the user's words;
at most one observed field.
Result: outcome 1.00 (+0.22), source 1.00 (+0.67), over-generation 1.00 (-2.0), valid first try 1.00,
recall 0.73, required-field recall 0.73. Remaining: child record types flattened into parent fields,
money fields typed string, a field marked found with no supporting thread.

## 2 — field types and support wording
Changes: type guidance (money/date/number/string); "found" only when a thread states it.
Result: type accuracy 1.00 (+0.10), over-generation 0.88, support 0.895 (-0.05: judged fields such as
urgency wrongly `not_found`), recall unchanged 0.73/0.73 (child record types still flattened).


## 3 — operational test for child record types; support covers judged states
Changes: "if a field would hold several values for one parent, make it its own record type";
"found" also when a state/stage/urgency can be read from the wording.
Result: recall 0.82 (+0.09), required-field recall 0.77 (+0.04), support 1.00, over-generation 0.67.
Remaining: one case still flattens two child record types into the parent.
Note: `interview.scheduled_date` is scored as extra vs label `interview_date` (synonym gap in the
label, not a planner error): listed for Jihad, label not edited.


## 4 — "attribute on a noun makes it a record type"
Changes: a noun that gets its own attribute in the prompt is a record type, not a parent field.
Result: required-field recall 0.81 (+0.04); recall unchanged 0.82. The one failing case still
produces a single flat "one row per parent" record type.


## 5 — "what is one row?"
Changes: each record type is a list with one row per item; a compound row must be split.
Result (non-holdout, 1 run): ALL thresholds pass. outcome 1.00, record type recall 0.91, precision 0.91,
source 1.00, required-field recall 0.92, over-generation 0.50, type 0.96, support 0.96, valid first try 1.00.
Remaining diffs are naming/synonym mismatches (`pending_signoff` vs label `approval`) and two
single-field slips. Stop: thresholds met; next is the final `--all --stability` run.

## Eval change (not a prompt change) — LLM name normaliser
Why: harmless renames (`deposit_info` vs `deposit`) were scored as a miss plus an extra. Decided with
Jihad instead of growing synonym lists or hardcoding names into the prompt. `normalize.py` maps only
unmatched planner names to unmatched label names (thinking on, temp 0, no thread content), caches verdicts
in `<run>/normalization.json`, and lists every applied rename in `report.md`. `--no-normalize` = strict.
Rescore of run 20261111T144452Z: required-field recall 0.72 -> 0.90, over-generation 0.85 -> 0.08.
