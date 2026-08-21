"""Form definitions, autofill, and printable PDF output.

The point of this module is the last mile. Knowing somebody qualifies for a
pension is useless if they still have to sit in front of a blank government form
they cannot read. So we keep a field map per form, fill everything the profile
already knows, and print a PDF that is either ready to sign or clearly marked
with the few blanks left to complete by hand.

Two deliberate choices:

* Missing fields are printed as ruled blanks with their label, not omitted. A
  form with visible gaps is honest; a form that silently drops a required field
  gets rejected at the counter.
* Nothing is invented. If the profile has no IFSC, the IFSC line stays empty --
  a plausible-looking wrong bank code is far worse than a blank one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from ..config import STORAGE_DIR

# --------------------------------------------------------------------------
# form definitions
# --------------------------------------------------------------------------


@dataclass
class FormField:
    name: str                 # profile attribute
    required: bool = True
    label_key: str | None = None

    @property
    def key(self) -> str:
        return self.label_key or f"field.{self.name}"


# Nearly every welfare form opens with the same identity and address block.
IDENTITY_BLOCK = [
    FormField("full_name"),
    FormField("guardian_name", required=False),
    FormField("date_of_birth"),
    FormField("gender"),
    FormField("mobile"),
    FormField("aadhaar_last4"),
]

ADDRESS_BLOCK = [
    FormField("address_line"),
    FormField("village_town"),
    FormField("district"),
    FormField("state"),
    FormField("pincode"),
]

BANK_BLOCK = [
    FormField("bank_name"),
    FormField("ifsc"),
    FormField("account_last4"),
]

FORMS: dict[str, dict] = {
    "pm_kisan_form": {
        "title": "PM-KISAN registration",
        "extra": [FormField("land_holding_acres"), FormField("social_category", required=False)],
        "bank": True,
    },
    "pmjay_form": {
        "title": "Ayushman Bharat PM-JAY beneficiary verification",
        "extra": [FormField("ration_card_type"), FormField("family_size", required=False)],
        "bank": False,
    },
    "pmay_g_form": {
        "title": "PM Awaas Yojana (Gramin) application",
        "extra": [FormField("house_type"), FormField("ration_card_type"), FormField("family_size")],
        "bank": True,
    },
    "ujjwala_form": {
        "title": "PM Ujjwala Yojana 2.0 connection request",
        "extra": [FormField("ration_card_type"), FormField("social_category", required=False)],
        "bank": True,
    },
    "nsap_form": {
        "title": "National Social Assistance Programme pension application",
        "extra": [
            FormField("marital_status", required=False),
            FormField("disability_percent", required=False),
            FormField("ration_card_type"),
            FormField("annual_income"),
        ],
        "bank": True,
    },
    "mgnrega_form": {
        "title": "MGNREGA job card application (Form 1)",
        "extra": [FormField("family_size"), FormField("social_category", required=False)],
        "bank": True,
    },
    "pmmvy_form": {
        "title": "PM Matru Vandana Yojana claim",
        "extra": [FormField("marital_status", required=False)],
        "bank": True,
    },
    "scholarship_form": {
        "title": "Post-Matric Scholarship application",
        "extra": [
            FormField("social_category"),
            FormField("annual_income"),
            FormField("education_level"),
        ],
        "bank": True,
    },
    "apy_form": {
        "title": "Atal Pension Yojana subscriber registration",
        "extra": [],
        "bank": True,
    },
    "jansuraksha_form": {
        "title": "Jan Suraksha insurance consent form",
        "extra": [],
        "bank": True,
    },
    "ration_form": {
        "title": "NFSA ration card application",
        "extra": [FormField("annual_income"), FormField("family_size")],
        "bank": False,
    },
    "vishwakarma_form": {
        "title": "PM Vishwakarma artisan registration",
        "extra": [FormField("occupation"), FormField("social_category", required=False)],
        "bank": True,
    },
    "jan_dhan_form": {
        "title": "PM Jan Dhan Yojana account opening",
        "extra": [FormField("occupation", required=False)],
        "bank": False,
    },
}


def form_fields(form_id: str) -> list[FormField]:
    spec = FORMS.get(form_id)
    if not spec:
        return IDENTITY_BLOCK + ADDRESS_BLOCK
    fields = list(IDENTITY_BLOCK) + list(ADDRESS_BLOCK) + list(spec.get("extra", []))
    if spec.get("bank"):
        fields += list(BANK_BLOCK)
    return fields


@dataclass
class FilledForm:
    form_id: str
    title: str
    filled: dict = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    completion_percent: float = 0.0


def _display(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")       # Indian forms are day-first
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def autofill(form_id: str, profile) -> FilledForm:
    """Map the profile onto one form and report exactly what is still blank."""
    spec = FORMS.get(form_id, {})
    result = FilledForm(form_id=form_id, title=spec.get("title", form_id))

    fields = form_fields(form_id)
    for f in fields:
        value = getattr(profile, f.name, None)
        text = _display(value)
        if text:
            result.filled[f.name] = text
        else:
            result.missing.append(f.name)
            if f.required:
                result.missing_required.append(f.name)

    required = [f for f in fields if f.required]
    filled_required = sum(1 for f in required if f.name in result.filled)
    result.completion_percent = (
        round(100.0 * filled_required / len(required), 1) if required else 100.0
    )
    return result


# --------------------------------------------------------------------------
# PDF rendering
# --------------------------------------------------------------------------

def _register_indic_font() -> str:
    """Use a Unicode font when one is available so Indic names are not boxes.

    reportlab ships Latin-only Type 1 fonts. Nirmala UI covers Devanagari and
    Tamil and is present on Windows; on other platforms we look for the Noto
    equivalents. If nothing is found we fall back to Helvetica, which renders
    Latin correctly and is still a usable form.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        ("Nirmala", r"C:\Windows\Fonts\Nirmala.ttf"),
        ("NotoSansDev", "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
        ("NotoSans", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        ("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for name, path in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    return "Helvetica"


def _scheme_subtitle(scheme: dict) -> str:
    full_name = scheme.get("full_name")
    if isinstance(full_name, dict):
        return full_name.get("en", "")
    return full_name or ""


def render_pdf(
    form_id: str,
    profile,
    scheme: dict,
    filled: FilledForm,
    labels: dict[str, str],
    out_dir: Path | None = None,
) -> Path:
    """Draw a filled application form. Returns the path written."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    out_dir = out_dir or (STORAGE_DIR / "forms")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    path = out_dir / f"{form_id}_{getattr(profile, 'id', 0)}_{stamp}.pdf"

    font = _register_indic_font()
    bold = "Helvetica-Bold" if font == "Helvetica" else font
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    left, right = 20 * mm, width - 20 * mm
    y = height - 20 * mm

    # header
    c.setFont(bold, 15)
    c.drawString(left, y, filled.title)
    y -= 7 * mm
    c.setFont(font, 9.5)
    c.setFillGray(0.35)
    c.drawString(left, y, _scheme_subtitle(scheme))
    y -= 5 * mm
    c.drawString(left, y, f"Prepared {today} - draft for verification, not a submitted application")
    c.setFillGray(0)
    y -= 4 * mm
    c.line(left, y, right, y)
    y -= 9 * mm

    # completion banner
    c.setFont(bold, 10)
    if filled.missing_required:
        c.drawString(
            left, y,
            f"{filled.completion_percent:.0f}% complete - "
            f"{len(filled.missing_required)} required field(s) still blank",
        )
    else:
        c.drawString(left, y, "100% complete - ready to sign and submit")
    y -= 9 * mm

    # fields
    label_width = 62 * mm
    for f in form_fields(form_id):
        if y < 50 * mm:                       # keep room for the declaration block
            c.showPage()
            y = height - 20 * mm

        label = labels.get(f.key, f.name.replace("_", " ").title())
        if f.required:
            label += " *"

        c.setFont(font, 10)
        c.setFillGray(0.3)
        c.drawString(left, y, label)
        c.setFillGray(0)

        value = filled.filled.get(f.name, "")
        value_x = left + label_width
        if value:
            c.setFont(bold, 10.5)
            c.drawString(value_x, y, value)
        else:
            # ruled blank so the gap is obvious and writable
            c.setStrokeGray(0.6)
            c.line(value_x, y - 1.2 * mm, right, y - 1.2 * mm)
            c.setStrokeGray(0)
        y -= 8 * mm

    # declaration and signature
    y -= 4 * mm
    c.line(left, y, right, y)
    y -= 7 * mm
    c.setFont(font, 8.5)
    c.setFillGray(0.35)
    for line in [
        "I declare that the information given above is true to the best of my knowledge.",
        "Filled with assistance from the Haq document assistant. All details must be checked by the",
        "applicant and verified by the issuing office before submission.",
    ]:
        c.drawString(left, y, line)
        y -= 4.5 * mm

    c.setFillGray(0)
    y -= 8 * mm
    c.setStrokeGray(0.5)
    c.line(left, y, left + 55 * mm, y)
    c.line(right - 55 * mm, y, right, y)
    y -= 5 * mm
    c.setFont(font, 9)
    c.setFillGray(0.35)
    c.drawString(left, y, "Signature or thumb impression")
    c.drawRightString(right, y, "Date")

    c.save()
    return path
