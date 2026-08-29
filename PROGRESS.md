# MetrologyEye (SIH26034) — Progress & Status Report

> **Automated Legal Metrology Compliance Verification for Packaged Commodity Labels**  
> *Status: Phases 0, 1, 2 & Premortem Steps 1–2 Complete | 119/119 Tests Passing*

---

## 1. Problem Overview & Purpose

Every packaged commodity manufactured, packed, or sold in India must strictly comply with the **Legal Metrology (Packaged Commodities) Rules, 2011 (LMPC 2011)** and the **Legal Metrology Act, 2009**.

### The Core Problem
- **Manual & Laborious:** Enforcement officers currently use manual magnifying rulers, paper checklists, and printed Gazette statute books to inspect retail labels and warehouses.
- **Scale of Non-Compliance:** Millions of SKUs across physical retail and e-commerce listings routinely violate basic labeling rules:
  - Non-standard unit symbols (e.g. printing `500 gms` or `500 gm` instead of the statutory symbol `500 g`).
  - Missing "Inclusive of all taxes" declaration next to MRP.
  - Omitted Country of Origin, incomplete Manufacturer/Packer address, or missing Consumer Care contacts.
  - Illegally tiny font heights below statutory millimetre thresholds.
- **Prosecution Risk:** Hand-written inspection notices with erroneous legal citations or uncalibrated measurements collapse under legal challenge in court.

### The MetrologyEye Solution
MetrologyEye allows an inspector to snap a smartphone photograph of any packaged commodity label. Within **3 seconds**, the system:
1. Preprocesses the image (glare mitigation, deskew, contrast normalization).
2. Derives physical millimetre scale via dual reference markers (EAN-13 barcode + standard ID/calibration card).
3. Reads English and Hindi/Devanagari text polygons via multilingual PaddleOCR.
4. Structurally extracts mandatory declaration fields using Gemini (with full offline fallback).
5. Fuses semantic text to precise optical word bounding boxes (*OCR owns geometry, Gemini owns meaning*).
6. Deterministically evaluates declarations against the LMPC 2011 statutory catalogue and exemption rules.
7. Renders evidence bounding boxes and outputs a ready-to-sign **Form-I Inspection Notice PDF**.

---

## 2. What Has Been Completed (Step-by-Step)

```
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│   Phase 0: Environment  │ ──► │ Phase 1: Skeleton/Config│ ──► │  Phase 2: Schemas & KIs │
│ • Python 3.12.10 setup  │     │ • gemini-2.5-flash def. │     │ • 3-Tier Scale Model    │
│ • venv & requirements   │     │ • .env & .env.example   │     │ • Non-Binary Severities │
│ • PaddleOCR EN+HI cached│     │ • /health endpoint (200)│     │ • Rule-Evidence Contract│
└─────────────────────────┘     └─────────────────────────┘     └─────────────────────────┘
                                                                             │
                                                                             ▼
                                                                ┌─────────────────────────┐
                                                                │  Validation & Testing   │
                                                                │ • pytest: 119/119 pass  │
                                                                │ • 100% test pass rate   │
                                                                └─────────────────────────┘
```

### Phase 0 — Environment & Toolchain Setup
- [x] Installed **Python 3.12.10** (`py -3.12`) to support modern computer vision and PyTorch/PaddlePaddle dependencies.
- [x] Initialized dedicated virtual environment at `MetrologyEyeApp/backend/venv`.
- [x] Cleaned and harmonized [`requirements.txt`](file:///c:/Users/Shree/Desktop/MetrologyEye/MetrologyEyeApp/backend/requirements.txt):
  - Fixed `numpy` constraints (`numpy>=1.26.0,<2.0`) required for `paddlepaddle==2.6.2` and `paddleocr==2.9.1`.
  - Configured `opencv-contrib-python` for native barcode detection without native DLL dependencies.
  - Used `httpx` for direct Gemini REST communication, avoiding gRPC/protobuf conflicts with PaddlePaddle.
  - Added `supabase>=2.10.0`, `reportlab>=4.2.0`, `pydantic>=2.10.0`, `rapidfuzz`, and `pytest`.
- [x] Pre-downloaded and cached PaddleOCR recognition and detection models for both English (`en`) and Devanagari/Hindi (`hi`) into `~/.paddleocr` to guarantee offline operational capability.

### Phase 1 — Configuration & Backend Skeleton
- [x] Updated [`app/config.py`](file:///c:/Users/Shree/Desktop/MetrologyEye/MetrologyEyeApp/backend/app/config.py):
  - Configured default model `GEMINI_MODEL=gemini-2.5-flash` per Plan v2.
  - Added confidence threshold constants: `OCR_FIELD_MIN_CONFIDENCE = 0.60` and `EXTRACT_FIELD_MIN_CONFIDENCE = 0.55`.
  - Added Supabase database configuration (`supabase_url`, `supabase_key`).
  - Added path property for statutory exemptions catalogue (`exemptions.yaml`).
- [x] Configured [`backend/.env.example`](file:///c:/Users/Shree/Desktop/MetrologyEye/MetrologyEyeApp/backend/.env.example) and generated local [`backend/.env`](file:///c:/Users/Shree/Desktop/MetrologyEye/MetrologyEyeApp/backend/.env).
- [x] Verified [`app/main.py`](file:///c:/Users/Shree/Desktop/MetrologyEye/MetrologyEyeApp/backend/app/main.py) with CORS middleware and `/health` capability diagnostic endpoint.

### Phase 2 & Premortem Appendix Steps 1 & 2 — Data Models & Schemas
- [x] **Non-Binary Severity Outcomes** ([`app/schemas/violations.py`](file:///c:/Users/Shree/Desktop/MetrologyEye/MetrologyEyeApp/backend/app/schemas/violations.py)):
  - `VIOLATION`: Confirmed legal defect (red highlight).
  - `WARNING`: Single-source scale estimate or advisory notice (yellow highlight).
  - `MANUAL_REQUIRED`: Ambiguous evidence or missing physical scale reference (grey/hatched highlight).
  - `COMPLIANT`: Verified statutory compliance (green highlight).
  - `POTENTIAL_NON_COMPLIANCE`: Preliminary finding awaiting officer verification.
- [x] **Rule-Evidence Contract**:
  - Enhanced `Finding` with `evidence` metadata (`source_text`, `ocr_confidence`, `match_method`, `bbox`) and `confidence` score.
- [x] **Three-Tier Scale Estimation Schema** ([`app/schemas/analysis.py`](file:///c:/Users/Shree/Desktop/MetrologyEye/MetrologyEyeApp/backend/app/schemas/analysis.py)):
  - Added `BarcodeScale` (`px_per_mm`, `confidence`, `assumed_magnification`, `barcode_value`).
  - Added `ReferenceObjectScale` (`px_per_mm`, `confidence`, `type="id_card"`).
  - Supported `tier: Literal["HIGH", "MEDIUM", "MANUAL_REQUIRED"]`.
- [x] **Statutory Exemption Model**:
  - Added `ExemptionResult` schema (`id`, `matched`, `citation`, `suppressed_rules`).
- [x] **Declaration Traceability**:
  - Enhanced `Declaration` with `ocr_confidence`, `extract_confidence`, and `needs_review: bool`.

---

## 3. Current System Verification & Test Results

```
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Shree\Desktop\MetrologyEye\MetrologyEyeApp\backend
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.14.2
collected 119 items

tests\test_api.py ....................                                   [ 16%]
tests\test_fuse.py .................                                     [ 31%]
tests\test_preprocess.py ...........                                     [ 40%]
tests\test_rules_engine.py ............................................. [ 78%]
......                                                                   [ 83%]
tests\test_scale.py ....................                                 [100%]

============================ 119 passed in 41.42s =============================
```

### Health Check Readout
`GET /health` returns:
```json
{
  "status": "ok",
  "extraction": "mocked",
  "gemini_model": null,
  "ocr": "paddleocr"
}
```
*(When `GEMINI_API_KEY` is provided in `.env`, `extraction` dynamically switches to `gemini` with `gemini-2.5-flash`).*

---

## 4. Current Architecture & Pipeline Flow

```
                      ┌─────────────────────────┐
                      │  Raw Label Photograph   │
                      └───────────┬─────────────┘
                                  │
                   ┌──────────────▼──────────────┐
                   │    1. Preprocessing         │ (CLAHE contrast, deskew, exposure fix)
                   └──────────────┬──────────────┘
                                  │
           ┌──────────────────────┴──────────────────────┐
           │                                             │
  ┌────────▼──────────────┐                    ┌─────────▼──────────────┐
  │  2. Scale Estimation  │                    │     3. Word OCR        │
  │  Barcode + Card       │                    │  PaddleOCR (EN + HI)   │
  │  -> HIGH/MED/MANUAL   │                    │  -> Word Polygons      │
  └────────┬──────────────┘                    └─────────┬──────────────┘
           │                                             │
           │         ┌─────────────────────────────┐     │
           │         │ 4. Semantic Extraction      │     │
           │         │ Gemini API (or Mock Fixture)│     │
           │         └─────────────┬───────────────┘     │
           │                       │                     │
           │                ┌──────▼──────┐              │
           │                │  5. Fusion  │◄─────────────┘
           │                │  (fuse.py)  │ (Matches values to exact word polygons)
           │                └──────┬──────┘
           │                       │
           └──────────────┬────────┘
                          │
                   ┌──────▼──────────────┐
                   │  6. Rules Engine    │ (Exemption pre-filter + catalogue.yaml)
                   │     (engine.py)     │ (Strict statutory validation)
                   └──────┬──────────────┘
                          │
                   ┌──────▼──────────────┐
                   │ 7. Output & Store   │ ──► JSON Response (`POST /api/analyze`)
                   │                     │ ──► Form-I Notice PDF (`POST /api/notice`)
                   └─────────────────────┘
```

---

## 5. Next Planned Milestones

| Phase | Milestone | Scope |
|---|---|---|
| **Phase 3** | Preprocessing & Tiered Scale | Integrate reference-card contour detector, scale tier resolution, and blur/glare capture quality gate. |
| **Phase 4** | Multilingual OCR & Box Merging | Run dual PaddleOCR models (`en` + `hi`) with IoU-based polygon merging. |
| **Phase 5** | Gemini Extraction Integration | Timeout-guarded (12s) structured JSON prompt with one retry and graceful fallback. |
| **Phase 6** | Statutory Exemptions & Catalogue | Load `exemptions.yaml` pre-filter and tier-aware font height evaluations. |
| **Phase 7** | Supabase Persistence | Write `analyses` and `notices` audit tables on every request. |
| **Phase 8** | Form-I Notice PDF Generation | ReportLab layout with "Preliminary Assessment" banner, reviewer block, and evidence crops. |
| **Phase 9** | Frontend Application | Next.js 15 UI with canvas evidence viewer, 3-colour bounding boxes, and camera guide overlay. |
