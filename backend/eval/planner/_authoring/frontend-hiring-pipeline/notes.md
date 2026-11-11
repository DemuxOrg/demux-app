# frontend-hiring-pipeline (hiring, holdout=false)
Intent: hiring manager wants applicants, their stage, upcoming interviews, plus expected pay. Outcome: ok.

Record types (TWO, both extracted):
- candidate (synonyms applicant) - Required: name (string, found), stage (enum, found), email (string, found mostly), expected_salary (money, support=NOT_FOUND - prompt asks "what pay they're hoping for"; no thread mentions salary/pay/compensation anywhere). Optional: role, source, notes.
  stage enum expected 4-7 values: applied, screening/intro_call, interview/technical, final, offer, rejected, withdrawn (hired not present). Messy wording planted: "Parking him for now", "we won't be taking it forward", "I've accepted another offer so I'd like to withdraw", "we'd love to make you an offer / I'll wait for the paperwork", "move him to the final round", "still very interested".
- interview (synonyms meeting, call, interview_slot) - Required: candidate (string, found), date_time (date/datetime, found), interviewer or format (string, found), optional status (scheduled/completed/cancelled).

TRAPS:
1. expected_salary requested, absent from all threads -> not_found (main).
2. Key identifier missing: agency candidate 'Candidate 0412' has no name; the 'Sven' thread has first name only; Tariq and Olivia emails sparse.
3. Messy stage wording across replies.
4. Noise lookalikes: Marketing Manager application (different role -> should not be in front-end pipeline; a labeller may treat as irrelevant), TalentBridge marketing newsletter, HireSnap ATS ad, JobBoard alerts, HR stats mail, LinkedIn, plus generic.
Forbidden record types: job_posting, recruiter, email. Forbidden fields: CV text.
Noise: ~9 of 32.
