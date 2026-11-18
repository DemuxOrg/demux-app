"""Tables owned by better-auth (the Next.js login framework): sessions, accounts, codes.

better-auth runs in the frontend (`frontend/src/lib/auth.ts`) and reads and writes these
tables directly; it also writes the login columns of `users` (email, name,
email_verified, image). They are declared here so that Alembic owns the schema and the
backend can resolve a session cookie to a user (`app/auth/session.py`).

Column names are snake_case; `frontend/src/lib/auth.ts` maps better-auth's camelCase
field names onto them. Change both together. better-auth checks the schema at startup.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class AuthSession(IdMixin, TimestampMixin, Base):
    """One signed-in browser. The cookie holds `token` (plus a signature)."""

    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuthAccount(IdMixin, TimestampMixin, Base):
    """A way to sign in. Today only `provider_id="credential"` (email + hashed password).

    Not related to the Gmail connection, which lives on `users` (backend-owned OAuth).
    """

    __tablename__ = "auth_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    account_id: Mapped[str] = mapped_column(Text, nullable=False)
    provider_id: Mapped[str] = mapped_column(Text, nullable=False)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    id_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    password: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuthVerification(IdMixin, TimestampMixin, Base):
    """Short-lived one-time codes (the 6-digit email OTP, valid 10 minutes)."""

    __tablename__ = "auth_verifications"

    identifier: Mapped[str] = mapped_column(Text, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
