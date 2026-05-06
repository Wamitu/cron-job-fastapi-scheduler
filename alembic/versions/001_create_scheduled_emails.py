"""create scheduled_emails table

Revision ID: 001
Revises:
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("cron_expression", sa.String(length=100), nullable=False),
        sa.Column("timezone", sa.String(length=50), nullable=False, server_default="UTC"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduled_emails_id", "scheduled_emails", ["id"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_emails_id", table_name="scheduled_emails")
    op.drop_table("scheduled_emails")
