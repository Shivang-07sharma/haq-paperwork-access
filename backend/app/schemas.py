"""Request models and the field catalogue the profile editor is built from.

FIELD_SPECS is the single source of truth for how a profile field is edited.
The frontend renders from it rather than hard-coding inputs, so adding a field
that a new scheme needs does not require touching the UI.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    language: str = "en"


class ProfileUpdate(BaseModel):
    language: str | None = None
    full_name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    guardian_name: str | None = None
    mobile: str | None = None
    address_line: str | None = None
    village_town: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = None
    area_type: str | None = None
    annual_income: float | None = None
    social_category: str | None = None
    ration_card_type: str | None = None
    occupation: str | None = None
    land_holding_acres: float | None = None
    family_size: int | None = None
    marital_status: str | None = None
    education_level: str | None = None
    disability_percent: float | None = None
    is_income_tax_payer: bool | None = None
    is_govt_employee: bool | None = None
    house_type: str | None = None
    has_lpg_connection: bool | None = None
    is_pregnant_or_lactating: bool | None = None
    has_bank_account: bool | None = None
    bank_name: str | None = None
    ifsc: str | None = None


class ApplicationCreate(BaseModel):
    scheme_id: str


class StatusUpdate(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=400)


# name, input type, option values, which screen group it belongs to
FIELD_SPECS: list[dict] = [
    {"name": "full_name", "type": "text", "group": "identity"},
    {"name": "date_of_birth", "type": "date", "group": "identity"},
    {"name": "gender", "type": "choice", "options": ["male", "female", "other"], "group": "identity"},
    {"name": "mobile", "type": "tel", "group": "identity"},
    {"name": "guardian_name", "type": "text", "group": "identity"},

    {"name": "address_line", "type": "text", "group": "address"},
    {"name": "village_town", "type": "text", "group": "address"},
    {"name": "district", "type": "text", "group": "address"},
    {"name": "state", "type": "text", "group": "address"},
    {"name": "pincode", "type": "text", "group": "address"},
    {"name": "area_type", "type": "choice", "options": ["rural", "urban"], "group": "address"},

    {"name": "annual_income", "type": "number", "group": "household", "unit": "INR"},
    {"name": "family_size", "type": "number", "group": "household"},
    {"name": "social_category", "type": "choice",
     "options": ["GEN", "OBC", "SC", "ST", "EWS"], "group": "household"},
    {"name": "ration_card_type", "type": "choice",
     "options": ["AAY", "PHH", "BPL", "APL"], "group": "household"},
    {"name": "house_type", "type": "choice",
     "options": ["kutcha", "pucca", "none"], "group": "household"},
    {"name": "marital_status", "type": "choice",
     "options": ["unmarried", "married", "widowed"], "group": "household"},

    {"name": "occupation", "type": "text", "group": "work"},
    {"name": "land_holding_acres", "type": "number", "group": "work", "unit": "acres"},
    {"name": "education_level", "type": "choice",
     "options": ["none", "class_11_12", "graduate", "post_graduate"], "group": "work"},
    {"name": "disability_percent", "type": "number", "group": "work", "unit": "percent"},

    {"name": "has_bank_account", "type": "boolean", "group": "bank"},
    {"name": "bank_name", "type": "text", "group": "bank"},
    {"name": "ifsc", "type": "text", "group": "bank"},

    {"name": "is_income_tax_payer", "type": "boolean", "group": "declarations"},
    {"name": "is_govt_employee", "type": "boolean", "group": "declarations"},
    {"name": "has_lpg_connection", "type": "boolean", "group": "declarations"},
    {"name": "is_pregnant_or_lactating", "type": "boolean", "group": "declarations"},
]

FIELD_SPEC_BY_NAME = {spec["name"]: spec for spec in FIELD_SPECS}

# Fields shown as the profile completeness denominator. Read-only derived values
# such as age are excluded because a person cannot fill them in.
TRACKED_FIELDS = [spec["name"] for spec in FIELD_SPECS]
