"""Shapes of the server-to-server access endpoints (`app/api/routes/billing.py`)."""

from typing import Annotated

from pydantic import BaseModel, StringConstraints

# Light check only (no email-validator dependency); the code sent at sign-up proves it.
EmailAddress = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]


class SignupCheck(BaseModel):
    email: EmailAddress


class SignupVerdict(BaseModel):
    allowed: bool
