# Haq documentation

Haq reads a person government documents, decides which welfare schemes they
qualify for, explains the answer in their language, fills in the form, and
reminds them before their papers expire.

Start here if you are new to the codebase. Read [ARCHITECTURE](ARCHITECTURE.md)
first, then whichever module you are about to touch.

| Document | Read it when |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | You want the system model: layers, request lifecycle, and the design decisions everything else follows from. |
| [USAGE.md](USAGE.md) | You want to install, run, demo, or troubleshoot the app. |
| [API.md](API.md) | You are calling the backend, writing a client, or adding an endpoint. |
| [DATA-MODEL.md](DATA-MODEL.md) | You need the database schema, the profile field catalogue, or how provenance is recorded. |
| [ELIGIBILITY.md](ELIGIBILITY.md) | You are adding a scheme or changing how eligibility is decided. |
| [OCR.md](OCR.md) | You are adding a document type, tuning extraction, or reviewing the privacy handling. |
| [I18N.md](I18N.md) | You are adding a language or changing user-facing wording. |

## The thirty second version

A person photographs whatever papers they have. The backend runs local OCR,
detects which document it is, extracts fields with a confidence score for each,
and folds them into a profile. A declarative rules engine evaluates sixteen
central-government schemes against that profile and returns one of three answers
per scheme: qualify, one detail missing, or not for you. The explainer turns
each verdict into plain-language sentences in the chosen language, including the
reasons and the concrete next step. A form autofiller maps the profile onto the
matching application form and draws a signable PDF. A vault tracks document
expiry and a tracker follows the application after it is submitted.

Nothing leaves the machine. No cloud OCR, no API keys, no outbound calls.

## Repository layout

```
backend/
  app/
    config.py          settings, languages, upload limits
    db.py              SQLite session plumbing
    models.py          five ORM tables
    schemas.py         request models and the editable field catalogue
    main.py            FastAPI application
    ocr/               provider chain, image normalisation
    extraction/        document detection, field patterns, redaction
    eligibility/       rules engine and scheme catalogue loader
    i18n/              translator, explainer, string bundles
    forms/             form templates, autofill, PDF rendering
    vault/             expiry states and reminders
    tracker/           application lifecycle
    routers/api.py     the whole HTTP surface
  data/schemes.json    the scheme catalogue
  storage/             uploaded documents and generated PDFs
frontend/
  app/                 Next.js App Router pages
  components/          Shell, SchemeCard, shared UI
  lib/                 typed API client, session context
samples/               synthetic demo documents plus their generator
docs/                  you are here
```

## Conventions used throughout

- **Dates** are stored ISO (`YYYY-MM-DD`) and displayed day-first
  (`DD/MM/YYYY`), which is how they are read in India.
- **Money** is stored as a plain number of rupees and formatted with Indian
  grouping and lakh or crore units for display.
- **User-facing text** never lives in the frontend. Every string comes from the
  backend so that wording and translation have a single source of truth.
- **Identity numbers** are never persisted in full. See
  [OCR.md](OCR.md) for the redaction rules.
