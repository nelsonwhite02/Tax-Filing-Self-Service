"""add conversation entry sessions

Revision ID: ee4a99e58ae6
Revises: 305b9624badf
Create Date: 2026-09-29 20:00:19.688654

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ee4a99e58ae6'
down_revision: Union[str, None] = '305b9624badf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entry_sessions",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            index=True,
        ),
        sa.Column(
            "taxpayer_id",
            sa.Integer(),
            sa.ForeignKey(
                "taxpayers.id",
            ),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "path",
            sa.String(length=30),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "current_step",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "selected_form_code",
            sa.String(length=30),
            nullable=True,
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_entry_sessions_taxpayer_id",
        "entry_sessions",
        ["taxpayer_id"],
    )

    op.create_index(
        "ix_entry_sessions_status",
        "entry_sessions",
        ["status"],
    )

    op.create_index(
        "ix_entry_sessions_selected_form_code",
        "entry_sessions",
        ["selected_form_code"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_entry_sessions_selected_form_code",
        table_name="entry_sessions",
    )

    op.drop_index(
        "ix_entry_sessions_status",
        table_name="entry_sessions",
    )

    op.drop_index(
        "ix_entry_sessions_taxpayer_id",
        table_name="entry_sessions",
    )

    op.drop_table("entry_sessions")
