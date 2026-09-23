"""Regenerate one saved meeting summary locally, without rerunning audio models.

Usage from backend/: python -m app.refresh_summary MEETING_ID
"""
import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .config import PROJECT_ROOT
from .database import SessionLocal
from .models import Meeting, ActionItem


def refresh_summary(meeting_id: str):
    sys.path.insert(0, str(PROJECT_ROOT))
    from ml.summary import summarize_meeting

    with SessionLocal() as session:
        meeting = session.scalar(select(Meeting).where(Meeting.id == meeting_id).options(
            selectinload(Meeting.segments), selectinload(Meeting.action_items)))
        if meeting is None or meeting.status != 'done':
            raise ValueError('A completed meeting is required')
        segments = [{'id': s.source_segment_id or str(s.id), 'text': s.text} for s in meeting.segments]
        actions = list(meeting.action_items)
        revisions = {a.id: a.revision for a in actions}
        tasks = [{'description': a.task, 'assignee_name': a.assignee,
                  'due_date': a.deadline_date.isoformat() if a.deadline_date else None,
                  'due_text': a.deadline_raw, 'source_segment_ids': a.source_segment_ids} for a in actions]
    summary, warnings = summarize_meeting(segments, tasks)
    with SessionLocal() as session:
        meeting = session.scalar(select(Meeting).where(Meeting.id == meeting_id).with_for_update())
        current = dict(session.execute(select(ActionItem.id, ActionItem.revision).where(
            ActionItem.meeting_id == meeting_id).with_for_update()).all())
        if meeting is None or current != revisions:
            raise RuntimeError('Tasks changed during summary generation; rerun with their new version')
        meeting.summary = summary
        old_warnings = [w for w in meeting.warnings if not w.startswith(("Summary statement omitted:", "Narrative summary unavailable"))]
        meeting.warnings = list(dict.fromkeys([*old_warnings, *warnings]))
        session.commit()
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('meeting_id')
    print(refresh_summary(parser.parse_args().meeting_id))
