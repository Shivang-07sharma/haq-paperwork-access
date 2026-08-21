"""Turn OCR text into profile fields.

Detection is keyword scoring rather than a classifier: the vocabulary on an
Aadhaar card or a caste certificate is fixed and printed in a known place, and a
scored keyword match is inspectable when it goes wrong. Every extracted value
carries a confidence so the UI can show the person what to double-check instead
of silently trusting a bad read.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import patterns as P

# --------------------------------------------------------------------------
# document type detection
# --------------------------------------------------------------------------

# (keyword, weight). Devanagari spellings are included because most cards are
# printed bilingually and the English half is often the more damaged one.
DOC_SIGNATURES: dict[str, list[tuple[str, float]]] = {
    "aadhaar": [
        ("unique identification authority", 3.0), ("aadhaar", 3.0), ("आधार", 3.0),
        ("uidai", 2.5), ("government of india", 1.0), ("भारत सरकार", 1.0),
        ("vid", 1.0), ("मेरा आधार", 1.5),
    ],
    "pan": [
        ("income tax department", 3.0), ("permanent account number", 3.0),
        ("आयकर विभाग", 2.5), ("pan", 1.5),
    ],
    "ration_card": [
        ("ration card", 3.0), ("राशन कार्ड", 3.0), ("food security", 2.0),
        ("antyodaya", 2.5), ("priority household", 2.5), ("खाद्य सुरक्षा", 2.0),
        ("fair price shop", 1.5), ("nfsa", 2.0),
    ],
    "income_certificate": [
        ("income certificate", 3.5), ("आय प्रमाण पत्र", 3.5),
        ("annual income", 2.0), ("वार्षिक आय", 2.0), ("tehsildar", 1.5),
        ("revenue department", 1.0),
    ],
    "caste_certificate": [
        ("caste certificate", 3.5), ("जाति प्रमाण पत्र", 3.5),
        ("scheduled caste", 2.0), ("scheduled tribe", 2.0),
        ("other backward", 2.0), ("अनुसूचित जाति", 2.0),
    ],
    "bank_passbook": [
        ("passbook", 3.0), ("ifsc", 3.0), ("account number", 2.0),
        ("branch", 1.5), ("बैंक", 1.5), ("savings account", 2.0),
    ],
    "voter_id": [
        ("election commission", 3.0), ("elector", 2.5), ("epic", 2.0),
        ("निर्वाचन आयोग", 3.0), ("voter", 2.0),
    ],
    "land_record": [
        ("khasra", 3.0), ("khatauni", 3.0), ("jamabandi", 3.0),
        ("land holding", 2.5), ("खसरा", 3.0), ("भूमि", 2.0),
        ("record of rights", 2.5), ("pahani", 2.5),
    ],
    "disability_certificate": [
        ("disability certificate", 3.5), ("udid", 3.0), ("दिव्यांग", 3.0),
        ("percentage of disability", 2.5), ("विकलांगता", 2.5),
    ],
    "birth_certificate": [
        ("birth certificate", 3.5), ("जन्म प्रमाण पत्र", 3.5),
        ("registrar of births", 2.5),
    ],
    "domicile_certificate": [
        ("domicile", 3.0), ("residence certificate", 3.0), ("निवास प्रमाण पत्र", 3.0),
    ],
    "job_card": [
        ("mgnrega", 3.5), ("nrega", 3.0), ("job card", 3.0),
        ("रोजगार गारंटी", 3.0), ("employment guarantee", 2.5),
    ],
}

# How long a certificate stays acceptable to a scheme office. Income and
# domicile certificates go stale; identity documents do not.
VALIDITY_DAYS: dict[str, int | None] = {
    "income_certificate": 365,
    "domicile_certificate": 365 * 3,
    "caste_certificate": None,
    "aadhaar": None,
    "pan": None,
    "ration_card": 365 * 5,
    "bank_passbook": None,
    "voter_id": None,
    "land_record": 365,
    "disability_certificate": 365 * 5,
    "birth_certificate": None,
    "job_card": None,
}

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Jammu and Kashmir",
    "Ladakh", "Puducherry", "Chandigarh", "Andaman and Nicobar Islands",
    "Dadra and Nagar Haveli", "Daman and Diu", "Lakshadweep",
]


@dataclass
class ExtractedField:
    name: str
    value: object
    confidence: float
    raw: str | None = None
    note: str | None = None


@dataclass
class ExtractionResult:
    doc_type: str = "unknown"
    doc_type_confidence: float = 0.0
    fields: list[ExtractedField] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    number_masked: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None

    def as_dict(self) -> dict:
        return {
            f.name: {
                "value": f.value.isoformat() if isinstance(f.value, date) else f.value,
                "confidence": round(f.confidence, 3),
                "raw": f.raw,
                "note": f.note,
            }
            for f in self.fields
        }


def detect_doc_type(text: str) -> tuple[str, float]:
    """Score the text against each signature. Ties go to the higher raw score."""
    lowered = text.lower()
    scores: dict[str, float] = {}
    for doc_type, signatures in DOC_SIGNATURES.items():
        score = sum(weight for keyword, weight in signatures if keyword in lowered)
        if score:
            scores[doc_type] = score

    if not scores:
        return "unknown", 0.0

    best = max(scores, key=lambda k: scores[k])
    total = sum(scores.values())
    # Confidence blends dominance over rivals with absolute evidence strength, so
    # a single weak keyword match does not come back as certain.
    dominance = scores[best] / total
    strength = min(scores[best] / 5.0, 1.0)
    return best, round(dominance * 0.5 + strength * 0.5, 3)


# --------------------------------------------------------------------------
# shared field pickers
# --------------------------------------------------------------------------

_NOISE_LINE = re.compile(
    r"(?i)^(government of india|भारत सरकार|unique identification|uidai|"
    r"income tax department|आयकर विभाग|male|female|dob|address|पता)\b"
)


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _name_above_dob(text: str) -> str | None:
    """On an Aadhaar card the holder name sits directly above the DOB line."""
    lines = _lines(text)
    for idx, line in enumerate(lines):
        if P.DOB_LABELLED_RE.search(line) or P.YOB_RE.search(line):
            for back in range(idx - 1, max(idx - 4, -1), -1):
                candidate = lines[back]
                if _NOISE_LINE.match(candidate):
                    continue
                cleaned = P.clean_name(candidate)
                if cleaned:
                    return cleaned
    return None


def _name_after_label(text: str) -> str | None:
    m = re.search(r"(?:^|\n)\s*(?:Name|NAME|नाम|Applicant)\s*[:\-]\s*(.+)", text)
    return P.clean_name(m.group(1)) if m else None


def _find_state(text: str) -> str | None:
    lowered = text.lower()
    for state in INDIAN_STATES:
        if state.lower() in lowered:
            return state
    return None


def _find_dob(text: str) -> tuple[date | None, float, str | None]:
    m = P.DOB_LABELLED_RE.search(text)
    if m:
        parsed = P.parse_indian_date(m.group(1))
        if parsed:
            return parsed, 0.92, m.group(1)

    m = P.YOB_RE.search(text)
    if m:                                  # year-only Aadhaar: assume mid-year
        year = int(m.group(1))
        return date(year, 7, 1), 0.6, m.group(1)

    m = P.DATE_ANY_RE.search(text)
    if m:
        parsed = P.parse_indian_date(m.group(1))
        if parsed and parsed.year < date.today().year:
            return parsed, 0.45, m.group(1)
    return None, 0.0, None


def _common_fields(text: str) -> list[ExtractedField]:
    """Fields worth lifting off any document that happens to carry them."""
    out: list[ExtractedField] = []

    mobile = P.MOBILE_RE.search(text)
    if mobile:
        out.append(ExtractedField("mobile", mobile.group(1), 0.8, mobile.group(1)))

    pincode = P.PINCODE_RE.search(text)
    if pincode:
        out.append(ExtractedField("pincode", pincode.group(1), 0.75, pincode.group(1)))

    state = _find_state(text)
    if state:
        out.append(ExtractedField("state", state, 0.8, state))

    return out


# --------------------------------------------------------------------------
# per document extractors
# --------------------------------------------------------------------------

def _extract_aadhaar(text: str, result: ExtractionResult) -> None:
    digits, checksum_ok = P.find_aadhaar(text)
    if digits:
        result.number_masked = P.mask_aadhaar(digits)
        result.fields.append(
            ExtractedField(
                "aadhaar_last4",
                digits[-4:],
                0.95 if checksum_ok else 0.55,
                result.number_masked,
                None if checksum_ok else "checksum_failed",
            )
        )
        if not checksum_ok:
            result.warnings.append("aadhaar_checksum_failed")

    name = _name_above_dob(text) or _name_after_label(text)
    if name:
        result.fields.append(ExtractedField("full_name", name, 0.8, name))

    dob, conf, raw = _find_dob(text)
    if dob:
        result.fields.append(ExtractedField("date_of_birth", dob, conf, raw))

    gender_match = P.GENDER_RE.search(text)
    gender = P.normalise_gender(gender_match.group(1)) if gender_match else None
    if gender:
        result.fields.append(ExtractedField("gender", gender, 0.9, gender_match.group(1)))

    address = _address_block(text)
    if address:
        result.fields.append(ExtractedField("address_line", address, 0.6, address))


def _address_block(text: str) -> str | None:
    m = re.search(r"(?:Address|पता|S/O|D/O|W/O|C/O)\s*[:\-]?\s*(.{20,240})", text, re.DOTALL)
    if not m:
        return None
    block = re.sub(r"\s+", " ", m.group(1)).strip()
    block = P.AADHAAR_RE.sub("", block)
    # Cards print an issuing-authority footer under the address; cut it off so it
    # does not end up inside somebody's postal address on a form.
    block = re.split(
        r"(?i)(unique identification|uidai|government of india|भारत सरकार|"
        r"aam\s*aadmi|aamaadmi|aadhaar\s*[-–]|मेरा आधार|help@uidai|www\.uidai|1947\b)",
        block,
    )[0]
    return block.strip(" ,-") or None


def _extract_pan(text: str, result: ExtractionResult) -> None:
    m = P.PAN_RE.search(text)
    if m:
        result.number_masked = m.group(1)[:3] + "XXXXX" + m.group(1)[-1]
        result.fields.append(ExtractedField("pan", m.group(1), 0.9, result.number_masked))
        # A PAN in active use often means the household files income tax, but
        # holding a PAN is not proof of it -- flag for confirmation, do not set.
        result.fields.append(
            ExtractedField("is_income_tax_payer", None, 0.0, None, "pan_present_verify_filing")
        )

    name = _name_after_label(text) or _name_above_dob(text)
    if name:
        result.fields.append(ExtractedField("full_name", name, 0.7, name))

    dob, conf, raw = _find_dob(text)
    if dob:
        result.fields.append(ExtractedField("date_of_birth", dob, conf, raw))


def _extract_ration_card(text: str, result: ExtractionResult) -> None:
    m = P.RATION_TYPE_RE.search(text)
    card_type = P.normalise_ration_type(m.group(1)) if m else None
    if card_type:
        result.fields.append(ExtractedField("ration_card_type", card_type, 0.9, m.group(1)))

    members = re.search(
        r"(?:no\.?\s*of\s*members|family\s*members|total\s*members|सदस्य)\s*[:\-]?\s*(\d{1,2})",
        text, re.IGNORECASE,
    )
    if members:
        result.fields.append(
            ExtractedField("family_size", int(members.group(1)), 0.8, members.group(1))
        )

    name = _name_after_label(text)
    if name:
        result.fields.append(ExtractedField("full_name", name, 0.65, name))

    # Space only, not \s: \s matches a newline and swallowed the following line.
    district = re.search(r"(?:District|जिला)[ \t]*[:\-]?[ \t]*([A-Za-z][A-Za-z ]{2,29})", text)
    if district:
        result.fields.append(
            ExtractedField("district", district.group(1).strip().title(), 0.7, district.group(1))
        )


def _extract_income_certificate(text: str, result: ExtractionResult) -> None:
    amount = None
    raw = None
    m = P.INCOME_CONTEXT_RE.search(text)
    if m:
        amount, raw = P.parse_money(m.group(1)), m.group(1)
    if amount is None:
        m = P.LAKH_RE.search(text)
        if m:
            amount, raw = P.parse_money(m.group(0)), m.group(0)
    if amount is None:
        m = P.MONEY_RE.search(text)
        if m:
            amount, raw = P.parse_money(m.group(1)), m.group(1)

    if amount is not None:
        # An income certificate stating more than a crore is an OCR artefact.
        confidence = 0.85 if amount < 10_000_000 else 0.3
        result.fields.append(ExtractedField("annual_income", amount, confidence, raw))

    name = _name_after_label(text)
    if name:
        result.fields.append(ExtractedField("full_name", name, 0.7, name))

    issued = _issue_date(text)
    if issued:
        result.issue_date = issued


def _extract_caste_certificate(text: str, result: ExtractionResult) -> None:
    m = P.CATEGORY_RE.search(text)
    category = P.normalise_category(m.group(1)) if m else None
    if category:
        result.fields.append(ExtractedField("social_category", category, 0.9, m.group(1)))

    name = _name_after_label(text)
    if name:
        result.fields.append(ExtractedField("full_name", name, 0.7, name))

    issued = _issue_date(text)
    if issued:
        result.issue_date = issued


def _extract_bank_passbook(text: str, result: ExtractionResult) -> None:
    m = P.IFSC_RE.search(text)
    if m:
        result.fields.append(ExtractedField("ifsc", m.group(1), 0.92, m.group(1)))
        result.fields.append(ExtractedField("has_bank_account", True, 0.92, m.group(1)))

    # Bank names run either way round (State Bank of India, Bank of Baroda), so
    # take the whole line that mentions a bank rather than a fixed-shape match.
    for line in _lines(text):
        if re.search(r"\bbank\b", line, re.IGNORECASE) and len(line) <= 48:
            if re.search(r"(?i)(ifsc|account|branch|passbook|a/?c)", line):
                continue
            cleaned = re.sub(r"[^A-Za-z\s.]", " ", line)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if len(cleaned) >= 6:
                result.fields.append(
                    ExtractedField("bank_name", cleaned.title(), 0.75, line)
                )
                break

    account = re.search(
        r"(?:A/?c\.?\s*(?:No\.?)?|Account\s*(?:No\.?|Number)|खाता)\s*[:\-]?\s*(\d{9,18})",
        text, re.IGNORECASE,
    )
    if account:
        digits = account.group(1)
        result.number_masked = "X" * (len(digits) - 4) + digits[-4:]
        result.fields.append(
            ExtractedField("account_last4", digits[-4:], 0.85, result.number_masked)
        )

    name = _name_after_label(text)
    if name:
        result.fields.append(ExtractedField("full_name", name, 0.6, name))


def _extract_voter_id(text: str, result: ExtractionResult) -> None:
    m = P.EPIC_RE.search(text)
    if m:
        result.number_masked = m.group(1)
        result.fields.append(ExtractedField("voter_id", m.group(1), 0.88, m.group(1)))

    name = _name_after_label(text)
    if name:
        result.fields.append(ExtractedField("full_name", name, 0.7, name))

    gender_match = P.GENDER_RE.search(text)
    gender = P.normalise_gender(gender_match.group(1)) if gender_match else None
    if gender:
        result.fields.append(ExtractedField("gender", gender, 0.85, gender_match.group(1)))

    dob, conf, raw = _find_dob(text)
    if dob:
        result.fields.append(ExtractedField("date_of_birth", dob, conf, raw))


def _extract_land_record(text: str, result: ExtractionResult) -> None:
    m = P.AREA_RE.search(text)
    if m:
        acres = P.acres_from(float(m.group(1)), m.group(2))
        result.fields.append(ExtractedField("land_holding_acres", acres, 0.8, m.group(0)))
        # Holding land is what PM-KISAN turns on, so record the occupation too.
        result.fields.append(ExtractedField("occupation", "farmer", 0.6, m.group(0)))

    name = _name_after_label(text)
    if name:
        result.fields.append(ExtractedField("full_name", name, 0.6, name))


def _extract_disability_certificate(text: str, result: ExtractionResult) -> None:
    m = P.DISABILITY_RE.search(text)
    if m:
        percent = float(m.group(1) or m.group(2))
        if 0 < percent <= 100:
            result.fields.append(ExtractedField("disability_percent", percent, 0.88, m.group(0)))

    name = _name_after_label(text)
    if name:
        result.fields.append(ExtractedField("full_name", name, 0.7, name))


def _extract_job_card(text: str, result: ExtractionResult) -> None:
    result.fields.append(ExtractedField("area_type", "rural", 0.8, "MGNREGA job card"))
    name = _name_after_label(text)
    if name:
        result.fields.append(ExtractedField("full_name", name, 0.65, name))


def _extract_birth_certificate(text: str, result: ExtractionResult) -> None:
    dob, conf, raw = _find_dob(text)
    if dob:
        result.fields.append(ExtractedField("date_of_birth", dob, max(conf, 0.9), raw))
    name = _name_after_label(text)
    if name:
        result.fields.append(ExtractedField("full_name", name, 0.7, name))


def _extract_domicile(text: str, result: ExtractionResult) -> None:
    state = _find_state(text)
    if state:
        result.fields.append(ExtractedField("state", state, 0.9, state))
    name = _name_after_label(text)
    if name:
        result.fields.append(ExtractedField("full_name", name, 0.7, name))
    issued = _issue_date(text)
    if issued:
        result.issue_date = issued


def _issue_date(text: str) -> date | None:
    m = re.search(
        r"(?:Date\s*of\s*Issue|Issued\s*on|Issue\s*Date|दिनांक|जारी)\s*[:\-]?\s*"
        r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
        text, re.IGNORECASE,
    )
    if m:
        return P.parse_indian_date(m.group(1))
    return None


_EXTRACTORS = {
    "aadhaar": _extract_aadhaar,
    "pan": _extract_pan,
    "ration_card": _extract_ration_card,
    "income_certificate": _extract_income_certificate,
    "caste_certificate": _extract_caste_certificate,
    "bank_passbook": _extract_bank_passbook,
    "voter_id": _extract_voter_id,
    "land_record": _extract_land_record,
    "disability_certificate": _extract_disability_certificate,
    "birth_certificate": _extract_birth_certificate,
    "domicile_certificate": _extract_domicile,
    "job_card": _extract_job_card,
}

SUPPORTED_DOC_TYPES = sorted(_EXTRACTORS.keys())


def extract(text: str, doc_type_hint: str | None = None) -> ExtractionResult:
    """Detect the document, pull its fields, and work out when it goes stale."""
    result = ExtractionResult()
    if not text or not text.strip():
        result.warnings.append("no_text_to_extract")
        return result

    if doc_type_hint and doc_type_hint in _EXTRACTORS:
        result.doc_type, result.doc_type_confidence = doc_type_hint, 1.0
    else:
        result.doc_type, result.doc_type_confidence = detect_doc_type(text)

    extractor = _EXTRACTORS.get(result.doc_type)
    if extractor:
        extractor(text, result)
    else:
        result.warnings.append("unrecognised_document_type")

    # Common fields never override a value the specific extractor already found.
    known = {f.name for f in result.fields}
    result.fields.extend(f for f in _common_fields(text) if f.name not in known)

    # Drop placeholder fields that exist only to carry a note.
    result.fields = [f for f in result.fields if f.value is not None or f.note]

    validity = VALIDITY_DAYS.get(result.doc_type)
    if validity and result.issue_date:
        result.expiry_date = result.issue_date + timedelta(days=validity)

    if not any(f.value is not None for f in result.fields):
        result.warnings.append("no_fields_extracted")

    return result
