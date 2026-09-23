"""Persistent local inbox. No email or external API delivery."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from sqlalchemy import select, or_, and_
from sqlalchemy.dialects.postgresql import insert

from ..config import settings
from ..database import SessionLocal
from ..models import ActionItem, Notification


def local_today(now=None):
    return (now or datetime.now(ZoneInfo(settings.timezone))).astimezone(ZoneInfo(settings.timezone)).date()


def eligible(today):
    return (ActionItem.needs_review.is_(False), ActionItem.status == "in_progress",
            ActionItem.assignee.is_not(None), ActionItem.deadline_date <= today + timedelta(days=2))


def generate_notifications(session_factory=None, now=None):
    today = local_today(now)
    with (session_factory or SessionLocal)() as session:
        for action in session.scalars(select(ActionItem).where(*eligible(today)).with_for_update()):
            kind = "overdue" if action.deadline_date < today else "due_soon"
            prefix = "Срок просрочен" if kind == "overdue" else "Приближается срок"
            session.execute(insert(Notification).values(
                action_item_id=action.id, revision=action.revision, kind=kind,
                message=f"{prefix}: {action.task}. Ответственный: {action.assignee}. Срок: {action.deadline_date:%d.%m.%Y}.",
            ).on_conflict_do_nothing(constraint="uq_notification_revision_kind"))
        session.commit()


def active_notifications():
    today = local_today()
    return select(Notification, ActionItem).join(ActionItem).where(
        *eligible(today), Notification.revision == ActionItem.revision,
        or_(and_(Notification.kind == "overdue", ActionItem.deadline_date < today),
            and_(Notification.kind == "due_soon", ActionItem.deadline_date >= today)),
    ).order_by(Notification.created_at.desc(), Notification.id.desc())


@asynccontextmanager
async def lifespan(app):
    stop = asyncio.Event()

    async def worker():
        while not stop.is_set():
            try:
                await asyncio.to_thread(generate_notifications)
            except Exception:
                logging.getLogger(__name__).exception("Local reminder scan failed; will retry")
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.reminders_interval)
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(worker()) if settings.reminders_enabled else None
    try:
        yield
    finally:
        stop.set()
        if task:
            await task
