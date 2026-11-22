"""unique (incident_id, seq) on audit_events so a forked chain is impossible"""
from alembic import op

revision = 'c7e1f4a9d052'
down_revision = 'b4d8a60e2c19'
branch_labels = None
depends_on = None


def upgrade():
    # Fails loudly if a case already has two events with the same seq (a forked chain). Fix those rows by hand first.
    op.create_index('ux_audit_incident_seq', 'audit_events', ['incident_id', 'seq'], unique=True)


def downgrade():
    op.drop_index('ux_audit_incident_seq', table_name='audit_events')
