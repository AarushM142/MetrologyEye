# MetrologyEye (SIH26034) — Implementation Plan v2

## 0. Why this version exists

v1 of this plan (the one already in your repo) was architecturally sound on the
extraction/judgment split, but it was written before the premortem pass. Cross-checking it
against `Legal_Metrology_Compliance_System_Premortem.pdf` surfaced seven gaps that would have
either broken the demo or undermined the "legally defensible" pitch. This version folds all of
those fixes directly into the architecture (not as a to-do list bolted on afterward), and adds
a few more problems the premortem didn't cover. Read §1 and §2 once, then execute §5 top to
bottom — everything you need is in this file, you should not need to re-derive design
decisions mid-build.

---

## 1. What changed from v1, and why

| # | Gap in v1 | Premortem source | Fix now baked into this plan |
|---|---|---|---|
| 1 | Font-height verdicts relied solely on barcode scale, softened only to a WARNING severity. Premortem is more specific: without *any* usable scale reference, don't emit a colour-coded verdict at all. | "No physical scale reference" | Three-tier scale confidence: `HIGH` (barcode **and** reference card both resolve, agree within tolerance) / `MEDIUM` (one source only) / `MANUAL_REQUIRED` (neither resolves — font-height rule is **suppressed**, not emitted as a soft warning). See §3.2. |
| 2 | No exemption handling at all — package-size, agricultural-produce, and industrial/institutional-pack exemptions under LMPC 2011 Rule 26 / Rule 3 were never modeled. A raid notice on an exempt package is the single worst failure mode for a legal tool. | "Exemptions and slab-based rules hardcoded loosely" | New `exemptions.yaml` + an exemption pre-filter step that runs **before** the rule catalogue and can suppress specific rules or the whole analysis with a stated reason. See §3.3. |
| 3 | Verification plan only used clean, self-photographed labels. No informal/messy/multilingual subset, so accuracy numbers would be meaningless for the actual deployment target (small manufacturers). | "Training/testing only on clean, well-lit, major-brand labels" | Split eval fixture set: `fixtures/clean/` vs `fixtures/informal/`, reported separately, never blended into one accuracy number. See §6. |
| 4 | OCR stage assumed English-only implicitly (PaddleOCR default). Indian labels are routinely bilingual (English + Hindi/regional script), and the smallest print (MRP, net qty) is exactly what OCR is worst at. | "Bilingual labels get mis-segmented" | PaddleOCR configured with the multilingual/Devanagari-capable model (`lang='en'` run alongside `lang='hi'`, boxes merged), and a per-field OCR-confidence threshold that routes low-confidence fields to `MANUAL_REQUIRED` instead of a silent auto-verdict. See §3.4. |
| 5 | Notice language didn't go far enough on "not a legal fact." v1 said "Draft" on the PDF; premortem wants an explicit reviewer sign-off field and an audit trail, and v1's own assumption #4 ("No persistence") directly undercuts that. | "Automated NON-COMPLIANT verdict treated as legal fact" | PDF now has a mandatory "Preliminary Assessment — Requires Officer Verification" banner **and** a signature/reviewer-ID block. Persistence is upgraded from "optional Supabase, say the word" to "one `analyses` table, written by default" — see §4 and §7 Assumption 4 (reversed). |
| 6 | Gemini's raw JSON output wasn't logged anywhere distinct from the final verdict, which is exactly the traceability gap the premortem calls out under "unaudited, unversioned rules engine." | "No way to point to which rule fired... hard to defend if challenged" | Every `/api/analyze` call persists three things separately: raw Gemini response, fused OCR+Gemini declarations, and rule engine output. See §3.5 and the `analyses` schema in §4. |
| 7 | No mention that label photos leave Indian government infrastructure to a third-party US commercial LLM (Gemini). Premortem flags this as a real data-sovereignty/procurement concern, not just a nice-to-have disclosure. | "Data-sovereignty and procurement concern" | Explicit disclosure section in the README/pitch deck (§8) plus a config flag (`REDACT_BEFORE_UPLOAD`) that is off by default for the hackathon but documented as the production path (crop to text regions only, strip EXIF/GPS, before the image ever reaches Gemini). | 

### 1.1 Problems beyond the premortem (found independently)

These aren't in either source document — flagging them because they'll bite during the build:

1. **`gemini-1.5-flash` will not work.** As of now (Aug 2026), Gemini 1.0 and 1.5 models are
   fully shut down and return HTTP 404 on any call — this isn't a future risk, it's already
   true. `gemini-2.0-flash` is also retired (shut down June 1, 2026). Do not default to either.
   Current stable, GA, multimodal options are `gemini-2.5-flash` (GA, shuts down Oct 16 2026 —
   safely past any hackathon deadline) or `gemini-3.1-flash-lite` (newer generation, longer
   runway, cheaper). **Default `GEMINI_MODEL=gemini-2.5-flash`, override via `.env` to
   `gemini-3.1-flash-lite` if the key doesn't have 2.5 access.** Keep it env-driven exactly as
   v1 already planned — that part of the design was correct, only the literal default value
   was wrong.
2. **Windows dev environment mismatches.** The repo path is
   `C:\Users\Asus\SIH2026\MetrologyEyeApp` — every backend command in this plan is given in
   both PowerShell/cmd and POSIX form where they differ (venv activation, path separators).
   Don't copy `source venv/bin/activate` verbatim on this machine.
3. **PaddleOCR install weight and first-run behavior.** `paddlepaddle` + `paddleocr` pull large
   wheels and download detection/recognition models on first run (needs internet the first
   time, then works offline). Budget this into Phase 0, not Phase 3, so it isn't a surprise
   mid-build. If the container/VM has no internet at OCR-runtime, pre-download models in Phase
   0 as well.
4. **No confidence-threshold constant was ever defined in v1** even though the schema had a
   `confidence` field on every declaration. A number with no threshold is decoration. §3.4
   fixes this with actual constants.
5. **No timeout/retry policy for the Gemini call.** v1's perf mitigation ("shrink image if
   Gemini is slow") is necessary but not sufficient — an API error or hang with zero timeout
   config will hang the whole `/api/analyze` request. §3.5 adds explicit timeout + one retry +
   fallback to `MANUAL_REQUIRED` extraction status.
6. **Reference-card calibration UI wasn't specified even though it's now load-bearing (fix
   #1).** §3.2 and §5 Phase 7 specify exactly what the UI needs: an on-screen guide rectangle
   for the reference object, and a manual override slider that already existed in v1 for the
   barcode-only case.

---

## 2. Scope statement (unchanged from v1, restated for the agent)

Build a working end-to-end **prototype** in 4–5 days: photograph a packaged-commodity label →
extract mandatory declarations → validate against LMPC 2011 → emit a Form-I-style preliminary
notice PDF. This is a hackathon prototype, not a production field system — §7 marks which
premortem fixes are "do now" vs "documented as the production path, not built this week."

---

## 3. Architecture and key technical decisions

### 3.0 Technology stack (complete)

**Backend**
- Python 3.12
- FastAPI + Uvicorn (ASGI server)
- Pydantic v2 / pydantic-settings (schemas + config)
- OpenCV (`opencv-contrib-python`) — preprocessing + `cv2.barcode.BarcodeDetector`
- PaddleOCR (`paddleocr` + `paddlepaddle`, CPU build) — word-level OCR, English model +
  Devanagari/multilingual model
- `pyzbar` — optional lazy-imported barcode fallback only
- `google-generativeai` (Gemini SDK) — semantic field extraction
- PyYAML — rule catalogue + exemption table loading
- ReportLab — Form-I-style PDF generation
- Supabase Python client (`supabase-py`) — persistence (analyses, audit log)
- pytest — rules engine unit tests, determinism tests
- python-multipart — file upload handling in FastAPI

**Frontend**
- Next.js 15 (App Router), TypeScript, Tailwind CSS
- HTML5 Canvas (native, no charting lib needed) for the evidence viewer
- `fetch` against the FastAPI backend (`lib/api.ts`)

**Infra / dev**
- Supabase (Postgres) — already configured per your session, `public` schema currently empty
- `.env` files for both backend and frontend, never committed
- Windows 11 host, Node 24.19 / npm 12 already present

### 3.1 OCR owns geometry, Gemini owns semantics (unchanged from v1 — this was correct)

Gemini returns field *values* and *labels* only, never geometry and never a compliance
verdict. PaddleOCR returns precise word polygons. `fuse.py` matches Gemini's extracted values
to OCR words by normalized string similarity and takes the bounding box from OCR. This is what
makes the font-height check meaningful, and it's also the direct architectural answer to the
premortem's "LLM becomes an unaudited rules engine" risk (§1.1 fix #7's logging closes the
remaining audit gap).

### 3.2 Scale estimation: tiered confidence, not a single barcode guess (fix #1)

v1 used barcode-only scale with a manual slider. This plan keeps the barcode path but adds a
second, independent source and makes the **absence** of a good scale an explicit outcome
rather than a silently-degraded warning.

**Two independent scale sources:**
1. **EAN-13 barcode** (as in v1): nominal 37.29 mm wide at 100% magnification, legally printed
   from 80%–200%. `scale.py` detects it via `cv2.barcode.BarcodeDetector` and returns
   `{px_per_mm, confidence, assumed_magnification: 1.0}`.
2. **Reference object** (new): the capture UI shows an on-screen guide rectangle and asks the
   inspector to place a standard ID/ATM/debit card (85.60 × 53.98 mm, ISO/IEC 7810 ID-1 — a
   fixed, well-known physical size, unlike the barcode's variable magnification) or an issued
   calibration card with a printed scale bar + QR marker inside it. `scale.py` detects the
   card's long edge in pixels via contour/aspect-ratio detection (or reads the QR marker if a
   calibration card is used) and computes `px_per_mm` directly — no magnification assumption
   needed.

**Confidence tiering (this is the actual fix, not the individual detectors):**

```
HIGH            both sources present, agree within 10%  -> font-height rule runs, verdict is
                                                             a normal colour-coded finding
MEDIUM          exactly one source present               -> font-height rule runs, but every
                                                             such finding is forced to
                                                             severity=WARNING regardless of
                                                             what the raw measurement says,
                                                             and is labeled "single-source
                                                             estimate" in the UI and PDF
MANUAL_REQUIRED neither source present, OR both present
                but disagree by >25%                      -> font-height rule is SUPPRESSED
                                                             entirely (not emitted, not a
                                                             yellow finding) and replaced with
                                                             one line: "Manual verification
                                                             required — no reliable scale
                                                             reference in frame."
```

This directly implements the premortem's instruction: *"Without a reference, output 'Manual
verification required' instead of a false compliant/non-compliant call."* Every non-font-height
rule (units, MRP format, missing declarations, date parsing) is unaffected by scale confidence
— those don't need a physical measurement.

### 3.3 Exemption pre-filter (fix #2 — new, did not exist in v1)

Before the rule catalogue runs, an exemption pre-filter checks the extracted declarations
against `exemptions.yaml`. Seed it with the categories the premortem explicitly names —
package-size thresholds, agricultural produce sold loose/unpackaged-equivalent, and
institutional/industrial packs not intended for retail sale (LMPC 2011 Rule 3 / Rule 26 area —
mark every seeded exemption `verified: false` for the same reason v1 already marks rule
citations unverified; see §7 Assumption 1, now widened to cover exemptions too).

```yaml
# backend/app/services/rules/exemptions.yaml
exemptions:
  - id: EXEMPT_INSTITUTIONAL
    description: "Packages sold to industrial/institutional consumers, not retail"
    citation: "Rule 3(b), LMPC 2011"
    verified: false
    condition: "declared_use == 'institutional' or declared_use == 'industrial'"
    suppresses: ["ALL"]
  - id: EXEMPT_AGRI_PRODUCE
    description: "Agricultural produce sold in bulk / unpackaged-equivalent form"
    citation: "Rule 3(a), LMPC 2011"
    verified: false
    condition: "category == 'agricultural_produce' and net_quantity_over_kg(25)"
    suppresses: ["ALL"]
  - id: EXEMPT_SMALL_PACK_FONT
    description: "Very small packages (<= 10 g/ml) get relaxed font-height minimums"
    citation: "Rule 6, LMPC 2011 (Schedule)"
    verified: false
    condition: "net_quantity_under(10, unit_class='small')"
    suppresses: ["FONT_HEIGHT_MIN"]
```

`engine.py` evaluates exemptions first. A matched exemption either suppresses the whole
analysis (with the reason surfaced prominently, not buried) or suppresses one named rule.
Never let an exemption fire silently — the notice PDF always states which exemption, if any,
was applied and its citation, exactly like a normal violation gets a citation.

### 3.4 OCR: multilingual + confidence-gated (fix #4)

- Run PaddleOCR with both an English model and the Devanagari/multilingual model over the same
  image; merge word boxes by IoU, preferring the higher per-word confidence when both models
  produce a box in roughly the same location.
- **Confidence thresholds (define once, in `config.py`, not scattered in code):**
  - `OCR_FIELD_MIN_CONFIDENCE = 0.60` — below this, the field's box is not trusted for
    font-height measurement; the field still displays but font-height check is skipped for
    that field specifically (independent of the scale tiering in §3.2).
  - `EXTRACT_FIELD_MIN_CONFIDENCE = 0.55` — below this, Gemini's extracted value for a field is
    flagged `needs_review: true` in the API response rather than feeding a hard VIOLATION
    finding (e.g., don't fire `MISSING_DECLARATION` on a field Gemini was unsure it even found
    versus one it's confident is genuinely absent).
- This is the direct fix for the premortem's point that the fields OCR is worst at (MRP, net
  quantity — smallest print) are also the fields that matter most: low confidence on exactly
  those fields now visibly downgrades the verdict instead of silently producing a wrong one.

### 3.5 Gemini call: logged, timed out, and never authoritative (fixes #6, #5)

- `extract.py` calls Gemini with `request_timeout=12s` and exactly one retry with backoff before
  giving up.
- On timeout/error/API-down: the pipeline does **not** crash and does **not** fabricate an
  extraction. It returns `extraction_status: "unavailable"`, and the API response's
  `declarations` array is empty with a top-level `manual_fallback: true` flag. The frontend
  shows "Gemini unavailable — falling back to local demo mode" and can load a pre-baked fixture
  response for the live-demo safety net (this literalizes v1's Verification §"Degradation"
  bullet, which mentioned graceful degradation but not a concrete flag name).
- Every successful call persists three separate JSON blobs against the same `analysis_id`:
  `raw_gemini_response`, `fused_declarations` (post `fuse.py`), and `rule_engine_output`
  (post `engine.py`, including which exemptions were evaluated and their result). This is what
  makes "which rule fired, and was the underlying extraction ever wrong" answerable later —
  directly closing the premortem's "unaudited, unversioned rules engine" gap.

### 3.6 Citations live in `catalogue.yaml`, not in code (unchanged from v1 — correct)

Each rule carries `id, description, citation, severity, check, verified`. Seeded from your two
spec docs (Rules 6, 7, 13; Section 15 of the Legal Metrology Act, 2009), all `verified: false`
until checked against the official statute text. Correcting a citation is a one-line YAML edit.

### 3.7 Barcode detection avoids the pyzbar DLL trap (unchanged from v1 — correct)

Primary detector: OpenCV's `cv2.barcode.BarcodeDetector` (ships in `opencv-contrib-python`, no
native DLL install). `pyzbar` is an optional fallback, imported lazily so a missing `libzbar`
never breaks startup.

### 3.8 Preliminary-assessment framing and persistence (fix #5, reverses v1 Assumption 4)

- Every generated PDF carries a banner: **"PRELIMINARY ASSESSMENT — AI-ASSISTED DRAFT —
  REQUIRES OFFICER VERIFICATION"** plus a signature block (`Reviewed by: ______`,
  `Officer ID: ______`, `Date: ______`) that must be physically/digitally signed before the
  notice has any legal standing. This is stronger than v1's "distinctly labeled as Draft."
- Persistence is no longer optional. Since Supabase is already configured and its `public`
  schema is empty (v1 correctly noted this), write two tables from day one:
  - `analyses` — one row per `/api/analyze` call: image reference, `raw_gemini_response`,
    `fused_declarations`, `rule_engine_output`, `scale_confidence_tier`, timestamps.
  - `notices` — one row per generated PDF: `analysis_id`, PDF storage path, `reviewer_id`
    (nullable until signed), `reviewed_at` (nullable).
  This is a small addition (two tables, a handful of inserts) relative to the premortem's
  ask for an *immutable audit trail*, and it's cheap to do now versus retrofitting after the
  judging round.

---

## 4. Updated API contract

`POST /api/analyze` (multipart image **or** `{"url": "..."}`, plus optional
`reference_object_present: bool` from the capture UI) →

```json
{
  "analysis_id": "uuid",
  "image": { "width": 1600, "height": 1200, "preview_url": "/api/image/uuid" },
  "extraction_status": "ok",
  "scale": {
    "barcode": { "px_per_mm": 7.42, "confidence": 0.81, "assumed_magnification": 1.0 },
    "reference_object": { "px_per_mm": 7.55, "confidence": 0.93, "type": "id_card" },
    "tier": "HIGH"
  },
  "exemptions_evaluated": [
    { "id": "EXEMPT_SMALL_PACK_FONT", "matched": false, "citation": "Rule 6, LMPC 2011 (Schedule)" }
  ],
  "declarations": [
    {
      "field": "net_quantity", "value": "500 gms", "bbox": [10,20,80,18],
      "ocr_confidence": 0.88, "extract_confidence": 0.91, "needs_review": false
    }
  ],
  "violations": [
    {
      "rule_id": "UNIT_NONSTANDARD", "severity": "VIOLATION", "citation": "Rule 13, LMPC 2011",
      "message": "Unit 'gms' is not a permitted symbol; use 'g'.",
      "field": "net_quantity", "bbox": [10,20,80,18], "verified_citation": false
    },
    {
      "rule_id": "FONT_HEIGHT_MIN", "severity": "MANUAL_REQUIRED", "citation": "Rule 6, LMPC 2011",
      "message": "No reliable scale reference in frame — manual verification required.",
      "field": "net_quantity", "bbox": null, "verified_citation": false
    }
  ],
  "summary": { "violations": 3, "warnings": 1, "manual_required": 1, "compliant": 5 },
  "timings_ms": { "preprocess": 120, "scale": 60, "ocr": 380, "extract": 1400, "rules": 4 }
}
```

`POST /api/notice` takes an `analysis_id`, returns the PDF stream and writes the `notices` row.
`PATCH /api/notice/{id}/review` — new endpoint — records `reviewer_id` + timestamp (stub auth
for the hackathon: a free-text officer ID field is enough, don't build real auth this week).

---

## 5. Build order (execute top to bottom)

### Phase 0 — Environment (blocking, do this first, budget real time for it)

```powershell
winget install -e --id Python.Python.3.12
```
Open a **new** terminal, confirm `python --version` reports 3.12.x. Node 24.19 / npm 12 already
present — confirm with `node --version` / `npm --version`.

```powershell
cd C:\Users\Asus\SIH2026\MetrologyEyeApp
python -m venv backend\venv
backend\venv\Scripts\activate
pip install -r backend\requirements.txt
```

`requirements.txt` (create this file first):
```
fastapi
uvicorn[standard]
pydantic>=2
pydantic-settings
python-multipart
opencv-contrib-python
paddleocr
paddlepaddle
pyzbar
google-generativeai
pyyaml
reportlab
supabase
pytest
```

Immediately after install, run a throwaway script that imports `paddleocr` and instantiates
`PaddleOCR(lang='en')` and `PaddleOCR(lang='devanagari')` once, so the model downloads happen
now (needs internet) rather than surprising you mid-Phase-3. If this environment has no
internet access at all, download the PaddleOCR model files on a machine that does and copy them
into the expected `~/.paddleocr` cache directory before continuing.

**Gate:** `python --version` → 3.12.x; PaddleOCR imports without error and both language models
are cached locally.

### Phase 1 — Contract-first backend skeleton

Create `backend/app/main.py` (FastAPI app, CORS via `CORS_ORIGIN` env var, `/health` route),
`backend/app/config.py` (pydantic-settings reading `GEMINI_API_KEY`, `GEMINI_MODEL` — default
`gemini-2.5-flash` per §1.1 fix #1 — `CORS_ORIGIN`, `OCR_FIELD_MIN_CONFIDENCE=0.60`,
`EXTRACT_FIELD_MIN_CONFIDENCE=0.55`, Supabase URL/key).

Create `backend/.env.example`:
```
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
CORS_ORIGIN=http://localhost:3000
SUPABASE_URL=
SUPABASE_KEY=
OCR_FIELD_MIN_CONFIDENCE=0.60
EXTRACT_FIELD_MIN_CONFIDENCE=0.55
```

Wire `POST /api/analyze` to return a **fixture** response matching §4's contract exactly
(hardcode a plausible JSON blob for now) so the frontend team is unblocked immediately.

**Gate:** `uvicorn app.main:app --reload` → `/health` returns 200; `/api/analyze` returns the
fixture JSON matching the §4 schema field-for-field.

### Phase 2 — Schemas

`backend/app/schemas/analysis.py`: `AnalyzeResponse`, `Declaration` (with `ocr_confidence`,
`extract_confidence`, `needs_review`), `BBox`, `ScaleInfo` (with `barcode`, `reference_object`,
`tier: Literal["HIGH","MEDIUM","MANUAL_REQUIRED"]`).
`backend/app/schemas/violations.py`: `Violation`, `Severity = Literal["VIOLATION","WARNING","MANUAL_REQUIRED"]`,
`RuleCitation`, `ExemptionResult`.

**Gate:** Pydantic models validate the exact fixture JSON from Phase 1 without error.

### Phase 3 — Preprocessing + tiered scale

`backend/app/services/preprocess.py`: deskew, glare reduction, CLAHE, perspective correction.
**Always keep the original unprocessed image alongside the processed one** — store both, and
if later stages fail confidence thresholds, the human reviewer (and a future retry) can fall
back to the original rather than trusting one fixed pipeline tuned on your own demo photos
(this is the premortem's Stage-2 fix — one static pipeline destroys signal on glossy-foil or
curved labels it wasn't tuned on).

`backend/app/services/scale.py`: implement both sources from §3.2 — `detect_barcode_scale()`
and `detect_reference_object_scale()` — plus `resolve_scale_tier(barcode, reference)` returning
the `HIGH`/`MEDIUM`/`MANUAL_REQUIRED` tier per the rules in §3.2. Also add a basic capture
quality gate here: blur score (variance of Laplacian) and glare score (overexposed pixel
fraction); if either fails a threshold, return `quality_gate: "retake_recommended"` in the
response rather than silently proceeding through the rest of the pipeline (premortem Stage-1
fix).

**Gate:** photograph one package at three distances, with and without a reference card in
frame; `px_per_mm` from the reference-card path lands within ±10% of a ruler measurement;
confirm all three tiers (`HIGH`/`MEDIUM`/`MANUAL_REQUIRED`) are reachable by manipulating which
sources are present.

### Phase 4 — OCR + fuse

`backend/app/services/ocr.py`: run both PaddleOCR language models, merge boxes by IoU per §3.4.
`backend/app/services/fuse.py`: match Gemini field values to OCR words by normalized string
similarity, take the geometry from OCR, attach `ocr_confidence` per field.

**Gate:** word boxes render correctly on the frontend canvas for both a pure-English label and
a bilingual (English + Hindi) label from your informal-label fixture set (see §6).

### Phase 5 — Gemini extraction (real API, timeout-guarded)

`backend/app/services/extract.py`: call Gemini with the model from config, `request_timeout=12`,
one retry, structured-JSON prompt (field values + labels only, explicitly instruct it **not**
to judge compliance). On failure/timeout, return `extraction_status: "unavailable"` and set
`manual_fallback: true` — never crash the request, never fabricate values.

**Gate:** structured JSON comes back from a real photographed label; killing network access
mid-call correctly falls through to `manual_fallback` instead of hanging or 500ing.

### Phase 6 — Exemptions + rules engine

`backend/app/services/rules/exemptions.yaml` and `engine.py`'s exemption pre-filter (§3.3),
then `catalogue.yaml` and the rule evaluator (§3.6). Order matters: exemptions run first and
can suppress specific rules (like `FONT_HEIGHT_MIN` for tiny packs) or the whole analysis
(institutional/agricultural). The font-height rule itself must read `scale.tier` and: run
normally if `HIGH`, force `severity=WARNING` if `MEDIUM`, suppress entirely and emit the
`MANUAL_REQUIRED` line if neither source resolved (§3.2) — implement this check inside
`engine.py`, not scattered across `scale.py`.

**Gate:** `pytest` on `engine.py` — a table of synthetic declaration + scale-tier + exemption
combinations → expected findings, asserting byte-identical output across repeated runs on
identical input (this is where "100% determinism" is actually demonstrated, exactly as v1
specified — that part didn't need to change).

### Phase 7 — Persistence

Create the two Supabase tables from §3.8 (`analyses`, `notices`). Wire `/api/analyze` to insert
into `analyses` (raw Gemini response, fused declarations, rule engine output, scale tier,
timestamps) on every call, and `/api/notice` to insert into `notices` on PDF generation. Add
`PATCH /api/notice/{id}/review` to record a reviewer ID.

**Gate:** two consecutive `/api/analyze` calls on the same image produce two distinct
`analyses` rows with identical `rule_engine_output` (determinism check at the persistence
layer, not just in pytest).

### Phase 8 — Notice PDF

`backend/app/services/notice.py`: ReportLab Form-I-style document with cropped evidence images,
citations (marked `[unverified]` where `verified: false`), the exemption result if any fired,
and the mandatory "PRELIMINARY ASSESSMENT — REQUIRES OFFICER VERIFICATION" banner + signature
block from §3.8.

**Gate:** PDF opens, shows correct citations, shows the banner and signature block, shows
`MANUAL_REQUIRED` items distinctly from `VIOLATION`/`WARNING` (e.g., grey vs red vs yellow).

### Phase 9 — Frontend

Next.js screens exactly per v1's structure (`page.tsx` upload/capture, `analyze/page.tsx`
staged progress, `results/page.tsx` canvas evidence viewer, `notice-preview/page.tsx`
embed+download), plus:
- Capture screen: on-screen guide rectangle for the reference card (§3.2), with copy explaining
  why ("place an ID/ATM card next to the label for accurate font measurement").
- Results screen: `EvidenceCanvas.tsx` colour-codes `VIOLATION` (red) / `WARNING` (yellow) /
  `MANUAL_REQUIRED` (grey/hatched) distinctly — this third state didn't exist in v1's UI.
- Manual calibration slider (from v1) still present as an override for the `MEDIUM` tier case.

**Gate:** full click-through, upload → analyze → results with all three severity colours
visible → notice PDF preview + download.

### Phase 10 — Error paths, demo fixtures, timing display

- Blurry/glared photo → retake prompt (Phase 3's quality gate), not a crash.
- No barcode and no reference object → `MANUAL_REQUIRED` tier flows through correctly end to
  end, including in the PDF.
- Gemini down → `manual_fallback` fixture demo mode (cache two pre-baked responses + two
  cached e-commerce listing pages, exactly as v1 planned for the URL-ingestion path).
- `timings_ms` visible in the UI; if Gemini latency breaches the <3s NFR, fall back to a
  smaller image long-edge before upload (unchanged from v1).

**Gate:** 3-minute demo script runs twice clean, including one deliberate `MANUAL_REQUIRED`
run (no reference object in frame) and one deliberate exemption-fired run (institutional pack).

---

## 6. Verification plan (updated)

- **Unit:** `pytest` on `rules/engine.py` — synthetic declaration/scale-tier/exemption
  combinations → expected findings; assert byte-identical determinism across runs.
- **Scale:** photograph one package at three distances, with/without reference card; barcode
  path and reference-card path each checked independently against a ruler measurement (±10%);
  confirm the `HIGH`/`MEDIUM`/`MANUAL_REQUIRED` tiering logic in isolation with mocked inputs.
- **Eval fixture set (new — closes the premortem's "no labeled ground truth" and "clean-only
  testing" gaps together):** build `fixtures/clean/` (5–8 well-lit, major-brand labels, hand
  labeled with expected declarations + expected violations) and `fixtures/informal/` (5–8
  photographed under harsher conditions — poor lighting, curved surface, bilingual or
  regional-script text, small/local-manufacturer packaging). Run both subsets through the full
  pipeline and report accuracy **separately per subset**, never as one blended number. Re-run
  this whenever `preprocess.py`, `ocr.py`, or the Gemini prompt changes.
- **End-to-end:** `uvicorn app.main:app --reload` + `npm run dev`; upload a real package with a
  deliberate `gms` label; assert red box on net quantity, correct tier-based colour on font
  size, PDF cites the unit rule and shows `[unverified]` correctly.
- **Perf (<3s NFR):** `timings_ms` in every response, shown in UI; Gemini latency dominates —
  fallback is a smaller image long-edge before upload.
- **Degradation:** blurry photo → manual-inspection prompt, not a crash. No barcode and no
  reference object → `MANUAL_REQUIRED`, never a fabricated compliant/non-compliant call. Gemini
  timeout/down → `manual_fallback` demo mode, not a hang or 500.

---

## 7. Assumptions & open items (updated)

1. **Citations and exemptions are unverified.** `verified: false` on every rule *and every
   exemption* until checked against the official statute. Please supply the LMPC 2011 and
   Legal Metrology Act 2009 PDFs, or confirm the Rule 3/6/7/13/26 and Section 15 references are
   correct — a notice (or a suppressed analysis) citing the wrong provision is the one defect
   that discredits the whole deliverable.
2. **Reference-object magnification is not an issue for the ID-card path** (fixed physical
   size), but the barcode path still assumes 100% magnification unless overridden — stated in
   the PDF, adjustable via the UI slider, exactly as v1 specified.
3. **E-commerce URL ingestion is thin,** unchanged from v1: fetch page → `og:image` + visible
   text → same pipeline; two demo listings cached so the live demo cannot fail on brittle
   marketplace HTML.
4. **Persistence is now default-on, not optional** (reversed from v1). Two tables
   (`analyses`, `notices`) are written on every call from Phase 7 onward — this is the minimum
   audit trail the premortem asks for, and it's cheap enough to build now rather than retrofit.
5. **Determinism scope, unchanged from v1:** the rule engine (including the exemption
   pre-filter) is fully deterministic given extracted JSON and a resolved scale tier; Gemini
   extraction itself is not. State it that way in the pitch — don't overclaim end-to-end
   determinism.
6. **Data leaves government infrastructure to Gemini (third-party commercial cloud).** Disclose
   this explicitly in the pitch/README (§1.1 fix #7). `REDACT_BEFORE_UPLOAD` (crop to text
   regions, strip EXIF/GPS before the API call) is documented here as the production-hardening
   path but is **not** built this week — out of scope for a 4–5 day prototype, but do not let
   the pitch imply it's already solved.
7. **Offline capture queue and on-device pre-checks (premortem's field-connectivity risk) are
   explicitly out of scope for this prototype.** The Phase 3 blur/glare quality gate is the one
   piece of that risk category worth building now because it's cheap and demo-relevant; the
   full offline-sync architecture is a production concern, not a hackathon-week concern — say
   this plainly if asked, rather than pretending the prototype is field-ready.

---

## 8. One-paragraph disclosure for the pitch deck / README

*"MetrologyEye sends label photos to Google's Gemini API for text extraction. This is a
data-sovereignty consideration for a government enforcement tool and is flagged here
explicitly, not glossed over: a production deployment would need either a data-processing
agreement, a self-hosted/open-weight extraction model, or on-device redaction of non-text
regions before any image leaves departmental infrastructure. The prototype does not implement
this; it is documented as the next hardening step."*

Appendix A — Backend-only MVP: get something running TODAY

Everything above is the real plan — build toward it over the 4–5 days. But if the goal for today is just "backend responds with a real, non-fake violation for a real photo," most of §5's phases are more than you need right now. This appendix is a stripped-down subset: it skips the frontend entirely, skips persistence, skips the exemption engine, skips multilingual OCR, skips the reference-card second scale source, and skips PDF polish. Nothing here contradicts the full plan — it's a subset of it, so nothing you build today gets thrown away; Phases 6–10 above just add onto this later.

What's deliberately deferred (not part of today's scope):

Frontend (Next.js) — test everything today via curl / Swagger UI (/docs) instead.
Supabase persistence (analyses, notices tables) — today, findings just come back in the HTTP response; nothing is saved.
Exemption pre-filter (exemptions.yaml) — skip it; no exemption logic fires today.
Reference-object (ID-card) scale source and tiering — today, scale is barcode-only, and if the barcode isn't found, font-height checks are just skipped (log a note, don't fabricate a tier system yet).
Multilingual OCR — English PaddleOCR model only today.
Officer sign-off / review endpoint — skip PATCH /api/notice/{id}/review.
A.1 — Environment (15–30 min)
powershell
winget install -e --id Python.Python.3.12

New terminal, confirm python --version → 3.12.x.

powershell
cd C:\Users\Asus\SIH2026\MetrologyEyeApp
python -m venv backend\venv
backend\venv\Scripts\activate

Create backend/requirements.txt with just what today needs:

fastapi
uvicorn[standard]
pydantic>=2
pydantic-settings
python-multipart
opencv-contrib-python
paddleocr
paddlepaddle
google-generativeai
pyyaml
reportlab
pytest
powershell
pip install -r backend\requirements.txt

Sanity-check PaddleOCR downloads its model now, not later:

powershell
python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='en')"

Gate: import succeeds, English model cached locally.

A.2 — Minimal skeleton and config (15 min)

backend/.env:

GEMINI_API_KEY=<your key>
GEMINI_MODEL=gemini-2.5-flash
CORS_ORIGIN=*

backend/app/config.py — pydantic-settings reading the three vars above, plus two constants directly in code (no need for full env-driven thresholds today):

python
OCR_FIELD_MIN_CONFIDENCE = 0.60
EXTRACT_FIELD_MIN_CONFIDENCE = 0.55

backend/app/main.py — FastAPI app, permissive CORS, GET /health returning {"status":"ok"}.

Gate: uvicorn app.main:app --reload starts; GET /health returns 200.

A.3 — Schemas (10–15 min)

Just enough of §4's contract to be useful — you can add the rest (scale tiers, exemptions, needs_review) later without breaking this:

backend/app/schemas/analysis.py:

BBox (x, y, w, h)
Declaration (field, value, bbox: Optional[BBox], ocr_confidence, extract_confidence)
Violation (rule_id, severity: Literal["VIOLATION","WARNING"], citation, message, field, bbox: Optional[BBox], verified_citation: bool = False)
AnalyzeResponse (analysis_id, image, scale: Optional[dict], declarations: list[Declaration], violations: list[Violation], summary: dict, timings_ms: dict)

Gate: models import cleanly with no circular imports.

A.4 — Barcode-only scale (30–45 min)

backend/app/services/scale.py:

python
def detect_barcode_scale(image) -> dict | None:
    # cv2.barcode.BarcodeDetector, EAN-13, nominal width 37.29mm @ 100%
    # returns {"px_per_mm": ..., "confidence": ..., "assumed_magnification": 1.0}
    # returns None if no barcode found — caller must handle this, not crash

No tiering logic yet — just scale = detect_barcode_scale(img); if None, font-height rule is skipped for this run (a MANUAL_REQUIRED style behavior, just not formalized as a tier system yet).

Gate: run against one real barcode photo, px_per_mm looks sane (cross-check by hand: barcode's pixel width ÷ 37.29mm).

A.5 — OCR (English only) (30–45 min)

backend/app/services/ocr.py — call PaddleOCR(lang='en') once at module load (don't re-instantiate per request, it's slow), return word-level boxes + text + confidence.

Gate: run against a real label photo, print the boxes, confirm net-quantity/MRP text is being picked up with reasonable confidence.

A.6 — Gemini extraction, real API, with a timeout (30–45 min)

backend/app/services/extract.py:

Prompt Gemini for structured JSON only: field name → value (net_quantity, mrp, mfr_address, mfg_date, consumer_care, country_of_origin). Explicitly instruct it not to judge compliance — extraction only.
request_timeout=12, no retry needed today (add the retry when you get to full Phase 5) — but do wrap in try/except so a timeout returns extraction_status: "unavailable" instead of crashing the request.

Gate: real photo → real Gemini call → structured JSON with the six fields above (or fewer, if genuinely absent from the label).

A.7 — Fuse (15–20 min)

backend/app/services/fuse.py — for each Gemini field value, find the closest-matching OCR word/phrase by normalized string similarity, attach that OCR box + ocr_confidence to the declaration. If no match found above a similarity threshold, leave bbox: None rather than guessing.

Gate: declarations in the API response carry real bounding boxes, not null, for fields that are actually visible on the label.

A.8 — Minimal rules engine (45–60 min)

backend/app/services/rules/catalogue.yaml — seed with just the highest-value rules so you have something to demo, skip the rest for today:

yaml
rules:
  - id: UNIT_NONSTANDARD
    check: "unit in ['gms','gm','ltr','lt']"
    citation: "Rule 13, LMPC 2011"
    severity: VIOLATION
    verified: false
  - id: MRP_MISSING_TAX_PHRASE
    check: "mrp_present and 'inclusive of all taxes' not in mrp_text.lower()"
    citation: "Rule 6, LMPC 2011"
    severity: VIOLATION
    verified: false
  - id: MISSING_DECLARATION
    check: "field not in declarations"
    citation: "Rule 6, LMPC 2011"
    severity: VIOLATION
    verified: false
  - id: FONT_HEIGHT_MIN
    check: "scale is not None and ocr_box_height_mm < statutory_min_mm"
    citation: "Rule 6, LMPC 2011 (Schedule)"
    severity: WARNING
    verified: false
    # today: if scale is None, this rule is simply not evaluated — no exemption
    # engine, no tier system yet, just "skip if we can't measure"

backend/app/services/rules/engine.py — plain Python evaluator, no exemption pre-filter, no tiering: loop the catalogue, run each check, append a Violation on match. Keep it pure and deterministic (same input → same output) even at this minimal scope — that property is cheap to preserve now and expensive to retrofit later.

Gate: pytest — feed 3–4 synthetic declaration sets, assert expected violations fire and re-running the same input twice gives byte-identical output.

A.9 — Wire it into /api/analyze (20–30 min)

backend/app/api/routes.py — POST /api/analyze accepting multipart image upload: preprocess (can be a no-op passthrough today, real deskew/CLAHE is Phase 3 of the full plan) → detect_barcode_scale → ocr → extract → fuse → engine.evaluate → assemble AnalyzeResponse → return JSON. No database write.

Gate: curl -F "file=@label.jpg" http://localhost:8000/api/analyze returns a full, schema-valid JSON response with real violations, in well under 5 seconds, using the FastAPI auto-docs at /docs to test interactively if that's easier than curl.

A.10 — (Optional, if time remains today) bare-bones PDF

backend/app/services/notice.py — minimal ReportLab doc: list violations + citations + [unverified] tags + one plain-text line "PRELIMINARY — AI-ASSISTED DRAFT, NOT A LEGAL DETERMINATION." Skip the signature block and cropped-evidence images for today; add those when you reach full Phase 8.

Gate: POST /api/notice with a valid analysis_id-shaped payload returns a PDF that opens and lists the same violations /api/analyze returned.

What "done for today" looks like

A running uvicorn process where a real photographed label, posted to /api/analyze via curl or /docs, returns real (not fixture) violations with real citations and real bounding boxes — and, if you got to A.10, a downloadable PDF summarizing them. No frontend, no database, no exemptions, no multilingual OCR, no reference-card calibration. Everything skipped here is still in the main plan above and slots in without rework once today's core loop works.