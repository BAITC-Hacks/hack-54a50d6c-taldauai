from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="converting")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    num_speakers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    ml_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    segments: Mapped[list[Segment]] = relationship(back_populates="meeting", cascade="all, delete-orphan", passive_deletes=True, order_by="Segment.start")
    participants: Mapped[list[Participant]] = relationship(back_populates="meeting", cascade="all, delete-orphan", passive_deletes=True, order_by="Participant.id")
    action_items: Mapped[list[ActionItem]] = relationship(back_populates="meeting", cascade="all, delete-orphan", passive_deletes=True, order_by="ActionItem.id")


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    source_segment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    start: Mapped[float] = mapped_column(Float, nullable=False)
    end: Mapped[float] = mapped_column(Float, nullable=False)
    speaker_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    lang: Mapped[str | None] = mapped_column(String(16), nullable=True)

    meeting: Mapped[Meeting] = relationship(back_populates="segments")


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker_label: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(500), nullable=False)
    auto_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    meeting: Mapped[Meeting] = relationship(back_populates="participants")


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    source_task_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    speaker_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    assigner_speaker_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    deadline_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deadline_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    urgency: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_segment_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    meeting: Mapped[Meeting] = relationship(back_populates="action_items")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("action_item_id", "revision", "kind", name="uq_notification_revision_kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    action_item_id: Mapped[str] = mapped_column(ForeignKey("action_items.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
