"""Regexes, validators and normalisers for Indian identity and welfare documents.

Two things matter more than raw recall here:

1. **Validation.** OCR misreads digits constantly. An Aadhaar number carries a
   Verhoeff check digit and an IFSC has a fixed shape, so we can reject a bad
   read instead of writing a wrong number into somebody's application form.
2. **Redaction.** A full Aadhaar number must never be persisted. We keep the
   last four digits, and the OCR text is scrubbed before it touches the DB.
"""
from __future__ import annotations

import re
from datetime import date, datetime

# --------------------------------------------------------------------------
# identifier patterns
# --------------------------------------------------------------------------

AADHAAR_RE = re.compile(r"(?<!\d)(\d{4})\s?-?\s?(\d{4})\s?-?\s?(\d{4})(?!\d)")
PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
IFSC_RE = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
EPIC_RE = re.compile(r"\b([A-Z]{3}[0-9]{7})\b")
MOBILE_RE = re.compile(r"(?<!\d)([6-9]\d{9})(?!\d)")
PINCODE_RE = re.compile(r"(?<!\d)([1-9]\d{5})(?!\d)")
ACCOUNT_RE = re.compile(r"(?<!\d)(\d{9,18})(?!\d)")

# Aadhaar cards print the DOB with an explicit label; birth-year-only cards exist too.
DOB_LABELLED_RE = re.compile(
    r"(?:DOB|D\.O\.B|Date\s*of\s*Birth|Birth|जन्म\s*तिथि|जन्म)\s*[:\-]?\s*"
    r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
    re.IGNORECASE,
)
YOB_RE = re.compile(
    r"(?:Year\s*of\s*Birth|YOB|जन्म\s*वर्ष)\s*[:\-]?\s*((?:19|20)\d{2})", re.IGNORECASE
)
DATE_ANY_RE = re.compile(r"(?<!\d)(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})(?!\d)")

GENDER_RE = re.compile(
    r"\b(MALE|FEMALE|TRANSGENDER|पुरुष|महिला|स्त्री|ஆண்|பெண்|পুরুষ|মহিলা)\b",
    re.IGNORECASE,
)

# Money can arrive as digits with Indian grouping or spelled out in lakhs.
MONEY_RE = re.compile(r"(?:Rs\.?|INR|₹)\s*([0-9][0-9,]{2,})(?:\.\d{1,2})?", re.IGNORECASE)
LAKH_RE = re.compile(
    r"([0-9]+(?:\.[0-9]+)?)\s*(lakh|lac|lakhs|crore|लाख|करोड़)", re.IGNORECASE
)
INCOME_CONTEXT_RE = re.compile(
    r"(?:annual\s*income|yearly\s*income|income|वार्षिक\s*आय|आय|வருமானம்|আয়)\s*"
    r"[:\-]?\s*(?:Rs\.?|INR|₹)?\s*([0-9][0-9,]{2,})",
    re.IGNORECASE,
)

AREA_RE = re.compile(
    r"([0-9]+(?:\.[0-9]+)?)\s*(hectares|hectare|ha\b|acres|acre|bigha|एकड़|हेक्टेयर)",
    re.IGNORECASE,
)
DISABILITY_RE = re.compile(
    r"(?:disability|विकलांगता|दिव्यांगता)\s*[:\-]?\s*([0-9]{1,3})\s*%"
    r"|([0-9]{1,3})\s*%\s*(?:disability|permanent|विकलांगता|दिव्यांगता)",
    re.IGNORECASE,
)

CATEGORY_RE = re.compile(
    r"\b(SC|ST|OBC-NCL|OBC|GENERAL|GEN|EWS|अनुसूचित\s*जाति|अनुसूचित\s*जनजाति|अन्य\s*पिछड़ा)\b",
    re.IGNORECASE,
)
RATION_TYPE_RE = re.compile(
    r"\b(AAY|ANTYODAYA|PHH|BPL|APL|PRIORITY\s*HOUSEHOLD)\b", re.IGNORECASE
)

# --------------------------------------------------------------------------
# Aadhaar Verhoeff checksum
# --------------------------------------------------------------------------

_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def verhoeff_valid(number: str) -> bool:
    """True when the 12 digits satisfy the Verhoeff check digit that UIDAI uses."""
    digits = re.sub(r"\D", "", number)
    if len(digits) != 12 or digits[0] in "01":   # Aadhaar never starts with 0 or 1
        return False
    c = 0
    for i, digit in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][int(digit)]]
    return c == 0


def find_aadhaar(text: str) -> tuple[str | None, bool]:
    """Return (12 digits, checksum_ok). Prefers a candidate that validates."""
    fallback: str | None = None
    for match in AADHAAR_RE.finditer(text):
        digits = "".join(match.groups())
        if verhoeff_valid(digits):
            return digits, True
        fallback = fallback or digits
    return fallback, False


def mask_aadhaar(digits: str) -> str:
    return f"XXXX XXXX {digits[-4:]}"


def redact(text: str) -> str:
    """Scrub full identity numbers out of OCR text before it is stored."""
    if not text:
        return text

    out = AADHAAR_RE.sub(lambda m: f"XXXX XXXX {m.group(3)}", text)
    out = PAN_RE.sub(lambda m: m.group(1)[:3] + "XXXXX" + m.group(1)[-1], out)
    # Long bare digit runs are usually bank account numbers.
    out = re.sub(
        r"(?<!\d)(\d{6})(\d{4,12})(?!\d)",
        lambda m: "X" * len(m.group(1)) + m.group(2),
        out,
    )
    return out


# --------------------------------------------------------------------------
# normalisers
# --------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_indian_date(raw: str) -> date | None:
    """Indian documents are day-first. Accepts 01/02/2003, 01-02-03, 1.2.2003."""
    if not raw:
        return None
    raw = raw.strip()

    m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$", raw)
    if m:
        day, month, year = (int(g) for g in m.groups())
        if year < 100:                       # two-digit year: assume 1900s for adults
            year += 2000 if year < 25 else 1900
        if month > 12 and day <= 12:         # tolerate a month-first document
            day, month = month, day
        try:
            return date(year, month, day)
        except ValueError:
            return None

    m = re.match(r"^(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})$", raw)
    if m:
        day, month_name, year = m.group(1), m.group(2)[:3].lower(), m.group(3)
        if month_name in _MONTHS:
            try:
                return date(int(year), _MONTHS[month_name], int(day))
            except ValueError:
                return None

    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_money(raw: str) -> float | None:
    """Handle Indian digit grouping (1,20,000) and lakh/crore words."""
    if not raw:
        return None

    m = LAKH_RE.search(raw)
    if m:
        amount = float(m.group(1))
        unit = m.group(2).lower()
        multiplier = 10_000_000 if unit in {"crore", "करोड़"} else 100_000
        return amount * multiplier

    cleaned = re.sub(r"[^\d.]", "", raw)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def normalise_gender(raw: str | None) -> str | None:
    if not raw:
        return None
    token = raw.strip().lower()
    if token in {"male", "पुरुष", "ஆண்", "পুরুষ", "m"}:
        return "male"
    if token in {"female", "महिला", "स्त्री", "பெண்", "মহিলা", "f"}:
        return "female"
    if token in {"transgender", "other", "t"}:
        return "other"
    return None


def normalise_category(raw: str | None) -> str | None:
    if not raw:
        return None
    token = raw.strip().upper()
    if token.startswith("SC") or "अनुसूचित जाति" in raw:
        return "SC"
    if token.startswith("ST") or "अनुसूचित जनजाति" in raw:
        return "ST"
    if token.startswith("OBC") or "पिछड़ा" in raw:
        return "OBC"
    if token == "EWS":
        return "EWS"
    if token.startswith("GEN"):
        return "GEN"
    return None


def normalise_ration_type(raw: str | None) -> str | None:
    if not raw:
        return None
    token = raw.strip().upper()
    if "ANTYODAYA" in token or token == "AAY":
        return "AAY"
    if "PRIORITY" in token or token == "PHH":
        return "PHH"
    if token in {"BPL", "APL"}:
        return token
    return None


def acres_from(value: float, unit: str) -> float:
    """Land records mix units. Normalise everything to acres."""
    unit = unit.lower().strip()
    if unit.startswith("hectare") or unit in {"ha", "हेक्टेयर"}:
        return round(value * 2.47105, 3)
    if unit.startswith("bigha"):          # regional, about 0.62 acre in much of north India
        return round(value * 0.619, 3)
    return round(value, 3)


def clean_name(raw: str | None) -> str | None:
    """Strip OCR noise from a name line without mangling the name itself."""
    if not raw:
        return None
    name = re.sub(r"[^A-Za-zऀ-ॿ஀-௿ঀ-৿\s.]", " ", raw)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if len(name) < 3 or len(name) > 80:
        return None
    # Reject label lines that OCR sometimes hands back as the value.
    if re.fullmatch(r"(?i)(government of india|male|female|dob|address|name)", name):
        return None
    return name.title() if name.isascii() else name
