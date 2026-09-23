"""Create meetings, segments, participants and action items.

Revision ID: 20260923_0001
Revises:
Create Date: 2026-09-23
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260923_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meetings",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("audio_path", sa.Text(), nullable=True),
        sa.Column("consent_confirmed", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "segments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("meeting_id", sa.String(length=80), nullable=False),
        sa.Column("start", sa.Float(), nullable=False),
        sa.Column("end", sa.Float(), nullable=False),
        sa.Column("speaker_label", sa.String(length=50), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("lang", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_segments_meeting_id"), "segments", ["meeting_id"], unique=False)
    op.create_table(
        "participants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("meeting_id", sa.String(length=80), nullable=False),
        sa.Column("speaker_label", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=500), nullable=False),
        sa.Column("auto_detected", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_participants_meeting_id"), "participants", ["meeting_id"], unique=False)
    op.create_table(
        "action_items",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("meeting_id", sa.String(length=80), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("assignee", sa.String(length=255), nullable=False),
        sa.Column("speaker_label", sa.String(length=50), nullable=False),
        sa.Column("deadline_raw", sa.String(length=255), nullable=False),
        sa.Column("deadline_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("urgency", sa.String(length=16), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_action_items_meeting_id"), "action_items", ["meeting_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_action_items_meeting_id"), table_name="action_items")
    op.drop_table("action_items")
    op.drop_index(op.f("ix_participants_meeting_id"), table_name="participants")
    op.drop_table("participants")
    op.drop_index(op.f("ix_segments_meeting_id"), table_name="segments")
    op.drop_table("segments")
    op.drop_table("meetings")
