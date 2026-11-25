"""access: billing customers and free-access grants

Who may sign up and use Demux (app/services/access.py):

- `billing_customers`: Stripe customers mirrored by the webhook (email, best
  subscription status and its trial end).
- `access_grants`: free access an admin gave to one email (/admin/access).

Existing accounts are not touched. After this migration, an account without a
subscription, a trial, free access or admin rights sees the subscribe screen.

Revision ID: e6e6d0fa4670
Revises: 4a72b0dadce2
Create Date: 2026-11-25 23:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6e6d0fa4670"
down_revision: str | None = "4a72b0dadce2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "billing_customers",
        sa.Column("stripe_customer_id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("subscription_id", sa.Text(), nullable=True),
        sa.Column("subscription_status", sa.Text(), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_customer_id"),
    )
    op.create_index(
        op.f("ix_billing_customers_email"), "billing_customers", ["email"], unique=False
    )
    op.create_table(
        "access_grants",
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )


def downgrade() -> None:
    op.drop_table("access_grants")
    op.drop_index(op.f("ix_billing_customers_email"), table_name="billing_customers")
    op.drop_table("billing_customers")
