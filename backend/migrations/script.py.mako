"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import pathlib

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def _sql(name: str) -> str:
    return pathlib.Path(__file__).parent.joinpath(name).read_text()


def upgrade() -> None:
    ${imports if imports else ""}
    op.execute(_sql("${upgrade_sql}"))


def downgrade() -> None:
    raise RuntimeError("expand/contract only: roll forward with a new migration (Phase 2 rule)")
