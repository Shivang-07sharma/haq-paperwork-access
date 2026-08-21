"""Generate synthetic government documents for demos and tests.

These are fabricated documents for a fictional person. They exist so the OCR
pipeline can be exercised without anybody uploading a real identity document.
The Aadhaar number is Verhoeff-valid because the extractor checks the checksum,
but it belongs to no one -- it is generated from a fixed prefix.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))
from app.extraction.patterns import verhoeff_valid  # noqa: E402

W, H = 1000, 640
REG = "C:/Windows/Fonts/arial.ttf"
BOLD = "C:/Windows/Fonts/arialbd.ttf"


def font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype(BOLD if bold else REG, size)
    except OSError:
        return ImageFont.load_default()


def make_aadhaar_number() -> str:
    prefix = "23456789012"
    return next(prefix + str(d) for d in range(10) if verhoeff_valid(prefix + str(d)))


AADHAAR = make_aadhaar_number()
SPACED = f"{AADHAAR[:4]} {AADHAAR[4:8]} {AADHAAR[8:]}"


def card(name: str, band: tuple, band_text: str, rows: list) -> Path:
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 90], fill=band)
    d.text((36, 30), band_text, font=font(30, True), fill="white")
    for x, y, text, size, bold in rows:
        d.text((x, y), text, font=font(size, bold), fill="black")
    d.rectangle([0, 0, W - 1, H - 1], outline=(180, 180, 180), width=2)
    out = HERE / name
    img.save(out, "PNG")
    return out


def main() -> None:
    made = []

    made.append(card(
        "01_aadhaar_sunita.png", (200, 30, 30), "Government of India",
        [
            (36, 130, "Unique Identification Authority of India", 22, False),
            (36, 200, "Sunita Devi", 40, True),
            (36, 260, "DOB: 12/04/1968", 28, False),
            (36, 305, "FEMALE", 28, False),
            (36, 380, SPACED, 46, True),
            (36, 460, "Address: W/O Ramesh Kumar, Village Bakhtiyarpur,", 20, False),
            (36, 492, "District Patna, Bihar 801505", 20, False),
            (36, 560, "Aadhaar - Aam Aadmi ka Adhikar", 18, False),
        ],
    ))

    made.append(card(
        "02_ration_card_sunita.png", (20, 90, 50), "Ration Card - Government of Bihar",
        [
            (36, 130, "National Food Security Act (NFSA)", 22, False),
            (36, 185, "PRIORITY HOUSEHOLD (PHH)", 34, True),
            (36, 250, "Card No: BR2019004512378", 26, False),
            (36, 300, "Name: Sunita Devi", 30, True),
            (36, 350, "District: Patna", 24, False),
            (36, 392, "Fair Price Shop: Bakhtiyarpur Block 4", 22, False),
            (36, 440, "Total Members: 4", 26, False),
            (36, 500, "Khadya Suraksha - Rashan Card", 20, False),
        ],
    ))

    made.append(card(
        "03_income_certificate_sunita.png", (40, 60, 130), "Office of the Tehsildar",
        [
            (36, 130, "Revenue Department, Government of Bihar", 22, False),
            (36, 190, "INCOME CERTIFICATE", 38, True),
            (36, 250, "Aay Praman Patra", 24, False),
            (36, 320, "Name: Sunita Devi", 30, True),
            (36, 372, "Annual Income: Rs. 84,000", 32, True),
            (36, 430, "Purpose: Government scheme application", 22, False),
            (36, 480, "Date of Issue: 05/10/2025", 26, False),
            (36, 540, "Signature of Tehsildar, Bakhtiyarpur", 20, False),
        ],
    ))

    made.append(card(
        "04_bank_passbook_sunita.png", (10, 60, 110), "State Bank of India",
        [
            (36, 130, "Savings Account Passbook", 26, False),
            (36, 200, "Name: Sunita Devi", 32, True),
            (36, 260, "Account Number: 30124578963", 28, False),
            (36, 315, "IFSC: SBIN0001234", 30, True),
            (36, 370, "Branch: Bakhtiyarpur", 26, False),
            (36, 420, "Account Type: Basic Savings Bank Deposit", 22, False),
            (36, 480, "Customer since: 2016", 22, False),
        ],
    ))

    made.append(card(
        "05_disability_certificate_sunita.png", (90, 40, 110), "Medical Board Certificate",
        [
            (36, 130, "Department of Empowerment of Persons with Disabilities", 20, False),
            (36, 190, "DISABILITY CERTIFICATE", 36, True),
            (36, 250, "UDID Card", 24, False),
            (36, 320, "Name: Sunita Devi", 30, True),
            (36, 375, "Percentage of Disability: 85 %", 32, True),
            (36, 435, "Type: Locomotor disability", 24, False),
            (36, 490, "Date of Issue: 11/06/2024", 24, False),
        ],
    ))

    print("Aadhaar number used (synthetic, checksum valid):", SPACED)
    for path in made:
        print("  wrote", path.name)


if __name__ == "__main__":
    main()
