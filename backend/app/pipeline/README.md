# pipeline/

Intentionally empty in Phase 0. This package will hold the Gmail → LLM extraction pipeline: fetching messages with the Gmail API, planning which fields to extract from a workspace's prompt, running the LLM extraction, and storing structured results so a workspace can be refreshed. Services will call into it; routes never will directly.
