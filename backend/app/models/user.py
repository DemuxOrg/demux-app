"""`users` table.

Responsible for the User model: one row per person using Demux, identified by a
unique email and (once signed in with Google) a unique `google_sub`. Google tokens are
stored encrypted (Fernet, see app/auth/crypto.py) and never leave the backend.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    google_sub: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    needs_reconnect: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
