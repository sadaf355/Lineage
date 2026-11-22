"""Phase I metadata, tombstones and operational counters"""
from alembic import op
import sqlalchemy as sa
revision = "e81a4b2c9d10"
down_revision = "d3b9e6a1f471"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("metadata_snapshots", sa.Column("id", sa.String(), primary_key=True), sa.Column("media_item_id", sa.String(), sa.ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False), sa.Column("parser_name", sa.String(), nullable=False), sa.Column("parser_version", sa.String(), nullable=False), sa.Column("file_sha256", sa.String(), nullable=False), sa.Column("raw_fields_json", sa.Text(), nullable=False), sa.Column("normalized_fields_json", sa.Text(), nullable=False), sa.Column("snapshot_sha256", sa.String(), nullable=False), sa.Column("taken_at", sa.DateTime(), nullable=False))
    op.create_index("ix_metadata_snapshots_media_item_id", "metadata_snapshots", ["media_item_id"])
    op.create_table("case_tombstones", sa.Column("id", sa.String(), primary_key=True), sa.Column("case_id", sa.String(), nullable=False, unique=True), sa.Column("owner_user_id", sa.String()), sa.Column("final_audit_head_hash", sa.String()), sa.Column("deletion_event_json", sa.Text(), nullable=False), sa.Column("deleted_at", sa.DateTime(), nullable=False))
    op.create_index("ix_case_tombstones_case_id", "case_tombstones", ["case_id"])
    op.create_table("operational_events", sa.Column("id", sa.String(), primary_key=True), sa.Column("category", sa.String(), nullable=False), sa.Column("reason", sa.String(), nullable=False), sa.Column("actor_user_id", sa.String()), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_operational_events_category", "operational_events", ["category"])
    op.create_index("ix_operational_events_created_at", "operational_events", ["created_at"])
def downgrade():
    op.drop_table("operational_events"); op.drop_table("case_tombstones"); op.drop_table("metadata_snapshots")
