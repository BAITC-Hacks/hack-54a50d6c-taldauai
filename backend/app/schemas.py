from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_segment_id: str | None
    start: float
    end: float
    speaker_label: str | None
    text: str
    suggested_text: str | None
    lang: Literal["ru", "kk", "mixed"] | None


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    speaker_label: str
    name: str
    role: str
    auto_detected: bool


class ActionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meeting_id: str
    source_task_id: str | None
    task: str
    assignee: str | None
    speaker_label: str | None
    assigner_speaker_label: str | None
    deadline_raw: str | None
    deadline_date: date | None
    status: Literal["in_progress", "done"]
    urgency: Literal["high", "medium", "low"]
    quote: str
    timestamp: float
    needs_review: bool
    source_segment_ids: list[str]
    revision: int
    reminded_at: datetime | None


class ActionItemWithState(ActionItemOut):
    meeting_title: str
    state: Literal["in_progress", "due_soon", "overdue", "done"]


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    date: datetime
    status: str
    summary: str
    audio_path: str | None
    consent_confirmed: bool
    error_message: str | None
    num_speakers: int | None
    warnings: list[str]
    created_at: datetime
    participants: list[ParticipantOut]
    segments: list[SegmentOut]
    action_items: list[ActionItemOut]


class ParticipantPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=500)


class ActionItemPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    expected_revision: int = Field(ge=1)

    @field_validator("task", "status", "urgency", "needs_review")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Поле не может быть null")
        return value

    assignee: str | None = Field(default=None, min_length=1, max_length=255)
    speaker_label: str | None = Field(default=None, min_length=1, max_length=50)
    deadline_date: date | None = None
    status: Literal["in_progress", "done"] | None = None
    urgency: Literal["high", "medium", "low"] | None = None
    task: str | None = Field(default=None, min_length=1)
    needs_review: bool | None = None


class ReminderOut(BaseModel):
    text: str
    action_item: ActionItemOut


class ActionItemCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    task: str = Field(min_length=1)
    assignee: str | None = Field(default=None, min_length=1, max_length=255)
    speaker_label: str | None = None
    deadline_date: date | None = None
