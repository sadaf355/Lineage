"""phase E: signed integrity manifests"""
from alembic import op
import sqlalchemy as sa

revision = '7a1d9e0b4c22'
down_revision = '5c7451c3916e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('signed_manifests',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('incident_id', sa.String(), nullable=False),
    sa.Column('generated_by', sa.String(), nullable=True),
    sa.Column('key_id', sa.String(), nullable=False),
    sa.Column('manifest_sha256', sa.String(), nullable=False),
    sa.Column('envelope_json', sa.Text(), nullable=False),
    sa.Column('has_timestamp', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['generated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('signed_manifests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_signed_manifests_incident_id'), ['incident_id'], unique=False)


def downgrade():
    with op.batch_alter_table('signed_manifests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_signed_manifests_incident_id'))
    op.drop_table('signed_manifests')
