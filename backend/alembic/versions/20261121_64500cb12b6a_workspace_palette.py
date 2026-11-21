"""workspace palette

The look the user picked for the workspace's generated app (frontend/theme.md §10.3):
one of the ids in app/agent/palettes.py. Existing workspaces get the default, violet,
which is how they already look.

Revision ID: 64500cb12b6a
Revises: 7c3f1e2d9a4b
Create Date: 2026-11-21 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "64500cb12b6a"
down_revision: str | None = "7c3f1e2d9a4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces", sa.Column("palette", sa.Text(), server_default="violet", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("workspaces", "palette")
