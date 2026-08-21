# Usage

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11 or newer | Developed on 3.12.5 |
| Node.js | 20 or newer | Developed on 22.16 |
| Disk | about 400 MB | Mostly onnxruntime and the OCR models |

No Tesseract, no poppler, no system OCR binary. The OCR models are pulled in by
pip as part of `rapidocr-onnxruntime` and run on the CPU.

## Install

### Backend

```
cd backend
python -m venv .venv
```

Windows:

```
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

macOS or Linux:

```
.venv/bin/python -m pip install -r requirements.txt
```

The first install downloads the ONNX detection and recognition models, roughly
15 MB. Everything after that is offline.

### Frontend

```
cd frontend
npm install
cp .env.example .env.local
```

`.env.local` holds the backend URL and is not committed. `.env.example` carries
the default, which matches the ports used below.

## Run

Two processes, two terminals.

**Terminal 1, backend:**

```
cd backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8010
```

**Terminal 2, frontend:**

```
cd frontend && npm run dev -- -p 3010
```

Then open <http://localhost:3010>.

| Surface | URL |
|---|---|
| App | http://localhost:3010 |
| API health | http://localhost:8010/api/health |
| Interactive API docs | http://localhost:8010/docs |

### Ports

The defaults in this repo are **8010** for the backend and **3010** for the
frontend, because 8000 and 3000 were already occupied on the machine this was
built on. To change them:

1. Start uvicorn with a different `--port`.
2. Update `NEXT_PUBLIC_API_BASE` in `frontend/.env.local`.
3. Restart the frontend so Next.js picks up the environment change.

CORS accepts any `localhost` or `127.0.0.1` origin in development, so the
frontend port does not need to be registered anywhere. Tighten
`CORS_ORIGIN_REGEX` in `backend/app/config.py` before deploying.

## Configuration

Everything lives in `backend/app/config.py` except the API base URL.

| Setting | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///backend/fed.db` | Override with the `FED_DATABASE_URL` environment variable |
| `STORAGE_DIR` | `backend/storage` | Uploaded originals and generated PDFs |
| `MAX_UPLOAD_BYTES` | 15 MB | Rejected with HTTP 413 above this |
| `ALLOWED_MIME_PREFIXES` | `image/`, `application/pdf` | Rejected with HTTP 415 otherwise |
| `LANGUAGES` | en, hi, ta | Add a row to offer another language |
| `DEFAULT_LANGUAGE` | `en` | Fallback for missing translations |
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8010` | In `frontend/.env.local` |

## Sample documents

Five synthetic documents for a fictional person live in `samples/`. They are
fabricated. The Aadhaar number is Verhoeff-valid so that the checksum path is
genuinely exercised, but it is generated from a fixed prefix and belongs to
nobody.

| File | Type | What it contributes |
|---|---|---|
| `01_aadhaar_sunita.png` | Aadhaar card | Name, date of birth, gender, address, PIN, last four digits |
| `02_ration_card_sunita.png` | Ration card | PHH category, family size, district |
| `03_income_certificate_sunita.png` | Income certificate | Annual income, issue date, expiry |
| `04_bank_passbook_sunita.png` | Bank passbook | IFSC, bank name, account last four |
| `05_disability_certificate_sunita.png` | Disability certificate | Disability percentage |

Regenerate them at any time:

```
backend/.venv/Scripts/python.exe samples/generate_samples.py
```

Edit `samples/generate_samples.py` to change the dates or details. The income
certificate is deliberately back-dated so that it falls inside the sixty day
expiry warning window and the vault has a live reminder to show.

## Demo script

Three minutes, and it lands best in Hindi because the language switch is the
most visible proof that the explainer is real.

**1. Open the app and press हिन्दी.**
Every heading, eligibility reason, next step and button switches language. The
switcher is in the header on every screen.

**2. Documents, then Take a photo, then choose `01_aadhaar_sunita.png`.**
Watch the result card: document type detected at high confidence, seven fields
extracted with a coloured dot per field showing confidence, and the number shown
as `XXXX XXXX 0124` with a note that the full number is never stored.

**3. Open My benefits.**
With one document almost every scheme reads *one detail missing*. This is the
point to make out loud: a binary engine would have said *not eligible* to all of
them. Instead the banner says which single document settles the most schemes.

**4. Add the ration card, then the income certificate, then the bank passbook.**
Eligible schemes climb from zero to two to three. The next-document prompt
changes each time as the highest-payoff gap moves.

**5. Add the disability certificate, then open Disability Pension.**
The explanation page shows why she qualifies, what was assumed and can be
corrected, the numbered steps ending at the Block Development Office, which
papers to carry with ticks for the ones she already has, and how long a decision
takes. Press the listen button to hear the whole page read aloud in Hindi.

**6. Press Apply.**
The form fills to 87 percent, names the two fields it cannot fill, and produces
a PDF. Download it: the filled values are there, the blanks are ruled lines with
labels, and it is stamped as a draft requiring verification.

**7. Open My applications and mark it Sent.**
A reference number is issued and the timeline starts.

**8. Open Document vault.**
Five documents with their expiry state, and a live reminder that the income
certificate lapses in forty five days.

## Common tasks

**Reset all data.** Stop the backend, then delete `backend/fed.db` and empty
`backend/storage/documents/` and `backend/storage/forms/`. The schema is
recreated on the next startup.

**Check what the OCR engine sees.** The health endpoint reports which providers
are available.

```
curl http://localhost:8010/api/health
```

**Add a scheme.** Edit `backend/data/schemes.json` and restart. Invalid rules
fail loudly at startup rather than silently misjudging somebody. See
[ELIGIBILITY.md](ELIGIBILITY.md).

**Add a language.** Copy `backend/app/i18n/strings/en.json`, translate, add a
row to `LANGUAGES`. See [I18N.md](I18N.md).

**Type-check the frontend without touching the dev build:**

```
cd frontend && npx tsc --noEmit
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `error while attempting to bind on address` | Port already in use | Start uvicorn on another port and update `NEXT_PUBLIC_API_BASE` |
| UI shows raw keys like `nav.home` | The strings request failed, so `t()` is returning keys | Check the backend is running and that `NEXT_PUBLIC_API_BASE` matches its port |
| Red banner: cannot reach the server | Backend down or wrong port | Confirm `curl http://localhost:8010/api/health` returns JSON |
| Blank page and 404s for JS chunks | `npm run build` was run while `next dev` was running, replacing `.next` | Restart the dev server. Use `npx tsc --noEmit` to type-check instead |
| Upload returns 415 | File is not an image or PDF | Only `image/*` and `application/pdf` are accepted |
| Upload returns 413 | File larger than 15 MB | Raise `MAX_UPLOAD_BYTES` or downscale the photo |
| `ocr_unavailable_enter_manually` warning | No provider could read the file | Fields can still be typed on the profile screen. Check `rapidocr-onnx` is true on the health endpoint |
| `pdf_has_no_text_layer` | A scanned PDF with no embedded text | Upload a photograph of the page instead |
| `aadhaar_checksum_failed` | OCR misread a digit | Expected on poor photographs. The field is kept at low confidence and flagged for checking |
| PDF shows boxes instead of Devanagari | No Unicode font found | The renderer looks for Nirmala UI on Windows and Noto or DejaVu elsewhere, then falls back to Helvetica |
| `UnicodeEncodeError` running a script | Windows console defaults to cp1252 | Prefix with `PYTHONIOENCODING=utf-8`. It does not affect the server, which emits UTF-8 JSON |
| Read-aloud button missing | No installed voice for that language | The button hides rather than reading Hindi in an English accent. Install the language voice pack in the operating system |

## Deploying

Not production ready as it stands. The gaps that must close first:

1. Authentication and per-user isolation. The profile id is currently an
   unauthenticated integer in `localStorage`.
2. Encryption at rest for `storage/` and the database.
3. A real migration tool instead of `create_all`.
4. `CORS_ORIGIN_REGEX` narrowed to the actual frontend origin.
5. Rule versioning, so an application records which version of the criteria it
   was judged against.
6. A review process for `schemes.json`, since an error there misinforms somebody
   about a legal entitlement.
