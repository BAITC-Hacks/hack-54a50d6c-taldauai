"""Persist the ML JSON v1 review fields.

Revision ID: 20260923_0002
Revises: 20260923_0001
Create Date: 2026-09-23
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260923_0002"
down_revision: str | None = "20260923_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("meetings", sa.Column("num_speakers", sa.Integer(), nullable=True))
    op.add_column("meetings", sa.Column("warnings", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False))
    op.add_column("meetings", sa.Column("ml_result", sa.JSON(), nullable=True))

    op.add_column("segments", sa.Column("source_segment_id", sa.String(length=80), nullable=True))
    op.add_column("segments", sa.Column("suggested_text", sa.Text(), nullable=True))
    op.alter_column("segments", "speaker_label", existing_type=sa.String(length=50), nullable=True)
    op.alter_column("segments", "lang", existing_type=sa.String(length=16), nullable=True)

    op.add_column("action_items", sa.Column("source_task_id", sa.String(length=80), nullable=True))
    op.add_column("action_items", sa.Column("assigner_speaker_label", sa.String(length=50), nullable=True))
    # Existing seeded/manual tasks are already curated. ML-created tasks pass their own flag.
    op.add_column("action_items", sa.Column("needs_review", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("action_items", sa.Column("source_segment_ids", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False))
    op.alter_column("action_items", "assignee", existing_type=sa.String(length=255), nullable=True)
    op.alter_column("action_items", "speaker_label", existing_type=sa.String(length=50), nullable=True)
    op.alter_column("action_items", "deadline_raw", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    op.alter_column("action_items", "deadline_raw", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("action_items", "speaker_label", existing_type=sa.String(length=50), nullable=False)
    op.alter_column("action_items", "assignee", existing_type=sa.String(length=255), nullable=False)
    op.drop_column("action_items", "source_segment_ids")
    op.drop_column("action_items", "needs_review")
    op.drop_column("action_items", "assigner_speaker_label")
    op.drop_column("action_items", "source_task_id")
    op.alter_column("segments", "lang", existing_type=sa.String(length=16), nullable=False)
    op.alter_column("segments", "speaker_label", existing_type=sa.String(length=50), nullable=False)
    op.drop_column("segments", "suggested_text")
    op.drop_column("segments", "source_segment_id")
    op.drop_column("meetings", "ml_result")
    op.drop_column("meetings", "warnings")
    op.drop_column("meetings", "num_speakers")
