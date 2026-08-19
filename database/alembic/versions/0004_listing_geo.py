"""listing : colonnes de géolocalisation (Phase 7 — géocodage des annonces)

Revision ID: 0004_listing_geo
Revises: 0003_dvf_id_mutation_unique
Create Date: 2026-08-18
"""
from __future__ import annotations

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0004_listing_geo"
down_revision: str | None = "0003_dvf_id_mutation_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("listing", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("listing", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
    op.add_column(
        "listing",
        sa.Column(
            "location",
            geoalchemy2.Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=True,
        ),
    )
    op.add_column("listing", sa.Column("insee_code", sa.String(5), nullable=True))
    op.add_column(
        "listing", sa.Column("geocoded_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("listing", sa.Column("geocoding_score", sa.Numeric(4, 3), nullable=True))
    op.create_index("ix_listing_insee_code", "listing", ["insee_code"])
    op.create_index("ix_listing_location", "listing", ["location"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_index("ix_listing_location", table_name="listing")
    op.drop_index("ix_listing_insee_code", table_name="listing")
    op.drop_column("listing", "geocoding_score")
    op.drop_column("listing", "geocoded_at")
    op.drop_column("listing", "insee_code")
    op.drop_column("listing", "location")
    op.drop_column("listing", "longitude")
    op.drop_column("listing", "latitude")
