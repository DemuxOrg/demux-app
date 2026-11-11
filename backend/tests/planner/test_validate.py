from app.pipeline.planner.models import Field, RecordType, Schema
from app.pipeline.planner.validate import validate


def fld(name="amount", **kw):
    base = {
        "name": name,
        "label": "Amount",
        "description": "The amount",
        "type": "string",
        "allowed_values": None,
        "origin": "explicit",
        "support": "found",
        "justification": None,
    }
    return Field(**{**base, **kw})


def rt(name="invoice", fields=None, **kw):
    base = {
        "name": name,
        "label": "Invoices",
        "description": "One invoice",
        "source": "extracted",
        "identity": "same invoice number",
        "fields": [fld()] if fields is None else fields,
    }
    return RecordType(**{**base, **kw})


def schema(rts=None, **kw):
    base = {
        "outcome": "ok",
        "user_message": None,
        "scope": "scope",
        "record_types": [rt()] if rts is None else rts,
        "unresolved": [],
    }
    return Schema(**{**base, **kw})


def test_baseline_valid():
    assert validate(schema()) == []


# Outcome
def test_outcome_ok_needs_record_type():
    assert validate(schema()) == []
    assert validate(schema(rts=[]))


def test_outcome_not_ok_needs_message_and_no_record_types():
    for outcome in ("needs_clarification", "unsupported"):
        assert validate(schema([], outcome=outcome, user_message="please clarify")) == []
        assert validate(schema([], outcome=outcome, user_message=None))
        assert validate(schema([], outcome=outcome, user_message=""))
        assert validate(schema([rt()], outcome=outcome, user_message="msg"))


# Caps
def test_caps_record_types_max_5():
    five = [rt(name=f"thing_{c}") for c in "abcde"]
    assert validate(schema(five)) == []
    assert validate(schema([*five, rt(name="thing_f")]))


def test_caps_fields_1_to_12():
    twelve = [fld(name=f"field_{c}") for c in "abcdefghijkl"]
    assert validate(schema([rt(fields=twelve)])) == []
    assert validate(schema([rt(fields=[*twelve, fld(name="field_m")])]))
    assert validate(schema([rt(fields=[])]))


# Names
def test_names_snake_case():
    assert validate(schema([rt(fields=[fld(name="due_date_2")])])) == []
    for bad in ("DueDate", "due date", "due-date", "_due", "due__date", "", "1due"):
        assert validate(schema([rt(fields=[fld(name=bad)])])), bad
    for bad in ("Invoice", "my invoice", "invoice-x"):
        assert validate(schema([rt(name=bad)])), bad


def test_names_record_types_unique():
    assert validate(schema([rt(name="invoice"), rt(name="vendor", identity="same name")])) == []
    assert validate(schema([rt(name="invoice"), rt(name="invoice")]))


def test_names_fields_unique_after_normalising():
    ok = [fld(name="due_date"), fld(name="amount")]
    assert validate(schema([rt(fields=ok)])) == []
    assert validate(schema([rt(fields=[fld(name="due_date"), fld(name="due_date")])]))
    assert validate(schema([rt(fields=[fld(name="due_date"), fld(name="duedate")])]))


def test_names_fields_unique_per_record_type_only():
    a = rt(name="invoice", fields=[fld(name="name")])
    b = rt(name="vendor", identity="same name", fields=[fld(name="name")])
    assert validate(schema([a, b])) == []


# Enums
def test_enums_enum_needs_2_to_6_unique_values():
    def enum(values):
        return schema([rt(fields=[fld(name="status", type="enum", allowed_values=values)])])

    assert validate(enum(["paid", "unpaid"])) == []
    assert validate(enum(["a", "b", "c", "d", "e", "f"])) == []
    assert validate(enum(None))
    assert validate(enum([]))
    assert validate(enum(["only"]))
    assert validate(enum(["a", "b", "c", "d", "e", "f", "g"]))
    assert validate(enum(["paid", "paid"]))


def test_enums_non_enum_has_no_allowed_values():
    assert validate(schema([rt(fields=[fld(type="money")])])) == []
    assert validate(schema([rt(fields=[fld(type="money", allowed_values=["a", "b"])])]))
    assert validate(schema([rt(fields=[fld(type="string", allowed_values=[])])]))


# Identity
def test_identity_extracted_needs_identity():
    assert validate(schema([rt(source="extracted", identity="same number")])) == []
    assert validate(schema([rt(source="extracted", identity=None)]))
    assert validate(schema([rt(source="extracted", identity="")]))
    assert validate(schema([rt(source="extracted", identity="   ")]))


def test_identity_thread_has_no_identity():
    assert validate(schema([rt(source="thread", identity=None)])) == []
    assert validate(schema([rt(source="thread", identity="same number")]))


# Origin x support
def test_origin_inferred_not_found_rejected():
    assert validate(schema([rt(fields=[fld(origin="inferred", support="found")])])) == []
    assert validate(schema([rt(fields=[fld(origin="inferred", support="not_found")])]))
    # explicit + not_found is allowed
    assert validate(schema([rt(fields=[fld(origin="explicit", support="not_found")])])) == []


def test_origin_observed_needs_found_and_justification():
    ok = fld(origin="observed", support="found", justification="threads show status")
    assert validate(schema([rt(fields=[ok])])) == []
    no_just = fld(origin="observed", support="found", justification=None)
    assert validate(schema([rt(fields=[no_just])]))
    assert validate(schema([rt(fields=[fld(origin="observed", justification="")])]))
    not_found = fld(origin="observed", support="not_found", justification="x")
    assert validate(schema([rt(fields=[not_found])]))


# Text
def test_text_no_empty_labels_or_descriptions():
    assert validate(schema()) == []
    assert validate(schema([rt(label="")]))
    assert validate(schema([rt(description="")]))
    assert validate(schema([rt(fields=[fld(label="")])]))
    assert validate(schema([rt(fields=[fld(description="")])]))
    assert validate(schema([rt(fields=[fld(label="  ")])]))


def test_errors_are_strings():
    errs = validate(schema(rts=[]))
    assert errs and all(isinstance(e, str) and e for e in errs)


def test_isolated_rule_does_not_fire_others():
    # a single violated rule yields errors; baseline stays clean
    assert validate(schema([rt(source="thread", identity="x")]))
    assert validate(schema()) == []
