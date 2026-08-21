"""ORM models.

The profile is deliberately wide and flat: every column here is something at
least one government scheme tests for. field_sources records which document
each value came from and how confident we were, so the UI can always answer
the question "where did you get that?".
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    language: Mapped[str] = mapped_column(String(8), default="en")

    # identity
    full_name: Mapped[str | None] = mapped_column(String(160))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(16))          # male | female | other
    guardian_name: Mapped[str | None] = mapped_column(String(160))
    mobile: Mapped[str | None] = mapped_column(String(20))
    aadhaar_last4: Mapped[str | None] = mapped_column(String(4))    # never the full number
    pan: Mapped[str | None] = mapped_column(String(12))
    voter_id: Mapped[str | None] = mapped_column(String(16))

    # address
    address_line: Mapped[str | None] = mapped_column(String(300))
    village_town: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    pincode: Mapped[str | None] = mapped_column(String(10))
    area_type: Mapped[str | None] = mapped_column(String(16))       # rural | urban

    # socio-economic -- the fields eligibility actually turns on
    annual_income: Mapped[float | None] = mapped_column(Float)
    social_category: Mapped[str | None] = mapped_column(String(16))  # GEN|OBC|SC|ST
    ration_card_type: Mapped[str | None] = mapped_column(String(8))  # AAY|PHH|BPL|APL
    occupation: Mapped[str | None] = mapped_column(String(80))
    land_holding_acres: Mapped[float | None] = mapped_column(Float)
    family_size: Mapped[int | None] = mapped_column(Integer)
    marital_status: Mapped[str | None] = mapped_column(String(20))
    education_level: Mapped[str | None] = mapped_column(String(40))
    disability_percent: Mapped[float | None] = mapped_column(Float)
    is_income_tax_payer: Mapped[bool | None] = mapped_column(Boolean)
    is_govt_employee: Mapped[bool | None] = mapped_column(Boolean)
    house_type: Mapped[str | None] = mapped_column(String(24))       # kutcha|pucca|none
    has_lpg_connection: Mapped[bool | None] = mapped_column(Boolean)
    is_pregnant_or_lactating: Mapped[bool | None] = mapped_column(Boolean)

    # banking
    has_bank_account: Mapped[bool | None] = mapped_column(Boolean)
    bank_name: Mapped[str | None] = mapped_column(String(120))
    ifsc: Mapped[str | None] = mapped_column(String(16))
    account_last4: Mapped[str | None] = mapped_column(String(4))

    # provenance: {field: {value, source_document_id, doc_type, confidence, method}}
    field_sources: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    applications: Mapped[list["Application"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))

    doc_type: Mapped[str] = mapped_column(String(48), default="unknown")
    doc_type_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    label: Mapped[str | None] = mapped_column(String(160))

    original_filename: Mapped[str] = mapped_column(String(260))
    stored_path: Mapped[str] = mapped_column(String(400))
    mime_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    ocr_engine: Mapped[str | None] = mapped_column(String(40))
    ocr_text: Mapped[str | None] = mapped_column(Text)            # already redacted
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    extracted_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    warnings: Mapped[list] = mapped_column(JSON, default=list)

    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    number_masked: Mapped[str | None] = mapped_column(String(40))

    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    profile: Mapped[Profile] = relationship(back_populates="documents")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))

    scheme_id: Mapped[str] = mapped_column(String(64))
    scheme_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    reference_no: Mapped[str | None] = mapped_column(String(40))
    form_pdf_path: Mapped[str | None] = mapped_column(String(400))
    filled_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)
    completion_percent: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    profile: Mapped[Profile] = relationship(back_populates="applications")
    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationEvent.at",
    )


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(String(400))
    actor: Mapped[str] = mapped_column(String(40), default="system")
    at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    application: Mapped[Application] = relationship(back_populates="events")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE")
    )

    kind: Mapped[str] = mapped_column(String(32))       # expiry | follow_up | renewal
    title_key: Mapped[str] = mapped_column(String(64))  # i18n key: reminders speak the user's language
    title_args: Mapped[dict] = mapped_column(JSON, default=dict)
    due_date: Mapped[date] = mapped_column(Date)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    profile: Mapped[Profile] = relationship(back_populates="reminders")
