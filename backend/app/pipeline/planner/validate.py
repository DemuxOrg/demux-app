"""Structural validation of a planner `Schema`."""

from app.pipeline.planner.models import Schema


def validate(schema: Schema) -> list[str]:
    """Return human-readable errors for `schema`; an empty list means valid.

    Rules:
    - Outcome: `ok` => >= 1 record type; otherwise `user_message` set and no record types.
    - Caps (safety only): <= 5 record types; each has 1-12 fields.
    - Names: snake_case; record type names unique; field names unique per record type after
      lowercasing and stripping `_`.
    - Enums: `enum` <=> `allowed_values` with 2-6 unique values; other types have None.
    - Identity: `extracted` => non-empty `identity`; `thread` => `identity` is None.
    - Origin x support: `inferred` + `not_found` rejected; `observed` => `found` and a
      non-empty `justification`.
    - Text: no empty `label` / `description`.
    """
    raise NotImplementedError
