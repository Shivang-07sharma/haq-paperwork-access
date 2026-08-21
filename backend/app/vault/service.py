"""Document vault and the reminders that hang off it.

A vault that only stores files is a folder. The value is in knowing when a paper
goes stale: an income certificate is typically accepted for a year, and people
discover it has lapsed at the counter, after travelling to the office. So every
document carries an expiry where one applies, and reminders are generated ahead
of it.

Reminders are stored as i18n keys plus arguments, never as finished sentences,
so a person who switches language sees their reminders switch too.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Application, Document, Reminder

EXPIRY_WARNING_DAYS = 60


def document_state(doc: Document, today: date | None = None) -> dict:
    """Classify a document by how much life it has left."""
    today = today or date.today()
    if not doc.expiry_date:
        return {"state": "no_expiry", "days_left": None}

    days_left = (doc.expiry_date - today).days
    if days_left < 0:
        return {"state": "expired", "days_left": days_left}
    if days_left <= EXPIRY_WARNING_DAYS:
        return {"state": "expiring_soon", "days_left": days_left}
    return {"state": "valid", "days_left": days_left}


def list_documents(db: Session, profile_id: int) -> list[Document]:
    stmt = (
        select(Document)
        .where(Document.profile_id == profile_id)
        .order_by(Document.uploaded_at.desc())
    )
    return list(db.scalars(stmt))


def owned_doc_types(db: Session, profile_id: int) -> set[str]:
    return {d.doc_type for d in list_documents(db, profile_id)}


def _has_reminder(db: Session, profile_id: int, title_key: str, document_id, application_id) -> bool:
    stmt = select(Reminder).where(
        Reminder.profile_id == profile_id,
        Reminder.title_key == title_key,
        Reminder.document_id.is_(document_id) if document_id is None else Reminder.document_id == document_id,
        Reminder.application_id.is_(application_id) if application_id is None else Reminder.application_id == application_id,
    )
    return db.scalars(stmt).first() is not None


def sync_reminders(db: Session, profile_id: int, today: date | None = None) -> list[Reminder]:
    """Create any reminders that are now due. Safe to call repeatedly."""
    today = today or date.today()
    created: list[Reminder] = []

    for doc in list_documents(db, profile_id):
        state = document_state(doc, today)
        if state["state"] not in {"expiring_soon", "expired"}:
            continue
        key = "reminder.doc_expired" if state["state"] == "expired" else "reminder.doc_expiring"
        if _has_reminder(db, profile_id, key, doc.id, None):
            continue
        reminder = Reminder(
            profile_id=profile_id,
            document_id=doc.id,
            kind="expiry",
            title_key=key,
            title_args={"doc": doc.doc_type, "date": doc.expiry_date.isoformat()},
            due_date=doc.expiry_date - timedelta(days=EXPIRY_WARNING_DAYS),
        )
        db.add(reminder)
        created.append(reminder)

    # Applications that have gone quiet past their advertised processing time.
    stmt = select(Application).where(
        Application.profile_id == profile_id,
        Application.status.in_(["submitted", "under_review"]),
    )
    for app in db.scalars(stmt):
        submitted = app.updated_at.date() if app.updated_at else today
        waiting = (today - submitted).days
        if waiting < 30:
            continue
        if _has_reminder(db, profile_id, "reminder.follow_up", None, app.id):
            continue
        reminder = Reminder(
            profile_id=profile_id,
            application_id=app.id,
            kind="follow_up",
            title_key="reminder.follow_up",
            title_args={"scheme": app.scheme_name, "days": waiting},
            due_date=today,
        )
        db.add(reminder)
        created.append(reminder)

    if created:
        db.commit()
    return created


def list_reminders(db: Session, profile_id: int, include_done: bool = False) -> list[Reminder]:
    stmt = select(Reminder).where(Reminder.profile_id == profile_id)
    if not include_done:
        stmt = stmt.where(Reminder.done.is_(False))
    return list(db.scalars(stmt.order_by(Reminder.due_date)))
