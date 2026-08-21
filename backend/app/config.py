"""Central configuration for the Paperwork & Access backend."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "documents").mkdir(exist_ok=True)
(STORAGE_DIR / "forms").mkdir(exist_ok=True)

DATABASE_URL = os.getenv("FED_DATABASE_URL", f"sqlite:///{(BASE_DIR / 'fed.db').as_posix()}")

# Dev servers land on whatever port is free, so match any localhost origin
# rather than pinning 3000. Tighten this to an explicit list before deploying.
CORS_ORIGIN_REGEX = r"http://(localhost|127\.0\.0\.1):\d+"

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB
ALLOWED_MIME_PREFIXES = ("image/", "application/pdf")

# Languages the explainer can speak. `tts` is the BCP-47 tag handed to the
# browser's speech synthesiser so the UI can read pages aloud.
#
# Adding a language is a drop-in: translate app/i18n/strings/en.json to
# <code>.json and add a row here. Coverage is measured at runtime, so a partial
# translation is served with the gaps backfilled from English and reported as
# incomplete rather than silently passed off as finished.
LANGUAGES = {
    "en": {"label": "English", "native": "English", "tts": "en-IN"},
    "hi": {"label": "Hindi",   "native": "हिन्दी",    "tts": "hi-IN"},
    "ta": {"label": "Tamil",   "native": "தமிழ்",    "tts": "ta-IN"},
}
DEFAULT_LANGUAGE = "en"

# UIDAI requires that a stored Aadhaar number be masked. We never persist more
# than the trailing four digits anywhere -- raw OCR text is redacted on ingest.
REDACT_AADHAAR = True
