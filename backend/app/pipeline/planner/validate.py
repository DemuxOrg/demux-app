"""Structural validation of a planner `Schema`."""

import re

from app.pipeline.planner.models import FieldType, Origin, Schema, Source, Support

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
MAX_RECORD_TYPES = 5
MAX_FIELDS = 12


def _blank(text: str | None) -> bool:
    return not text or not text.strip()


def validate(schema: Schema) -> list[str]:
    """Return human-readable errors for `schema`; an empty list means valid.

    Rules:
    - Outcome: `ok` => >= 1 record type; otherwise `user_message` set and `record_types` empty.
    - Caps (safety only): <= 5 record types; each has 1-12 fields.
    - Names: snake_case; record type names unique; field names unique per record type after
      lowercasing and stripping `_`.
    - Enums: `enum` <=> `allowed_values` with 2-6 unique values; other types have None.
    - Identity: `extracted` => non-empty `identity`; `thread` => `identity` is None.
    - Origin x support: `inferred` + `not_found` rejected; `observed` => `found` and a
      non-empty `justification`.
    - Text: no empty `label` / `description`.
    """
    errors: list[str] = []

    if schema.outcome == "ok":
        if not schema.record_types:
            errors.append("outcome 'ok' requires at least one record type")
    else:
        if _blank(schema.user_message):
            errors.append(f"outcome '{schema.outcome}' requires a user_message")
        if schema.record_types:
            errors.append(f"outcome '{schema.outcome}' must have no record types")

    if len(schema.record_types) > MAX_RECORD_TYPES:
        errors.append(f"too many record types ({len(schema.record_types)} > {MAX_RECORD_TYPES})")

    seen_rt: set[str] = set()
    for rt in schema.record_types:
        where = f"record type '{rt.name}'"
        if not SNAKE_CASE.match(rt.name):
            errors.append(f"{where}: name is not snake_case")
        if rt.name in seen_rt:
            errors.append(f"{where}: duplicate record type name")
        seen_rt.add(rt.name)
        if _blank(rt.label):
            errors.append(f"{where}: empty label")
        if _blank(rt.description):
            errors.append(f"{where}: empty description")

        if rt.source == Source.extracted and _blank(rt.identity):
            errors.append(f"{where}: source 'extracted' requires an identity")
        if rt.source == Source.thread and rt.identity is not None:
            errors.append(f"{where}: source 'thread' must have identity null")

        if not 1 <= len(rt.fields) <= MAX_FIELDS:
            errors.append(f"{where}: needs 1-{MAX_FIELDS} fields, has {len(rt.fields)}")

        seen_fields: set[str] = set()
        for f in rt.fields:
            fw = f"{where}, field '{f.name}'"
            if not SNAKE_CASE.match(f.name):
                errors.append(f"{fw}: name is not snake_case")
            key = f.name.lower().replace("_", "")
            if key in seen_fields:
                errors.append(f"{fw}: duplicate field name (ignoring case and underscores)")
            seen_fields.add(key)
            if _blank(f.label):
                errors.append(f"{fw}: empty label")
            if _blank(f.description):
                errors.append(f"{fw}: empty description")

            if f.type == FieldType.enum:
                values = f.allowed_values
                if values is None or not 2 <= len(values) <= 6 or len(set(values)) != len(values):
                    errors.append(f"{fw}: enum needs 2-6 unique allowed_values")
            elif f.allowed_values is not None:
                errors.append(f"{fw}: allowed_values only allowed for enum fields")

            if f.origin == Origin.inferred and f.support == Support.not_found:
                errors.append(f"{fw}: inferred fields that are not_found must be dropped")
            if f.origin == Origin.observed:
                if f.support != Support.found:
                    errors.append(f"{fw}: observed fields must have support 'found'")
                if _blank(f.justification):
                    errors.append(f"{fw}: observed fields need a justification")

    return errors
