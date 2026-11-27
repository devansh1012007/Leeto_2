"""initial schema — full DDL

Revision ID: 0001
Revises:
Create Date: 2026-11-25

Corrections applied: R-03/E.1 (gt answer packs), R-15/B4 (idempotency retention),
R-16/B11 (node sub-states), R-31 (weight_multiplier), R-32/E.1 (AP overlap trigger),
R-33/E.1 (ledger origins), R-02 (no runner DB role).
"""
import pathlib

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql = pathlib.Path(__file__).parents[1].joinpath("schema.sql").read_text()
    # strip psql-style backslash commands (none expected) and run as one script
    op.execute(sql)


def downgrade() -> None:
    raise RuntimeError("expand/contract only: roll forward with a new migration (Phase 2 rule)")
