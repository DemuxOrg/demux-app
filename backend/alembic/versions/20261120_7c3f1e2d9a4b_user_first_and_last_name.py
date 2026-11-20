"""user first and last name

Asked at sign-up (better-auth `additionalFields`, mapped in frontend/src/lib/auth.ts)
and editable on the profile page. Existing users get empty names until they set them.

Revision ID: 7c3f1e2d9a4b
Revises: d0d1d5378501
Create Date: 2026-11-20 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "7c3f1e2d9a4b"
down_revision: str | None = "d0d1d5378501"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.Text(), server_default="", nullable=False))
    op.add_column("users", sa.Column("last_name", sa.Text(), server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
