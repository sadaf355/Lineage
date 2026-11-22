"""mfa replay protection and recovery codes"""
from alembic import op
import sqlalchemy as sa

revision = 'd3b9e6a1f471'
down_revision = 'c7e1f4a9d052'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("mfa_last_step", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("mfa_recovery_hashes", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("users", "mfa_recovery_hashes")
    op.drop_column("users", "mfa_last_step")
