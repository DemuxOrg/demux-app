"""Who may use Demux (see `app/services/access.py` for the rule).

- `billing_customers`: one row per Stripe customer, mirrored from Stripe by the webhook
  (`app/services/billing.py`). Holds only what the access rule needs: the customer's
  email and their best subscription's status and trial end. Never card data.
- `access_grants`: free access given by an admin (/admin/access) to one email: beta
  users, friends, partners. Optional expiry; revoking keeps the row for the record.

Emails are stored lowercased and matched against the login email (`users.email`).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, false
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class BillingCustomer(IdMixin, TimestampMixin, Base):
    __tablename__ = "billing_customers"

    stripe_customer_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    # The customer's best subscription (active > trialing > past_due, else the newest).
    subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    # That subscription's free-trial end (when Stripe first charges), if it had a trial.
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )


class AccessGrant(IdMixin, TimestampMixin, Base):
    __tablename__ = "access_grants"

    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
