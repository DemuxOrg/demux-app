"""`users` table.

Responsible for the User model: one row per person using Demux, identified by a
unique email. Real auth (Google OAuth) arrives in Phase 1; until then the dev stub in
app/api/deps.py creates a fixed dev user.
"""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
