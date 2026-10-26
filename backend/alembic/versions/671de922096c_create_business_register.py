
"""create business register

Revision ID: 671de922096c
Revises: 3d3fc726eae9
Create Date: 2026-10-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "671de922096c"
down_revision: Union[str, None] = "3d3fc726eae9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_register",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("business_name", sa.String(length=250), nullable=False),
        sa.Column("normalized_name", sa.String(length=250), nullable=False),
        sa.Column("registration_number", sa.String(length=100), nullable=True),
        sa.Column("tax_identifier", sa.String(length=100), nullable=True),
        sa.Column("phone_number", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column(
            "city",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "state",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column("source_name", sa.String(length=200), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=True),
        sa.Column("matched_taxpayer_id", sa.Integer(), nullable=True),
        sa.Column("match_confidence", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("match_status", sa.String(length=40), nullable=False),
        sa.Column("verification_status", sa.String(length=40), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["matched_taxpayer_id"],
            ["taxpayers.id"],
            name="fk_business_register_matched_taxpayer_id_taxpayers",
            ondelete="SET NULL",
        ),
    )

    op.create_index(
        "ix_business_register_id",
        "business_register",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_business_register_business_name",
        "business_register",
        ["business_name"],
        unique=False,
    )
    op.create_index(
        "ix_business_register_normalized_name",
        "business_register",
        ["normalized_name"],
        unique=False,
    )
    op.create_index(
        "ix_business_register_registration_number",
        "business_register",
        ["registration_number"],
        unique=False,
    )
    op.create_index(
        "ix_business_register_tax_identifier",
        "business_register",
        ["tax_identifier"],
        unique=False,
    )
    op.create_index(
        "ix_business_register_phone_number",
        "business_register",
        ["phone_number"],
        unique=False,
    )
    op.create_index(
        "ix_business_register_tax_year",
        "business_register",
        ["tax_year"],
        unique=False,
    )
    op.create_index(
        "ix_business_register_matched_taxpayer_id",
        "business_register",
        ["matched_taxpayer_id"],
        unique=False,
    )
    op.create_index(
        "ix_business_register_match_status",
        "business_register",
        ["match_status"],
        unique=False,
    )
    op.create_index(
        "ix_business_register_verification_status",
        "business_register",
        ["verification_status"],
        unique=False,
    )
    op.create_index(
        "ix_business_register_name_city",
        "business_register",
        ["normalized_name", "city"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_business_register_name_city",
        table_name="business_register",
    )
    op.drop_index(
        "ix_business_register_verification_status",
        table_name="business_register",
    )
    op.drop_index(
        "ix_business_register_match_status",
        table_name="business_register",
    )
    op.drop_index(
        "ix_business_register_matched_taxpayer_id",
        table_name="business_register",
    )
    op.drop_index(
        "ix_business_register_tax_year",
        table_name="business_register",
    )
    op.drop_index(
        "ix_business_register_phone_number",
        table_name="business_register",
    )
    op.drop_index(
        "ix_business_register_tax_identifier",
        table_name="business_register",
    )
    op.drop_index(
        "ix_business_register_registration_number",
        table_name="business_register",
    )
    op.drop_index(
        "ix_business_register_normalized_name",
        table_name="business_register",
    )
    op.drop_index(
        "ix_business_register_business_name",
        table_name="business_register",
    )
    op.drop_index(
        "ix_business_register_id",
        table_name="business_register",
    )
    op.drop_table("business_register")
