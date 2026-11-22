"""audit hash chain: seq, prev_hash, event_hash on audit_events"""
from alembic import op
import sqlalchemy as sa

revision = '9c2e5f1a7d33'
down_revision = '7a1d9e0b4c22'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('seq', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('prev_hash', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('event_hash', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.drop_column('event_hash')
        batch_op.drop_column('prev_hash')
        batch_op.drop_column('seq')
