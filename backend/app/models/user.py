"""`users` table.

One row per person using Demux. Two independent identities live here:

- **Login** (written by better-auth in the frontend): `email`, `name`, `first_name`,
  `last_name` (asked at sign-up, editable on the profile page), `email_verified`,
  `image`. The password hash is in `auth_accounts`, sessions in `auth_sessions`.
- **Gmail connection** (written by the backend's Google OAuth flow): `gmail_email`,
  `google_sub` and the encrypted tokens (Fernet, see app/auth/crypto.py). The tokens
  never leave the backend. The Gmail address can differ from the login email.
- **Admin** (`is_admin`): may open /admin. ADMIN_EMAILS in the environment also grants it.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Login (better-auth)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    first_name: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    last_name: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    image: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Gmail connection (backend-owned OAuth)
    gmail_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_sub: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    needs_reconnect: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
