from __future__ import annotations

import shutil
from datetime import date as date_type, datetime, time, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session, selectinload

from .config import settings
from .database import get_db
from .models import ActionItem, Meeting, Participant, Notification
from .schemas import (
    ActionItemOut,
    ActionItemCreate,
    ActionItemPatch,
    ActionItemWithState,
    MeetingOut,
    ParticipantOut,
    ParticipantPatch,
    ReminderOut,
)
from .services.export import build_protocol_docx
from .services.processor import process_meeting


from .services.reminders import lifespan, active_notifications

app = FastAPI(lifespan=lifespan, title="TaldauAI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

meeting_options = (
    selectinload(Meeting.participants),
    selectinload(Meeting.segments),
    selectinload(Meeting.action_items),
)


def _meeting_or_404(session: Session, meeting_id: str) -> Meeting:
    meeting = session.scalar(select(Meeting).where(Meeting.id == meeting_id).options(*meeting_options))
    if meeting is None:
        raise HTTPException(status_code=404, detail="Совещание не найдено")
    return meeting


def _action_state(action: ActionItem) -> str:
    if action.status == "done":
        return "done"
    if action.deadline_date is None:
        return "in_progress"
    remaining = (action.deadline_date - datetime.now(ZoneInfo(settings.timezone)).date()).days
    if remaining < 0:
        return "overdue"
    if remaining <= 2:
        return "due_soon"
    return "in_progress"


@app.get("/api/health")
def health(session: Session = Depends(get_db)) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.get("/api/meetings", response_model=list[MeetingOut])
def list_meetings(session: Session = Depends(get_db)) -> list[Meeting]:
    return list(session.scalars(select(Meeting).options(*meeting_options).order_by(Meeting.date.desc())).all())


@app.get("/api/meetings/{meeting_id}", response_model=MeetingOut)
def get_meeting(meeting_id: str, session: Session = Depends(get_db)) -> Meeting:
    return _meeting_or_404(session, meeting_id)


@app.post("/api/meetings", response_model=MeetingOut, status_code=201)
def create_meeting(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1),
    meeting_date: str = Form(..., alias="date"),
    consent_confirmed: bool = Form(...),
    num_speakers: int | None = Form(default=None, ge=1, le=32),
    session: Session = Depends(get_db),
) -> Meeting:
    if not consent_confirmed:
        raise HTTPException(status_code=400, detail="Необходимо подтвердить согласие участников")
    try:
        parsed_date = date_type.fromisoformat(meeting_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Дата должна быть в формате YYYY-MM-DD") from exc

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "recording.webm").suffix.lower()[:12] or ".bin"
    meeting_id = f"meeting-{uuid4().hex[:12]}"
    destination = settings.uploads_dir / f"{meeting_id}{suffix}"
    with destination.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    meeting = Meeting(
        id=meeting_id,
        title=title.strip(),
        date=datetime.combine(parsed_date, time(hour=9), tzinfo=ZoneInfo(settings.timezone)),
        status="converting",
        summary="",
        audio_path=str(destination),
        consent_confirmed=True,
        error_message=None,
        num_speakers=num_speakers,
        warnings=[],
    )
    session.add(meeting)
    session.commit()
    background_tasks.add_task(process_meeting, meeting_id)
    return _meeting_or_404(session, meeting_id)


@app.patch("/api/participants/{participant_id}", response_model=ParticipantOut)
def patch_participant(participant_id: int, payload: ParticipantPatch, session: Session = Depends(get_db)) -> Participant:
    participant = session.get(Participant, participant_id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Участник не найден")
    previous_name = participant.name
    participant.name = payload.name.strip()
    participant.role = payload.role.strip()
    participant.auto_detected = False
    if previous_name != participant.name:
        session.execute(
            update(ActionItem).where(
                ActionItem.meeting_id == participant.meeting_id,
                ActionItem.speaker_label == participant.speaker_label,
            ).values(assignee=participant.name, needs_review=True, revision=ActionItem.revision + 1)
        )
    session.commit()
    session.refresh(participant)
    return participant


@app.patch("/api/action-items/{action_id}", response_model=ActionItemOut)
def patch_action_item(action_id: str, payload: ActionItemPatch, session: Session = Depends(get_db)) -> ActionItem:
    action = session.scalar(select(ActionItem).where(ActionItem.id == action_id).with_for_update())
    if action is None:
        raise HTTPException(status_code=404, detail="Поручение не найдено")
    if payload.expected_revision != action.revision:
        raise HTTPException(status_code=409, detail="Поручение изменилось. Обновите страницу и проверьте новую версию")
    previous_review = action.needs_review
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
    changed = any(getattr(action, key) != value for key, value in changes.items() if key != "needs_review")
    if changed and changes.get("needs_review") is False:
        raise HTTPException(status_code=422, detail="Сначала сохраните изменения, затем подтвердите поручение отдельно")
    if "assignee" in changes and "speaker_label" not in changes and changes["assignee"] != action.assignee:
        changes["speaker_label"] = None
    for field, value in changes.items():
        setattr(action, field, value)
    _validate_assignee(session, action)
    review_changed = any(key in changes for key in ("task", "assignee", "speaker_label", "deadline_date", "urgency")) and changed
    if review_changed:
        action.needs_review = True
    if action.needs_review is False and (not action.assignee or action.deadline_date is None):
        raise HTTPException(status_code=422, detail="Укажите ответственного и срок перед подтверждением")
    if changed or action.needs_review != previous_review:
        action.revision += 1
    session.commit()
    session.refresh(action)
    return action


def _validate_assignee(session: Session, action: ActionItem) -> None:
    if action.speaker_label:
        participant = session.scalar(select(Participant).where(
            Participant.meeting_id == action.meeting_id,
            Participant.speaker_label == action.speaker_label,
        ))
        if participant is None or participant.name != action.assignee:
            raise HTTPException(status_code=422, detail="Ответственный не соответствует выбранному говорящему")


@app.post("/api/meetings/{meeting_id}/action-items", response_model=ActionItemOut, status_code=201)
def create_action_item(meeting_id: str, payload: ActionItemCreate, session: Session = Depends(get_db)) -> ActionItem:
    meeting = _meeting_or_404(session, meeting_id)
    if meeting.status != "done":
        raise HTTPException(status_code=409, detail="Дождитесь завершения обработки")
    action = ActionItem(id=f"manual-{uuid4().hex}", meeting_id=meeting_id,
                        **payload.model_dump(), quote="Добавлено секретарём", timestamp=0,
                        needs_review=True, source_segment_ids=[], status="in_progress", urgency="medium")
    _validate_assignee(session, action)
    session.add(action)
    session.commit()
    session.refresh(action)
    return action


@app.get("/api/notifications")
def list_notifications(session: Session = Depends(get_db)) -> list[dict]:
    return [dict(id=n.id, action_item_id=a.id, meeting_id=a.meeting_id, assignee=a.assignee,
                 kind=n.kind, message=n.message, created_at=n.created_at, read_at=n.read_at)
            for n, a in session.execute(active_notifications()).all()]


@app.patch("/api/notifications/{notification_id}/read")
def read_notification(notification_id: int, session: Session = Depends(get_db)) -> dict:
    notification = session.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Напоминание не найдено")
    notification.read_at = notification.read_at or datetime.now(timezone.utc)
    session.commit()
    return {"id": notification.id, "read_at": notification.read_at}


@app.delete("/api/action-items/{action_id}", status_code=204)
def delete_action_item(action_id: str, session: Session = Depends(get_db)) -> Response:
    action = session.get(ActionItem, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Поручение не найдено")
    session.delete(action)
    session.commit()
    return Response(status_code=204)


@app.get("/api/action-items", response_model=list[ActionItemWithState])
def list_action_items(
    status: str | None = Query(default=None),
    assignee: str | None = Query(default=None),
    meeting_id: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> list[dict]:
    statement = select(ActionItem, Meeting.title).join(Meeting).order_by(ActionItem.deadline_date.asc().nullslast(), ActionItem.id)
    if status in {"in_progress", "done"}:
        statement = statement.where(ActionItem.status == status)
    if assignee:
        statement = statement.where(ActionItem.assignee == assignee)
    if meeting_id:
        statement = statement.where(ActionItem.meeting_id == meeting_id)
    result = []
    for action, meeting_title in session.execute(statement).all():
        state = _action_state(action)
        if status in {"due_soon", "overdue"} and state != status:
            continue
        item = ActionItemOut.model_validate(action).model_dump()
        result.append({**item, "meeting_title": meeting_title, "state": state})
    return result


@app.post("/api/action-items/{action_id}/remind", response_model=ReminderOut)
def remind_action_item(action_id: str, session: Session = Depends(get_db)) -> dict:
    action = session.get(ActionItem, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Поручение не найдено")
    if action.needs_review:
        raise HTTPException(status_code=409, detail="Сначала проверьте и подтвердите поручение")
    meeting = session.get(Meeting, action.meeting_id)
    deadline = action.deadline_date.strftime("%d.%m.%Y") if action.deadline_date else action.deadline_raw or "не указан"
    reminder = (
        f"Здравствуйте, {action.assignee or 'ответственный'}!\n\n"
        f"Напоминаем о поручении: {action.task}\n"
        f"Срок исполнения: {deadline}\n"
        f"Совещание: {meeting.title if meeting else action.meeting_id}\n\n"
        f"Ссылка: http://localhost:5173/meetings/{action.meeting_id}?t={action.timestamp:g}"
    )
    action.reminded_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(action)
    return {"text": reminder, "action_item": action}


@app.get("/api/meetings/{meeting_id}/export.docx")
def export_meeting(meeting_id: str, session: Session = Depends(get_db)) -> StreamingResponse:
    meeting = _meeting_or_404(session, meeting_id)
    if meeting.status != "done":
        raise HTTPException(status_code=409, detail="Дождитесь успешного завершения обработки")
    if any(action.needs_review for action in meeting.action_items):
        raise HTTPException(status_code=409, detail="Подтвердите или удалите все поручения перед экспортом")
    document = build_protocol_docx(meeting)
    filename = quote(f"Протокол {meeting.title}.docx")
    return StreamingResponse(
        document,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
