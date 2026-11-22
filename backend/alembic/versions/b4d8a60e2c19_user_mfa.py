"""user mfa columns

Revision ID: b4d8a60e2c19
Revises: 9c2e5f1a7d33
"""
from alembic import op
import sqlalchemy as sa

revision = "b4d8a60e2c19"
down_revision = "9c2e5f1a7d33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_secret", sa.String(), nullable=True))
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=True, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "mfa_secret")
