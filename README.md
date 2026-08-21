# Haq — paperwork and access

**The help you are entitled to.**

Photograph your government documents. Haq reads them, works out which welfare
schemes you qualify for, explains the answer in your language with the reasons
spelled out, fills in the application form, and reminds you before your papers
expire.

Built for the *Paperwork & Access* challenge: making government schemes,
documents, forms and claims navigable for people who find them opaque.

> **Documentation:** [`docs/`](docs/README.md) —
> [Architecture](docs/ARCHITECTURE.md) ·
> [Usage](docs/USAGE.md) ·
> [API](docs/API.md) ·
> [Data model](docs/DATA-MODEL.md) ·
> [Eligibility](docs/ELIGIBILITY.md) ·
> [OCR](docs/OCR.md) ·
> [Languages](docs/I18N.md)

---

## Why this shape

Most benefits-finder tools ask twenty questions and return a list of links. Two
choices here are different, and everything else follows from them.

**1. A rule has three outcomes, not two.** Pass, fail, and *unknown*. A binary
engine has to treat "we have no income certificate" as "you do not qualify" —
exactly the failure mode that keeps people away from money they are owed. Here
an unmet rule with no data becomes a question to ask or a document to fetch, and
the scheme is reported as `need_more_info` rather than rejected. That in turn
powers the most useful prompt in the app: not *upload your documents*, but
**"add your bank passbook — it settles 5 more schemes."**

**2. The document is the input, not a form.** People do not know their social
category code or their annual income to the rupee. They do have a ration card in
a plastic sleeve. So OCR runs first, the profile is built from what the papers
say, and the person is asked only the handful of questions that no document can
answer — ranked by how many schemes each one unblocks.

---

## The six modules

| Module | Where | What it does |
|---|---|---|
| Document OCR | [`backend/app/ocr/`](backend/app/ocr/engine.py) | Provider chain: local ONNX text recognition, PDF text layer, optional Tesseract. Never calls out to a cloud service. |
| Field extraction | [`backend/app/extraction/`](backend/app/extraction/documents.py) | Detects 12 Indian document types by keyword scoring; pulls fields with per-field confidence; validates the Aadhaar Verhoeff checksum; redacts before storing. |
| Eligibility engine | [`backend/app/eligibility/`](backend/app/eligibility/engine.py) | Tri-state evaluation of declarative JSON rules. No `eval`. 16 real central schemes in [`data/schemes.json`](backend/data/schemes.json). |
| Vernacular explainer | [`backend/app/i18n/`](backend/app/i18n/translator.py) | Turns a verdict into what-this-is / what-you-get / why-you-qualify / what-to-do-next, plus a flat string for browser text-to-speech. |
| Form autofill | [`backend/app/forms/`](backend/app/forms/autofill.py) | Maps the profile onto 13 form templates and draws a filled PDF with ruled blanks where data is still missing. |
| Vault, reminders, tracker | [`backend/app/vault/`](backend/app/vault/service.py), [`backend/app/tracker/`](backend/app/tracker/service.py) | Expiry tracking with reminders stored as i18n keys; application lifecycle with a guarded status machine and an event timeline. |

Frontend: Next.js App Router, mobile-first, in [`frontend/app/`](frontend/app).

---

## Run it

Two processes. Python 3.12+ and Node 20+.

**Backend** (first run downloads the OCR models, roughly 15 MB):

```bash
cd backend && python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

```bash
cd backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8010
```

**Frontend:**

```bash
cd frontend && npm install && npm run dev -- -p 3010
```

Open <http://localhost:3010>. API docs at <http://localhost:8010/docs>.

If you change the backend port, update `frontend/.env.local`
(`NEXT_PUBLIC_API_BASE`). On macOS or Linux the interpreter path is
`.venv/bin/python` rather than `.venv/Scripts/python.exe`.

---

## Demo in three minutes

Sample documents for a fictional person are in [`samples/`](samples) — regenerate
them any time with `python samples/generate_samples.py`. They are fabricated;
the Aadhaar number is checksum-valid but belongs to nobody.

1. **Open the app, pick हिन्दी.** Every heading, reason and step switches
   language, including the read-aloud button.
2. **Add `01_aadhaar_sunita.png`.** Watch it detect the card at ~98% confidence
   and pull name, date of birth, gender, address and PIN — with the number shown
   as `XXXX XXXX 0124` and a note that the full number is never stored.
3. **Go to My benefits.** With one document, almost everything reads
   *"one detail missing"*, and the app says which paper to add next.
4. **Add the ration card, income certificate and bank passbook.** Eligible
   schemes climb from 0 to 4; the prompt updates each time.
5. **Open a scheme.** Read why she qualifies, what is assumed, the numbered
   steps, which papers to carry, and where to go. Press **सुनें** to hear it.
6. **Apply.** The form fills to 87%, names the two blanks it cannot fill, and
   produces a signable PDF. Submitting issues a reference number and starts the
   timeline.

---

## Design decisions worth a look

- **Aadhaar is never stored in full.** Extraction sees the number long enough to
  verify the Verhoeff check digit and keep the last four; the OCR text is
  scrubbed before it touches the database ([`patterns.py`](backend/app/extraction/patterns.py), `redact`).
- **Conflicting documents resolve by confidence, not by arrival order.** A
  ration card and an Aadhaar card both claim to know your name. The more
  confident read wins, and anything a person typed themselves outranks every OCR
  result ([`api.py`](backend/app/routers/api.py), `_merge_into_profile`).
- **Cash and cover are never added together.** Summing a ₹5 lakh hospital cover
  into a yearly income figure would tell a widow on a ₹300 pension she is owed
  lakhs. They are reported as separate numbers.
- **Unknown exclusions are shown as assumptions.** If we cannot check whether
  somebody pays income tax, the scheme still shows as eligible, but the page
  says plainly what was assumed and offers to correct it.
- **Provenance for every field.** The profile screen shows *"from your ration
  card"* or *"you entered this"* next to each value, so a wrong OCR read is
  visible and fixable rather than silently baked into a form.
- **Partial translations report themselves.** Language coverage is measured at
  runtime; a language below full coverage is served English-backfilled and
  flagged, never passed off as complete.

---

## Honest limitations

- **Eligibility here is triage, not adjudication.** The rules encode headline
  central-government criteria and deliberately omit state variations, SECC
  deprivation codes and annual revisions. Every screen carries a disclaimer that
  only the government office decides. Verify against the official portal before
  telling anyone they do or do not qualify.
- **Scheme descriptions exist in English and Hindi only.** The UI, all
  eligibility reasons, field labels and next-step wording are also in Tamil
  (~82% coverage); Tamil scheme prose falls back to English. Adding a language is
  a JSON file plus one row in `config.LANGUAGES` — no code change.
- **OCR is tuned on clean printed documents.** It handles the generated samples
  and good phone photos well. Worn, folded, low-light or handwritten documents
  will degrade, which is why every extracted field is editable and low-confidence
  values are flagged rather than trusted.
- **Application status is self-reported.** No government portal exposes an API
  for this. The tracker holds the thread — what was applied for, when, under
  which reference — so the app can answer "did I already apply?" and "how long
  has it been?" and prompt a follow-up after 30 days.
- **Generated PDFs are drafts, not official forms.** They carry the right fields
  and a declaration, and are marked as requiring verification. Real submission
  still happens at the counter or on the scheme portal.
- **No authentication.** The profile id lives in `localStorage`. Fine for a
  prototype on a shared kiosk demo; a real deployment needs a proper session and
  encryption at rest.

---

## Extending it

**Add a scheme** — append an object to `backend/data/schemes.json`. Rules are
declarative and validated at startup:

```json
{ "field": "age", "op": ">=", "value": 60, "key": "rule.age_min", "args": { "n": 60 } }
```

Operators: `==`, `!=`, `in`, `not_in`, `>`, `>=`, `<`, `<=`, `is_true`,
`is_false`, `exists`; combine with `all`, `any`, `not`. If a rule needs a field
the profile does not have, add it to `models.Profile`, `schemas.FIELD_SPECS`
and `eligibility.FIELD_SOURCES` so the app knows which document supplies it.

**Add a language** — copy `backend/app/i18n/strings/en.json` to `<code>.json`,
translate, and add a row to `LANGUAGES` in `backend/app/config.py` with a
BCP-47 tag for speech.

**Add a document type** — add a keyword signature to `DOC_SIGNATURES` and an
extractor to `_EXTRACTORS` in `backend/app/extraction/documents.py`.

---

## API

Eighteen endpoints under `/api`. Full schema at `/docs`.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Status, OCR providers available, scheme count |
| `GET /api/meta/{languages,strings,doc-types,fields}` | Everything the UI renders from |
| `POST /api/profiles`, `GET`/`PATCH /api/profiles/{id}` | Profile lifecycle |
| `GET /api/profiles/{id}/questions` | Self-declared questions, ranked by schemes unlocked |
| `POST /api/profiles/{id}/documents` | Upload, OCR, extract, merge — returns what changed |
| `GET /api/profiles/{id}/schemes[/{scheme_id}]` | Ranked verdicts and full explanations |
| `POST /api/profiles/{id}/applications` | Autofill and render the form |
| `POST /api/applications/{id}/status` | Advance the tracker |
| `GET /api/applications/{id}/form` | Download the filled PDF |
| `GET /api/profiles/{id}/vault` | Documents, expiry states, reminders |

---

## Stack

FastAPI · SQLAlchemy · SQLite · RapidOCR (ONNX) · Pillow · pdfplumber ·
ReportLab · Next.js 14 · React 18 · Tailwind CSS · TypeScript

Everything runs locally. No outbound network calls, no API keys, no cloud OCR —
a deliberate constraint, because these documents carry identity numbers and the
deployment target is a Common Service Centre desktop with unreliable
connectivity.
