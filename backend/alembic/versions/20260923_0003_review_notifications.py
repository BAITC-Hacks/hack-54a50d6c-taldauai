"""Version reviewed tasks and persist automatic local reminders."""
from alembic import op
import sqlalchemy as sa

revision = "20260923_0003"
down_revision = "20260923_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("action_items", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.create_table("notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action_item_id", sa.String(100), sa.ForeignKey("action_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("action_item_id", "revision", "kind", name="uq_notification_revision_kind"),
    )
    op.create_index("ix_notifications_action_item_id", "notifications", ["action_item_id"])


def downgrade():
    op.drop_table("notifications")
    op.drop_column("action_items", "revision")
