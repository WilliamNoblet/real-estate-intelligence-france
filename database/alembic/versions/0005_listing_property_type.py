"""listing : ajout de property_type (type de bien)

Revision ID: 0005_listing_property_type
Revises: 0004_listing_geo
Create Date: 2026-08-18
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_listing_property_type"
down_revision: str | None = "0004_listing_geo"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # server_default 'UNKNOWN' pour les lignes existantes, puis retiré (le défaut vient de l'app).
    op.add_column(
        "listing",
        sa.Column("property_type", sa.String(20), nullable=False, server_default="UNKNOWN"),
    )
    op.alter_column("listing", "property_type", server_default=None)


def downgrade() -> None:
    op.drop_column("listing", "property_type")
