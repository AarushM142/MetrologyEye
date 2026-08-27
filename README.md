# MetrologyEye — SIH 2026 (Problem Statement 26034)

> **Automated Legal Metrology compliance checker for packaged commodity labels.**
>
> A field inspector photographs a label → the system extracts every mandatory declaration,
> validates them against the LMPC Rules 2011, and produces a ready-to-sign Form-I notice
> PDF — all in under 3 seconds.

---

## Table of Contents

1. [What this is](#1-what-this-is)
2. [Architecture at a glance](#2-architecture-at-a-glance)
3. [Prerequisites](#3-prerequisites)
4. [Repository layout](#4-repository-layout)
5. [First-time setup](#5-first-time-setup)
6. [Configure your environment](#6-configure-your-environment)
7. [Run the backend](#7-run-the-backend)
8. [Run the tests](#8-run-the-tests)
9. [API quick-reference](#9-api-quick-reference)
10. [Working without a Gemini API key (offline / demo mode)](#10-working-without-a-gemini-api-key-offline--demo-mode)
11. [Project conventions](#11-project-conventions)
12. [Known limitations](#12-known-limitations)

---

## 1. What this is

MetrologyEye is a FastAPI backend that implements the following pipeline for every uploaded label image:

```
Image upload
    ↓
Preprocess   — exposure correction, curved-label dewarp, deskew, glare reduction, CLAHE
    ↓
Scale        — detect EAN-13 barcode → px/mm conversion for font-height checks
    ↓
OCR          — PaddleOCR word polygons (gives precise bounding boxes)
    ↓
Verify       — Gemini receives OCR text + image → corrects errors, structures declarations
    ↓
Fuse         — join Gemini values to OCR geometry (OCR owns position, Gemini owns meaning)
    ↓
Rules        — deterministic engine validates against LMPC Rules 2011 catalogue
    ↓
Notice       — ReportLab generates a Form-I PDF with evidence crops and statutory citations
```

The frontend (Next.js 15) is in the **Phase 7** implementation stage and is not yet in this repository.

---

## 2. Architecture at a glance

```
SIH2026/
├── .env                    ← placeholder; real secrets go in MetrologyEyeApp/backend/.env
├── .gitignore
├── Plan.md                 ← original project design document
├── premortem.md            ← risk register
└── MetrologyEyeApp/
    └── backend/            ← FastAPI application (Python 3.12)
        ├── .env            ← YOUR LOCAL SECRETS (never committed)
        ├── .env.example    ← template — copy this to .env
        ├── requirements.txt
        ├── pytest.ini
        ├── app/
        │   ├── main.py         entry point (uvicorn app.main:app)
        │   ├── config.py       all environment config in one place
        │   ├── schemas/        Pydantic models (the API contract)
        │   ├── api/routes.py   HTTP endpoints
        │   ├── store.py        in-memory TTL store for analysis results
        │   ├── fixtures.py     offline/demo extraction fallback
        │   └── services/
        │       ├── preprocess.py   exposure, dewarp, deskew, CLAHE
        │       ├── scale.py        barcode → px/mm
        │       ├── ocr.py          PaddleOCR word polygons
        │       ├── extract.py      Gemini verification of OCR output
        │       ├── fuse.py         geometry + semantics join
        │       ├── pipeline.py     orchestrator
        │       ├── notice.py       Form-I PDF generator
        │       ├── ingest.py       URL-based label ingestion
        │       └── rules/
        │           ├── catalogue.yaml  ← edit this to change statutory rules
        │           └── engine.py
        └── tests/              full test suite (119 tests, 0 external calls)
```

---

## 3. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| **Python** | 3.12.x | 3.11 probably works; 3.13 is untested |
| **pip** | latest | bundled with Python |
| **Gemini API key** | — | free tier at https://aistudio.google.com. **Optional** — the system runs fully offline without it |

> **Windows note:** all commands below use PowerShell. Substitute `/` for `\` on macOS/Linux.

---

## 4. Repository layout

The repo lives at `C:\Users\Asus\SIH2026` (or wherever you clone it). There is currently
**one runnable application** — the FastAPI backend in `MetrologyEyeApp/backend/`. The Next.js
frontend will live in `MetrologyEyeApp/frontend/` once Phase 7 is implemented.

---

## 5. First-time setup

```powershell
# 1. Navigate to the backend
cd MetrologyEyeApp\backend

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
.venv\Scripts\Activate.ps1        # PowerShell
# or:  .venv\Scripts\activate.bat  # cmd.exe
# or:  source .venv/bin/activate   # bash / zsh

# 4. Install dependencies
pip install -r requirements.txt
```

> **PaddleOCR note:** the install downloads ~200 MB of model weights on first use.
> This happens automatically when the server starts for the first time — expect a
> 30–60 second pause on first launch. Subsequent starts are fast.

---

## 6. Configure your environment

```powershell
# From MetrologyEyeApp/backend/
cp .env.example .env
```

Then open `.env` in your editor and fill in the values:

```env
# REQUIRED for live Gemini extraction.
# Leave empty to run in mocked/offline mode (fully functional for demos).
GEMINI_API_KEY=your_key_here

# Everything else has a working default — you probably don't need to change these:
GEMINI_MODEL=gemini-1.5-flash
GEMINI_TIMEOUT_S=20.0
CORS_ORIGIN=http://localhost:3000
MAX_UPLOAD_MB=12
ANALYSIS_TTL_SECONDS=3600
MAX_IMAGE_EDGE_PX=1600
```

See `.env.example` for the full list with comments explaining each variable.

> ⚠️ **Never commit `.env`.** It is already in `.gitignore`. If you accidentally stage it,
> run `git rm --cached MetrologyEyeApp/backend/.env` before pushing.

---

## 7. Run the backend

```powershell
# From MetrologyEyeApp/backend/ with the venv activated
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

The API is now available at **http://localhost:8000**.

| URL | What it is |
|-----|-----------|
| http://localhost:8000/health | Liveness check + capability report |
| http://localhost:8000/docs | Interactive Swagger UI (explore all endpoints) |
| http://localhost:8000/redoc | ReDoc documentation |

**Verify the server started correctly:**

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","extraction":"gemini","gemini_model":"gemini-1.5-flash","ocr":"paddleocr"}
# If no API key: {"status":"ok","extraction":"mocked","gemini_model":null,"ocr":"paddleocr"}
```

---

## 8. Run the tests

```powershell
# From MetrologyEyeApp/backend/ with the venv activated
.venv\Scripts\python -m pytest tests\ -v
```

The test suite:
- **119 tests, 0 external calls** — no Gemini quota is consumed, no network is required.
- Covers: preprocessing, scale detection, OCR fusion, rules engine, all API endpoints,
  notice generation.
- Target: **119/119 passed** in ~15 seconds.

```powershell
# Run a specific test file
.venv\Scripts\python -m pytest tests\test_rules_engine.py -v

# Run a specific test
.venv\Scripts\python -m pytest tests\test_api.py::test_analyze_finds_the_three_seeded_violations -v
```

---

## 9. API quick-reference

### Upload a label image
```http
POST /api/analyze
Content-Type: multipart/form-data

file: <image file>              # JPEG, PNG, WebP, BMP
manual_px_per_mm: 8.0           # optional — overrides barcode scale
```

### Ingest from a URL
```http
POST /api/analyze/url
Content-Type: application/json

{"url": "https://example.com/product-label.jpg"}
```

### Get a stored analysis (survives page refresh)
```http
GET /api/analysis/{id}
```

### Get the preprocessed image (coordinate frame for canvas)
```http
GET /api/image/{id}
```

### Recalibrate scale without a new Gemini call
```http
PATCH /api/analysis/{id}/calibrate
Content-Type: application/json

{"manual_px_per_mm": 9.5}
```

### Generate Form-I notice PDF
```http
POST /api/notice
Content-Type: application/json

{
  "analysis_id": "...",
  "inspector_name": "A. Deshmukh",
  "inspector_designation": "Legal Metrology Officer",
  "premises": "Retail outlet, Nashik"
}
```

---

## 10. Working without a Gemini API key (offline / demo mode)

Leave `GEMINI_API_KEY` empty in `.env`. The backend automatically falls back to the
**fixture extractor** (`app/fixtures.py`), which returns a pre-written set of declarations
for a fictional "Suraj Refined Sunflower Oil" label.

Every response in offline mode carries `"degraded": ["extract_mocked"]`. The banner
appears in the frontend so the inspector/judge knows this is a demo run.

**Everything else runs on real code paths in offline mode:**
- Exposure correction, dewarp, deskew, glare reduction, CLAHE ✅
- EAN-13 barcode scale detection ✅
- PaddleOCR word polygons ✅
- Rules engine (all 9 rules, LMPC 2011 catalogue) ✅
- Form-I PDF with evidence crops (if OCR located the declaration) ✅

This means the demo is fully functional and professionally presentable without a Gemini key.

---

## 11. Project conventions

### Rules catalogue
All statutory rules live in `app/services/rules/catalogue.yaml`. To add or modify a rule,
edit this file — **do not touch `engine.py`** unless you are adding a new check type.
Every citation is marked `verified: false` until it has been manually checked against the
official LMPC 2011 text.

### Adding a new environment variable
1. Add it to `app/config.py` as a typed field on `Settings`.
2. Add a commented entry to `MetrologyEyeApp/backend/.env.example`.
3. Document it in this README.

### Code style
No linter is currently configured. Follow the existing style: type annotations on all
public functions, docstrings on every module and class, `from __future__ import annotations`
at the top of every file.

### No frontend yet
The Next.js frontend is scaffolded in Phase 7. When it is added, it will live at
`MetrologyEyeApp/frontend/` and connect to the backend via the API above.

---

## 12. Known limitations

| Limitation | Impact | Planned fix |
|-----------|--------|-------------|
| **Citations unverified** | Every statutory reference is marked `[unverified]` in the PDF. Do not use for real enforcement without checking against the official LMPC 2011 text. | Manual verification task |
| **Barcode scale assumes 100% magnification** | The print magnification (80–200% is legal) is unknown from a photograph. Font-height findings are `WARNING` not `VIOLATION`. | Physical measurement / barcode spec lookup |
| **In-memory store only** | Analyses expire after `ANALYSIS_TTL_SECONDS` (default 1 hour). A server restart clears everything. | Supabase integration in `store.py` (pre-wired) |
| **Gemini is non-deterministic** | Same image can produce slightly different extracted values across runs. The rules engine is deterministic given the same input. | Accepted — stated in PRD §15 |
| **URL ingestion is fragile** | Relies on `og:image` and visible `<img>` tags. Marketplace HTML changes break it. | Two demo fixtures cached as fallbacks |

---

## Getting help

- **API schema:** http://localhost:8000/docs (Swagger UI with try-it-out)
- **Design decisions:** `Plan.md` in the repo root
- **Risk register:** `premortem.md` in the repo root
- **Implementation plan:** `.gemini/antigravity/brain/*/implementation_plan.md`
