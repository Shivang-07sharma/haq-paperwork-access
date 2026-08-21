"""Application lifecycle and status tracking.

The status a person cares about is not in our database -- it lives in a
government back office. What this module does is hold the thread: it records
what was applied for, when, under which reference number, and what the office
last said. That is enough to answer the two questions people actually ask, which
are "did I already apply for this?" and "how long has it been?".

Statuses advance only through recorded events, so the timeline shown to the user
is an audit trail rather than a single mutable field.
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..forms.autofill import autofill, render_pdf
from ..models import Application, ApplicationEvent, Profile

STATUSES = [
    "draft", "submitted", "under_review", "documents_requested", "approved", "rejected",
]

# Which statuses can follow which. Guards against a UI bug marking a rejected
# application approved, and keeps the timeline meaningful.
TRANSITIONS = {
    "draft": {"submitted"},
    "submitted": {"under_review", "documents_requested", "approved", "rejected"},
    "under_review": {"documents_requested", "approved", "rejected"},
    "documents_requested": {"under_review", "submitted", "rejected"},
    "approved": set(),
    "rejected": {"submitted"},
}


def generate_reference() -> str:
    year = datetime.now(timezone.utc).year
    return f"HAQ-{year}-{secrets.randbelow(90000) + 10000}"


def get_application(db: Session, profile_id: int, scheme_id: str) -> Application | None:
    stmt = select(Application).where(
        Application.profile_id == profile_id, Application.scheme_id == scheme_id
    )
    return db.scalars(stmt).first()


def list_applications(db: Session, profile_id: int) -> list[Application]:
    stmt = (
        select(Application)
        .where(Application.profile_id == profile_id)
        .order_by(Application.updated_at.desc())
    )
    return list(db.scalars(stmt))


def start_application(
    db: Session,
    profile: Profile,
    scheme: dict,
    scheme_name: str,
    labels: dict,
) -> Application:
    """Create or refresh a draft, filling the form and rendering the PDF."""
    existing = get_application(db, profile.id, scheme["id"])
    app = existing or Application(
        profile_id=profile.id, scheme_id=scheme["id"], scheme_name=scheme_name
    )

    form_id = scheme.get("form_id", "")
    filled = autofill(form_id, profile)
    app.scheme_name = scheme_name
    app.filled_fields = filled.filled
    app.missing_fields = filled.missing_required
    app.completion_percent = filled.completion_percent

    try:
        pdf_path = render_pdf(form_id, profile, scheme, filled, labels)
        app.form_pdf_path = str(pdf_path)
    except Exception:
        # A PDF that fails to draw must not lose the application record.
        app.form_pdf_path = None

    if existing is None:
        db.add(app)
        db.flush()
        db.add(
            ApplicationEvent(
                application_id=app.id, status="draft", note="Form prepared", actor="system"
            )
        )
    db.commit()
    db.refresh(app)
    return app


def advance(
    db: Session, app: Application, status: str, note: str | None = None, actor: str = "user"
) -> Application:
    """Move an application to a new status, recording the change."""
    if status not in STATUSES:
        raise ValueError(f"unknown status: {status}")
    allowed = TRANSITIONS.get(app.status, set())
    if status != app.status and status not in allowed:
        raise ValueError(f"cannot move from {app.status} to {status}")

    app.status = status
    if status == "submitted" and not app.reference_no:
        app.reference_no = generate_reference()

    db.add(ApplicationEvent(application_id=app.id, status=status, note=note, actor=actor))
    db.commit()
    db.refresh(app)
    return app


def days_waiting(app: Application, today: date | None = None) -> int | None:
    if app.status in {"draft", "approved", "rejected"}:
        return None
    today = today or date.today()
    started = app.updated_at.date() if app.updated_at else today
    return (today - started).days
