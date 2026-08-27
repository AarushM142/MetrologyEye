# MetrologyEye (SIH26034) — Implementation Plan

## Context

We are building a working end-to-end prototype in 4–5 days that scans packaged-commodity
labels, extracts mandatory declarations, validates them against the Legal Metrology
(Packaged Commodities) Rules, 2011, and emits a Form-I inspection notice PDF. Source specs:
the PRD and the End-to-End Demo Workflow doc supplied in this session.

`C:\Users\Asus\SIH2026\MetrologyEyeApp` is currently empty apart from `.claude/` config, `.mcp.json`,
and the two Supabase skills — this is a greenfield build, no existing code to reuse.

Three specification risks were identified during planning and are designed around below
rather than discovered mid-build: the barcode scale anchor is not absolute, VLM bounding
boxes are too coarse to measure font height, and the statutory citations need verification
against the official text (Indian government sites are unreachable from this environment).

**Decisions confirmed with the user:** install Python 3.12; real Gemini API via
`GEMINI_API_KEY` from the environment; PaddleOCR for word-level boxes.

---

## Step 0 — Environment prerequisite (blocking)

Python is not installed. Nothing backend runs until this is done:

```bash
winget install -e --id Python.Python.3.12
```

Then a new terminal, and `python --version` must report 3.12.x. Node 24.19 / npm 12 are
already present for the frontend.

---

## Architecture

```
MetrologyEyeApp/
├── backend/
│   ├── requirements.txt
│   ├── .env.example              # GEMINI_API_KEY, GEMINI_MODEL, CORS_ORIGIN
│   └── app/
│       ├── main.py               # FastAPI app, CORS, /health
│       ├── config.py             # pydantic-settings; model name is config, not literal
│       ├── schemas/
│       │   ├── analysis.py       # AnalyzeResponse, Declaration, BBox, ScaleInfo
│       │   └── violations.py     # Violation, Severity, RuleCitation
│       ├── services/
│       │   ├── preprocess.py     # deskew, glare reduction, CLAHE, perspective correct
│       │   ├── scale.py          # EAN-13 detect → px_per_mm + confidence
│       │   ├── ocr.py            # PaddleOCR → word boxes + polygons
│       │   ├── extract.py        # Gemini structured JSON (declaration fields)
│       │   ├── fuse.py           # match Gemini field values → OCR boxes (geometry source)
│       │   ├── rules/
│       │   │   ├── engine.py     # deterministic evaluator over catalogue
│       │   │   └── catalogue.yaml# rule defs + statutory citations  ← single edit point
│       │   └── notice.py         # ReportLab Form-I with cropped evidence
│       └── api/routes.py         # POST /api/analyze, POST /api/notice, GET /api/notice/{id}
└── frontend/                     # Next.js 15 App Router, TS, Tailwind
    ├── app/
    │   ├── page.tsx              # Screen 1 — upload / capture / paste URL
    │   ├── analyze/page.tsx      # Screen 2 — staged progress
    │   ├── results/page.tsx      # Screen 3 — canvas evidence viewer
    │   └── notice-preview/page.tsx # Screen 4 — embed + download
    ├── components/
    │   ├── Dropzone.tsx
    │   ├── EvidenceCanvas.tsx    # HTML5 canvas, colour-coded boxes, hover→rule
    │   └── StageProgress.tsx
    └── lib/api.ts, lib/types.ts  # types mirror backend schemas
```

---

## Key technical decisions

**1. OCR owns geometry, Gemini owns semantics.** Gemini returns field *values* and *labels*
only. PaddleOCR returns precise word polygons. `fuse.py` matches extracted values to OCR
words by normalised string similarity and takes the box from OCR. This is what makes the
font-height check meaningful — VLM boxes alone are not accurate enough to measure against a
statutory minimum.

**2. Barcode scale is an estimate with declared confidence.** An EAN-13 symbol is nominally
37.29 mm wide at 100 % magnification but is legally printed from ~80 % to 200 %. So
`scale.py` returns `{px_per_mm, confidence, assumed_magnification: 1.0}` and the UI exposes a
manual calibration slider. All font-size findings are emitted as **WARNING** severity (yellow),
never as hard violations — which matches the demo doc's own colour semantics. The assumption
is printed in the PDF notice so it is never silently load-bearing.

**3. Citations live in `catalogue.yaml`, not in code.** Each rule carries
`id, description, citation, severity, check`. Citations are seeded from your two spec docs
(Rules 6, 7, 13; Section 15 of the Legal Metrology Act, 2009) and marked `verified: false`.
Correcting a citation is a one-line YAML edit, no code change, no redeploy.

**4. Barcode detection avoids the pyzbar DLL trap.** Primary detector is OpenCV's
`cv2.barcode.BarcodeDetector` (ships in `opencv-contrib-python`, no native install). `pyzbar`
is an optional fallback, imported lazily so a missing `libzbar` never breaks startup.

**5. Gemini model name is configuration.** `GEMINI_MODEL` defaults to `gemini-1.5-flash` per
the PRD but is env-overridable — 1.5 Flash is old enough that it may be unavailable on new
keys, and that must not require a code change.

### Rules shipped in the catalogue

| Rule | Check | Severity |
|---|---|---|
| Non-standard unit symbols (`gms`, `gm`, `ltr`, `lt`) vs `g`/`kg`/`ml`/`l` | regex on net-qty | VIOLATION |
| MRP present without "inclusive of all taxes" | value + text presence | VIOLATION |
| Missing mandatory declaration (mfr name & address, net qty, MRP, mfg month/year, consumer-care, country of origin) | field presence, one finding each | VIOLATION |
| MRP not in `₹`/`Rs.` + numeric form | regex | VIOLATION |
| Unparseable / implausible mfg date | date parse | VIOLATION |
| Letter height below statutory minimum | OCR box height × `px_per_mm` | WARNING |

---

## API contract (fix first — unblocks parallel frontend work)

`POST /api/analyze` (multipart image **or** `{"url": "..."}`) →

```json
{
  "analysis_id": "uuid",
  "image": { "width": 1600, "height": 1200, "preview_url": "/api/image/uuid" },
  "scale": { "px_per_mm": 7.42, "confidence": 0.81, "source": "ean13", "assumed_magnification": 1.0 },
  "declarations": [
    { "field": "net_quantity", "value": "500 gms", "bbox": [x,y,w,h], "confidence": 0.94 }
  ],
  "violations": [
    { "rule_id": "UNIT_NONSTANDARD", "severity": "VIOLATION", "citation": "Rule 13, LMPC 2011",
      "message": "Unit 'gms' is not a permitted symbol; use 'g'.",
      "field": "net_quantity", "bbox": [x,y,w,h], "verified_citation": false }
  ],
  "summary": { "violations": 3, "warnings": 1, "compliant": 5 },
  "timings_ms": { "preprocess": 120, "scale": 60, "ocr": 380, "extract": 1400, "rules": 4 }
}
```

`POST /api/notice` takes an `analysis_id`, returns the PDF stream.

---

## Build order

| Phase | Work | Gate |
|---|---|---|
| 0 | Python install; `requirements.txt`; venv; FastAPI skeleton + `/health` | `/health` returns 200 |
| 1 | Schemas + `/api/analyze` returning a **fixture** response | frontend unblocked |
| 2 | `preprocess.py`, `scale.py` | px_per_mm on a real barcode photo |
| 3 | `ocr.py` + `fuse.py` | word boxes render correctly on canvas |
| 4 | `extract.py` (real Gemini) | structured JSON from a real label |
| 5 | `rules/engine.py` + `catalogue.yaml` | seeded violations fire deterministically |
| 6 | `notice.py` ReportLab Form-I | PDF opens with citations + evidence crops |
| 7 | Frontend screens 1–4 + `EvidenceCanvas` | full click-through |
| 8 | Error paths (blurry, no barcode, Gemini timeout), demo fixtures, timing display | 3-min demo runs twice clean |

Phase 1 before 2 is deliberate: a frozen contract lets the four screens be built against
fixtures while the CV work proceeds.

---

## Verification

- **Unit:** `pytest` on `rules/engine.py` — a table of synthetic declaration sets → expected
  findings. This is where the "100 % determinism" NFR is actually demonstrated, and it must
  assert that identical input yields byte-identical findings across runs.
- **Scale:** photograph one package at three distances; `px_per_mm` × known package width must
  land within ±10 % of a ruler measurement. Records the honest error bar.
- **End-to-end:** `uvicorn app.main:app --reload` + `npm run dev`; upload a real package with a
  deliberate `gms` label; assert red box on net quantity, yellow on small print, PDF cites the
  unit rule.
- **Perf (<3 s NFR):** `timings_ms` is in every response and shown in the UI. Gemini latency
  dominates; if it breaches, the fallback is a smaller image long-edge before upload.
- **Degradation:** blurry photo → manual-inspection prompt, not a crash; no barcode → analysis
  proceeds with `scale: null` and font checks suppressed rather than fabricated.

---

## Assumptions & open items

1. **Citations are unverified.** `verified: false` on every rule until checked against the
   official statute. Please supply the LMPC 2011 and Legal Metrology Act 2009 PDFs, or confirm
   the Rule 6/7/13 and Section 15 references from your spec are correct — a notice citing the
   wrong rule is the one defect that discredits the whole deliverable.
2. **Barcode magnification assumed 100 %.** Stated in the PDF, adjustable in the UI.
3. **E-commerce URL ingestion is thin.** Fetch page → `og:image` + visible text → same
   pipeline. Marketplace HTML is brittle; I will cache two demo listings so the demo cannot
   fail live. Flagging now: this is the least reliable requirement in the spec.
4. **No persistence.** Neither spec asks for a database, so analyses are in-memory with a TTL.
   Supabase is configured and its `public` schema is empty — say the word and audit history
   becomes one table plus one insert.
5. **Determinism scope.** The rule engine is fully deterministic given extracted JSON; Gemini
   extraction is not. The NFR is met at the engine boundary, and I will state it that way
   rather than overclaim.