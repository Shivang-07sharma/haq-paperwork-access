"""HTTP surface.

One router rather than six: at this size, splitting these twenty endpoints
across files would cost more in navigation than it buys in tidiness.

The interesting logic here is `_merge_into_profile`. Documents disagree -- a
ration card and an Aadhaar card will both claim to know your name, with
different OCR quality. Rather than last-write-wins, a field is only overwritten
by a strictly more confident reading, and anything a person typed themselves
outranks every OCR result. Provenance for each field is kept so the UI can show
where a value came from and let the person overrule it.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import (
    ALLOWED_MIME_PREFIXES, DEFAULT_LANGUAGE, LANGUAGES, MAX_UPLOAD_BYTES, STORAGE_DIR,
)
from ..db import get_db
from ..eligibility import (
    ELIGIBLE, NEED_MORE_INFO, all_schemes, build_facts, catalog_meta, evaluate_all,
    evaluate_scheme, get_scheme, unlock_summary,
)
from ..extraction import SUPPORTED_DOC_TYPES, extract, redact
from ..forms.autofill import autofill, form_fields
from ..i18n import available_languages, explain, money, strings_for, t
from ..models import Application, Document, Profile, Reminder
from ..ocr import ocr_available, run_ocr
from ..schemas import (
    FIELD_SPEC_BY_NAME, FIELD_SPECS, TRACKED_FIELDS,
    ApplicationCreate, ProfileCreate, ProfileUpdate, StatusUpdate,
)
from ..tracker import service as tracker
from ..vault import service as vault

router = APIRouter(prefix="/api")

# Manual entry beats any OCR read, so it is given a confidence no engine reaches.
MANUAL_CONFIDENCE = 1.01

# Categories whose headline number is a maximum cover, not money received.
COVER_CATEGORIES = {"health", "insurance"}


def _lang(lang: str | None) -> str:
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


def _day_first(iso: str) -> str:
    """Render an ISO date the way it is read in India: 05/10/2026."""
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return iso


def _get_profile(db: Session, profile_id: int) -> Profile:
    profile = db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="profile not found")
    return profile


# --------------------------------------------------------------------------
# meta
# --------------------------------------------------------------------------

@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "ocr_providers": ocr_available(),
        "schemes": len(all_schemes()),
        "catalog": catalog_meta(),
    }


@router.get("/meta/languages")
def meta_languages() -> list[dict]:
    return available_languages()


@router.get("/meta/strings")
def meta_strings(lang: str = Query(DEFAULT_LANGUAGE)) -> dict:
    return strings_for(_lang(lang))


@router.get("/meta/doc-types")
def meta_doc_types(lang: str = Query(DEFAULT_LANGUAGE)) -> list[dict]:
    code = _lang(lang)
    return [{"doc_type": d, "label": t(f"doc.{d}", code)} for d in SUPPORTED_DOC_TYPES]


@router.get("/meta/fields")
def meta_fields(lang: str = Query(DEFAULT_LANGUAGE)) -> list[dict]:
    """Field catalogue with translated labels and option labels."""
    code = _lang(lang)
    out = []
    for spec in FIELD_SPECS:
        row = dict(spec)
        row["label"] = t(f"field.{spec['name']}", code)
        if spec.get("options"):
            row["option_labels"] = {opt: t(f"value.{opt}", code) for opt in spec["options"]}
        out.append(row)
    return out


# --------------------------------------------------------------------------
# profile
# --------------------------------------------------------------------------

def _serialise_profile(profile: Profile, lang: str) -> dict:
    filled = sum(1 for name in TRACKED_FIELDS if getattr(profile, name, None) is not None)
    facts = build_facts(profile)
    return {
        "id": profile.id,
        "language": profile.language,
        "fields": {
            name: (
                getattr(profile, name).isoformat()
                if isinstance(getattr(profile, name, None), date)
                else getattr(profile, name, None)
            )
            for name in TRACKED_FIELDS
        },
        "derived": {"age": facts.get("age"), "is_bpl": facts.get("is_bpl")},
        "aadhaar_last4": profile.aadhaar_last4,
        "account_last4": profile.account_last4,
        "field_sources": profile.field_sources or {},
        "filled_count": filled,
        "total_count": len(TRACKED_FIELDS),
        "completeness": round(100.0 * filled / len(TRACKED_FIELDS), 1),
    }


@router.post("/profiles")
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db)) -> dict:
    profile = Profile(language=_lang(payload.language), field_sources={})
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _serialise_profile(profile, profile.language)


@router.get("/profiles/{profile_id}")
def read_profile(
    profile_id: int, lang: str = Query(DEFAULT_LANGUAGE), db: Session = Depends(get_db)
) -> dict:
    return _serialise_profile(_get_profile(db, profile_id), _lang(lang))


@router.patch("/profiles/{profile_id}")
def update_profile(
    profile_id: int,
    payload: ProfileUpdate,
    lang: str = Query(DEFAULT_LANGUAGE),
    db: Session = Depends(get_db),
) -> dict:
    profile = _get_profile(db, profile_id)
    sources = dict(profile.field_sources or {})

    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, name, value)
        if name != "language":
            sources[name] = {
                "value": value.isoformat() if isinstance(value, date) else value,
                "method": "manual",
                "confidence": MANUAL_CONFIDENCE,
                "doc_type": None,
                "source_document_id": None,
                "at": datetime.now(timezone.utc).isoformat(),
            }

    profile.field_sources = sources
    db.commit()
    db.refresh(profile)
    return _serialise_profile(profile, _lang(lang))


@router.get("/profiles/{profile_id}/questions")
def profile_questions(
    profile_id: int, lang: str = Query(DEFAULT_LANGUAGE), db: Session = Depends(get_db)
) -> list[dict]:
    """Self-declared answers that would settle the most undecided schemes.

    These are the questions no document can answer, ranked by payoff, so the UI
    can ask two useful questions instead of twenty pointless ones.
    """
    code = _lang(lang)
    profile = _get_profile(db, profile_id)
    verdicts = evaluate_all(all_schemes(), build_facts(profile))

    tally: dict[str, set[str]] = {}
    for verdict in verdicts:
        if verdict.status != NEED_MORE_INFO:
            continue
        for field_name in verdict.questions_to_ask:
            tally.setdefault(field_name, set()).add(verdict.scheme_id)

    rows = []
    for field_name, scheme_ids in tally.items():
        spec = FIELD_SPEC_BY_NAME.get(field_name, {"name": field_name, "type": "text"})
        row = dict(spec)
        row["label"] = t(f"field.{field_name}", code)
        row["unlocks"] = len(scheme_ids)
        row["scheme_ids"] = sorted(scheme_ids)
        if spec.get("options"):
            row["option_labels"] = {o: t(f"value.{o}", code) for o in spec["options"]}
        rows.append(row)

    return sorted(rows, key=lambda r: r["unlocks"], reverse=True)


# --------------------------------------------------------------------------
# documents
# --------------------------------------------------------------------------

def _merge_into_profile(profile: Profile, document: Document, extraction) -> list[dict]:
    """Fold extracted fields into the profile, best-confidence-wins.

    Returns the list of changes so the upload screen can show what moved.
    """
    sources = dict(profile.field_sources or {})
    changes: list[dict] = []

    for field in extraction.fields:
        if field.value is None or not hasattr(profile, field.name):
            continue

        previous = sources.get(field.name)
        previous_confidence = float(previous.get("confidence", 0.0)) if previous else -1.0
        current = getattr(profile, field.name, None)

        # A person who typed a value is never overruled by a camera.
        if previous and previous.get("method") == "manual":
            continue
        if current is not None and field.confidence <= previous_confidence:
            continue

        setattr(profile, field.name, field.value)
        sources[field.name] = {
            "value": field.value.isoformat() if isinstance(field.value, date) else field.value,
            "method": "ocr",
            "confidence": round(field.confidence, 3),
            "doc_type": extraction.doc_type,
            "source_document_id": document.id,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        changes.append(
            {
                "field": field.name,
                "value": sources[field.name]["value"],
                "confidence": round(field.confidence, 3),
                "replaced": current is not None,
            }
        )

    profile.field_sources = sources
    return changes


def _serialise_document(document: Document, lang: str) -> dict:
    state = vault.document_state(document)
    return {
        "id": document.id,
        "doc_type": document.doc_type,
        "label": t(f"doc.{document.doc_type}", lang),
        "doc_type_confidence": document.doc_type_confidence,
        "original_filename": document.original_filename,
        "mime_type": document.mime_type,
        "size_bytes": document.size_bytes,
        "ocr_engine": document.ocr_engine,
        "ocr_confidence": document.ocr_confidence,
        "extracted_fields": document.extracted_fields,
        "warnings": document.warnings,
        "number_masked": document.number_masked,
        "issue_date": document.issue_date.isoformat() if document.issue_date else None,
        "expiry_date": document.expiry_date.isoformat() if document.expiry_date else None,
        "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
        "state": state["state"],
        "days_left": state["days_left"],
    }


@router.post("/profiles/{profile_id}/documents")
async def upload_document(
    profile_id: int,
    file: UploadFile = File(...),
    doc_type: str | None = Form(default=None),
    lang: str = Query(DEFAULT_LANGUAGE),
    db: Session = Depends(get_db),
) -> dict:
    code = _lang(lang)
    profile = _get_profile(db, profile_id)

    mime = file.content_type or "application/octet-stream"
    if not mime.startswith(ALLOWED_MIME_PREFIXES):
        raise HTTPException(status_code=415, detail=f"unsupported file type: {mime}")

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large")
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")

    # store the original
    folder = STORAGE_DIR / "documents" / str(profile_id)
    folder.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix[:8] or (
        ".pdf" if mime == "application/pdf" else ".jpg"
    )
    stored = folder / f"{uuid.uuid4().hex}{suffix}"
    stored.write_bytes(raw)

    ocr = run_ocr(raw, mime)
    extraction = extract(ocr.text, doc_type_hint=doc_type)

    document = Document(
        profile_id=profile_id,
        doc_type=extraction.doc_type,
        doc_type_confidence=extraction.doc_type_confidence,
        label=t(f"doc.{extraction.doc_type}", code),
        original_filename=file.filename or stored.name,
        stored_path=str(stored),
        mime_type=mime,
        size_bytes=len(raw),
        ocr_engine=ocr.engine,
        # Redaction happens here, before anything is written. Extraction above
        # saw the real number long enough to checksum it and keep the last four.
        ocr_text=redact(ocr.text)[:20000],
        ocr_confidence=ocr.confidence,
        extracted_fields=extraction.as_dict(),
        warnings=list(ocr.warnings) + list(extraction.warnings),
        issue_date=extraction.issue_date,
        expiry_date=extraction.expiry_date,
        number_masked=extraction.number_masked,
    )
    db.add(document)
    db.flush()

    changes = _merge_into_profile(profile, document, extraction)
    db.commit()
    db.refresh(document)
    db.refresh(profile)

    vault.sync_reminders(db, profile_id)

    verdicts = evaluate_all(all_schemes(), build_facts(profile))
    unlocks = unlock_summary(verdicts)

    return {
        "document": _serialise_document(document, code),
        "changes": [{**c, "label": t(f"field.{c['field']}", code)} for c in changes],
        "ocr": {
            "engine": ocr.engine,
            "confidence": ocr.confidence,
            "line_count": len(ocr.lines),
            "warnings": ocr.warnings,
        },
        "profile": _serialise_profile(profile, code),
        "eligible_count": sum(1 for v in verdicts if v.status == ELIGIBLE),
        "need_info_count": sum(1 for v in verdicts if v.status == NEED_MORE_INFO),
        "next_documents": [
            {**row, "label": t(f"doc.{row['doc_type']}", code)} for row in unlocks[:3]
        ],
    }


@router.get("/profiles/{profile_id}/documents")
def list_documents(
    profile_id: int, lang: str = Query(DEFAULT_LANGUAGE), db: Session = Depends(get_db)
) -> list[dict]:
    code = _lang(lang)
    _get_profile(db, profile_id)
    return [_serialise_document(d, code) for d in vault.list_documents(db, profile_id)]


@router.get("/documents/{document_id}/file")
def document_file(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document or not Path(document.stored_path).exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(
        document.stored_path,
        media_type=document.mime_type,
        filename=document.original_filename,
    )


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)) -> dict:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="document not found")
    path = Path(document.stored_path)
    db.delete(document)
    db.commit()
    if path.exists():
        path.unlink(missing_ok=True)
    return {"deleted": document_id}


# --------------------------------------------------------------------------
# schemes
# --------------------------------------------------------------------------

@router.get("/profiles/{profile_id}/schemes")
def profile_schemes(
    profile_id: int,
    lang: str = Query(DEFAULT_LANGUAGE),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    code = _lang(lang)
    profile = _get_profile(db, profile_id)
    owned = vault.owned_doc_types(db, profile_id)

    schemes = {s["id"]: s for s in all_schemes()}
    verdicts = evaluate_all(all_schemes(), build_facts(profile))

    results = [explain(schemes[v.scheme_id], v, code, owned_doc_types=owned) for v in verdicts]
    summary = {
        "eligible": sum(1 for r in results if r["status"] == ELIGIBLE),
        "need_more_info": sum(1 for r in results if r["status"] == NEED_MORE_INFO),
        "not_eligible": sum(1 for r in results if r["status"] == "not_eligible"),
    }

    # Money in hand and insurance cover are different things and must not be
    # added together. Summing a Rs 5 lakh hospital cover into a yearly income
    # figure would tell a widow on a Rs 300 pension that she is owed lakhs.
    cash_value = sum(
        (r["benefit_amount"] or 0) * (12 if r["benefit_period"] == "month" else 1)
        for r in results
        if r["status"] == ELIGIBLE
        and r["benefit_period"] in {"month", "year"}
        and r["category"] not in COVER_CATEGORIES
    )
    cover_value = max(
        [
            r["benefit_amount"] or 0
            for r in results
            if r["status"] == ELIGIBLE and r["category"] in COVER_CATEGORIES
        ],
        default=0,
    )
    summary["annual_value"] = cash_value
    summary["annual_value_text"] = money(cash_value, code)
    summary["cover_value"] = cover_value
    summary["cover_value_text"] = money(cover_value, code)

    if status:
        results = [r for r in results if r["status"] == status]

    return {
        "schemes": results,
        "summary": summary,
        "next_documents": [
            {**row, "label": t(f"doc.{row['doc_type']}", code)}
            for row in unlock_summary(verdicts)[:4]
        ],
        "disclaimer": t("app.disclaimer", code),
    }


@router.get("/profiles/{profile_id}/schemes/{scheme_id}")
def profile_scheme_detail(
    profile_id: int,
    scheme_id: str,
    lang: str = Query(DEFAULT_LANGUAGE),
    db: Session = Depends(get_db),
) -> dict:
    code = _lang(lang)
    profile = _get_profile(db, profile_id)
    scheme = get_scheme(scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail="scheme not found")

    verdict = evaluate_scheme(scheme, build_facts(profile))
    payload = explain(
        scheme, verdict, code, owned_doc_types=vault.owned_doc_types(db, profile_id)
    )

    existing = tracker.get_application(db, profile_id, scheme_id)
    payload["application"] = _serialise_application(existing, code) if existing else None

    filled = autofill(scheme.get("form_id", ""), profile)
    payload["form_preview"] = {
        "form_id": scheme.get("form_id"),
        "title": filled.title,
        "completion_percent": filled.completion_percent,
        "missing_required": [
            {"field": name, "label": t(f"field.{name}", code)}
            for name in filled.missing_required
        ],
        "field_count": len(form_fields(scheme.get("form_id", ""))),
    }
    return payload


# --------------------------------------------------------------------------
# applications
# --------------------------------------------------------------------------

def _serialise_application(app: Application, lang: str) -> dict:
    return {
        "id": app.id,
        "scheme_id": app.scheme_id,
        "scheme_name": app.scheme_name,
        "status": app.status,
        "status_label": t(f"app_status.{app.status}", lang),
        "reference_no": app.reference_no,
        "completion_percent": app.completion_percent,
        "missing_fields": [
            {"field": name, "label": t(f"field.{name}", lang)}
            for name in (app.missing_fields or [])
        ],
        "has_form": bool(app.form_pdf_path),
        "days_waiting": tracker.days_waiting(app),
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "updated_at": app.updated_at.isoformat() if app.updated_at else None,
        "events": [
            {
                "status": e.status,
                "status_label": t(f"app_status.{e.status}", lang),
                "note": e.note,
                "actor": e.actor,
                "at": e.at.isoformat() if e.at else None,
            }
            for e in app.events
        ],
    }


@router.post("/profiles/{profile_id}/applications")
def create_application(
    profile_id: int,
    payload: ApplicationCreate,
    lang: str = Query(DEFAULT_LANGUAGE),
    db: Session = Depends(get_db),
) -> dict:
    code = _lang(lang)
    profile = _get_profile(db, profile_id)
    scheme = get_scheme(payload.scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail="scheme not found")

    names = scheme.get("name") or {}
    scheme_name = names.get(code) or names.get("en", payload.scheme_id)
    app = tracker.start_application(db, profile, scheme, scheme_name, strings_for(code))
    return _serialise_application(app, code)


@router.get("/profiles/{profile_id}/applications")
def list_applications(
    profile_id: int, lang: str = Query(DEFAULT_LANGUAGE), db: Session = Depends(get_db)
) -> list[dict]:
    code = _lang(lang)
    _get_profile(db, profile_id)
    return [_serialise_application(a, code) for a in tracker.list_applications(db, profile_id)]


@router.post("/applications/{application_id}/status")
def set_application_status(
    application_id: int,
    payload: StatusUpdate,
    lang: str = Query(DEFAULT_LANGUAGE),
    db: Session = Depends(get_db),
) -> dict:
    code = _lang(lang)
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="application not found")
    try:
        app = tracker.advance(db, app, payload.status, payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    vault.sync_reminders(db, app.profile_id)
    return _serialise_application(app, code)


@router.get("/applications/{application_id}/form")
def application_form(application_id: int, db: Session = Depends(get_db)):
    app = db.get(Application, application_id)
    if not app or not app.form_pdf_path or not Path(app.form_pdf_path).exists():
        raise HTTPException(status_code=404, detail="form not generated")
    return FileResponse(
        app.form_pdf_path,
        media_type="application/pdf",
        filename=f"{app.scheme_id}_form.pdf",
    )


# --------------------------------------------------------------------------
# vault
# --------------------------------------------------------------------------

@router.get("/profiles/{profile_id}/vault")
def read_vault(
    profile_id: int, lang: str = Query(DEFAULT_LANGUAGE), db: Session = Depends(get_db)
) -> dict:
    code = _lang(lang)
    _get_profile(db, profile_id)
    vault.sync_reminders(db, profile_id)

    documents = [_serialise_document(d, code) for d in vault.list_documents(db, profile_id)]
    reminders = []
    for reminder in vault.list_reminders(db, profile_id):
        args = dict(reminder.title_args or {})
        if "doc" in args:
            args["doc"] = t(f"doc.{args['doc']}", code)
        # Reminder args are stored ISO for sorting, but read day-first.
        if "date" in args:
            args["date"] = _day_first(args["date"])
        reminders.append(
            {
                "id": reminder.id,
                "kind": reminder.kind,
                "text": t(reminder.title_key, code, **args),
                "due_date": reminder.due_date.isoformat() if reminder.due_date else None,
                "document_id": reminder.document_id,
                "application_id": reminder.application_id,
            }
        )

    return {
        "documents": documents,
        "reminders": reminders,
        "counts": {
            "total": len(documents),
            "expiring_soon": sum(1 for d in documents if d["state"] == "expiring_soon"),
            "expired": sum(1 for d in documents if d["state"] == "expired"),
        },
    }


@router.post("/reminders/{reminder_id}/done")
def complete_reminder(reminder_id: int, db: Session = Depends(get_db)) -> dict:
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="reminder not found")
    reminder.done = True
    db.commit()
    return {"id": reminder_id, "done": True}
