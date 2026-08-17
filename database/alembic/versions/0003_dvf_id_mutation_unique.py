"""transaction_dvf.id_mutation : index simple -> contrainte UNIQUE

Permet l'upsert idempotent par mutation (ON CONFLICT (id_mutation)).

Revision ID: 0003_dvf_id_mutation_unique
Revises: 0002_initial_schema
Create Date: 2026-08-17
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_dvf_id_mutation_unique"
down_revision: str | None = "0002_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_transaction_dvf_id_mutation", table_name="transaction_dvf")
    op.create_unique_constraint(
        "uq_transaction_dvf_id_mutation", "transaction_dvf", ["id_mutation"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_transaction_dvf_id_mutation", "transaction_dvf", type_="unique"
    )
    op.create_index(
        "ix_transaction_dvf_id_mutation", "transaction_dvf", ["id_mutation"]
    )
