# Perform a Premortem on This and Give Solutions for Each Issue You Found

This plan is thoughtfully scoped, but it can still fail by attempting too many fragile integrations — computer vision, Gemini extraction, legal reasoning, PDF generation, and a polished UI — inside 4–5 days. The highest-risk failure mode is producing an impressive demo that is not reliable enough to defend when the judges test a different package image. [1]

## Premortem Assumptions

Assume the final demo fails or scores poorly. The most likely reasons are:

- The app works only on prepared images, not ordinary package photos.
- Legal findings are challenged because citations or rule logic are inaccurate.
- Backend dependencies and model/API issues consume most of the build window.
- The "font-size measurement" feature produces visibly questionable results.
- The team runs out of time before integrating and rehearsing the end-to-end path.

## Risks and Fixes

### 1. Python/PaddleOCR/OpenCV setup blocks the project

- **Early warning sign:** Phase 0 takes more than 2–3 hours; import errors, model-download failures, or Windows DLL errors appear.
- **Why it matters:** Every later backend feature depends on this, and the repository is greenfield.
- **Practical solution:** Timebox setup to 90 minutes. Make a minimal `/health` endpoint and one local OCR smoke-test image the only Phase-0 deliverable. If PaddleOCR is not running by the deadline, switch to a pre-tested fallback such as EasyOCR/Tesseract only if already installable, or use Gemini extraction without geometry and degrade the evidence viewer gracefully.

### 2. Gemini model/key/API availability fails at demo time

- **Early warning sign:** `GEMINI_API_KEY` is missing, the configured model returns 404/403, requests are slow, or JSON output is malformed.
- **Why it matters:** Gemini is responsible for identifying declaration semantics, so failure makes the rules engine mostly blind.
- **Practical solution:** Validate the real key and chosen model on Day 1 — not Phase 4. Build a `FixtureExtractor` behind the same interface as Gemini and preserve 3–5 local analysis fixtures. Add strict JSON-schema validation, one retry, timeout handling, and a clear UI state: "AI extraction unavailable; showing demo fixture/manual review." The plan already makes model selection configurable; turn that into a tested fallback path.

### 3. OCR-to-Gemini fusion cannot locate the declared field

- **Early warning sign:** Extracted value is correct but no OCR box matches it; boxes highlight only one word of a multi-line address or the wrong repeated price.
- **Why it matters:** The evidence canvas and font-size check depend on geometry being trustworthy.
- **Practical solution:** Do not fuse on value similarity alone. Match using a ranked strategy: exact normalized string → token overlap → nearby label/value pair → OCR line grouping. Store `match_method`, `match_score`, and `geometry_confidence`. If confidence is below a threshold, show the declaration without a precise box and suppress all geometry-dependent conclusions.

### 4. Font-height findings are inaccurate or easily disproved

- **Early warning sign:** Different photo distances produce materially different measured heights; manual slider changes flip results.
- **Why it matters:** The plan correctly recognizes that EAN-13 dimensions are not a reliable absolute scale because legal barcode magnification can vary from roughly 80% to 200%.
- **Practical solution:** Treat this feature as "estimated visual-size review," not a statutory measurement. Disable it by default unless one of these calibration methods exists: a user-entered known package dimension, a printed ruler/reference card, or a manually confirmed barcode magnification. In the PDF, call it "manual verification required," never "letter-height violation." Also add an explicit "scale unavailable / unverified" state rather than a weak yellow result.

### 5. Barcode detection fails on real packaging

- **Early warning sign:** No EAN-13 is detected on glossy, curved, cropped, or low-light photos.
- **Why it matters:** The app then loses its measurement anchor and may look broken.
- **Practical solution:** Make no-barcode handling a primary — not exceptional — flow. The plan says analysis continues with `scale: null` and suppresses font checks; implement and demo that path deliberately. Add a guided capture overlay asking for a flat, well-lit photo and "include barcode if available," but never require it to evaluate text declarations.

### 6. Image preprocessing harms OCR instead of helping

- **Early warning sign:** CLAHE/glare removal makes small text noisy, colours artificial, or barcode unreadable.
- **Why it matters:** Over-processing can create false negatives and wastes debugging time.
- **Practical solution:** Preserve the original image and create preprocessing as an A/B choice. Run OCR on original and processed versions, then select the result with higher aggregate OCR confidence. For the hackathon, implement only EXIF orientation correction, resize, light denoise, and optional perspective correction; defer glare removal and aggressive deskew unless test images prove they help.

### 7. Legal citations are wrong, incomplete, or not suited to the claimed offence

- **Early warning sign:** A judge asks "which exact provision mandates this?" and the app shows `verified: false` or an unsupported citation.
- **Why it matters:** This directly undermines the core claim: automated legal-metrology compliance checking.
- **Practical solution:** This is the most serious credibility risk in the plan. Freeze the rule catalogue only after checking the primary text or authoritative government PDFs. Do not surface unverified provisions in a formal-looking Form-I notice. Until verified, phrase output as "potential non-compliance for inspector review," label citations as "reference pending verification," or exclude the rule from the generated notice. The plan itself identifies all citations as unverified, including Rules 6, 7, 13 and Section 15.

### 8. Rule logic is overly simplistic and causes obvious false positives

- **Early warning sign:** "MRP" formatting is rejected even though the declaration is valid in context; country-of-origin or manufacturer text is present but formatted differently.
- **Why it matters:** Deterministic code does not guarantee legally correct conclusions.
- **Practical solution:** Model each rule with three outcomes: `PASS`, `POTENTIAL_ISSUE`, and `INSUFFICIENT_EVIDENCE`. Reserve red "violation" only for high-confidence, unambiguous cases such as explicit grams where the underlying rule has been verified. Put ambiguous presentation and extraction failures in yellow review cards. Add at least 10 synthetic tests per rule, including valid variants, OCR-corrupted text, absent text, and borderline cases.

### 9. The Form-I PDF overclaims legal authority

- **Early warning sign:** The PDF looks like an official government notice but is generated from uncertain OCR, unverified citations, and no inspector identity or workflow.
- **Why it matters:** It can create legal and ethical concern during evaluation, even if technically impressive.
- **Practical solution:** Rename the output to "Draft Form-I Inspection Notice / Demo Output" and put a persistent disclaimer on every page: "AI-assisted preliminary analysis; requires authorised inspector review." Include source image crop, extracted text, confidence, calibration status, and rule-version ID. Only enable the final "notice" layout for verified rules; otherwise produce a "Preliminary Inspection Report."

### 10. URL ingestion breaks or creates security problems

- **Early warning sign:** Marketplace links fail, take too long, return bot-block pages, or users can make the backend fetch internal network URLs.
- **Why it matters:** This feature is explicitly described as the least reliable part of the requirements.
- **Practical solution:** Cut live URL ingestion from the critical path. Support it only as a "demo mode" with two pre-cached URLs/images. If retaining fetch: allow only http/https, reject private/local IP ranges after DNS resolution, cap redirects and response sizes, set a short timeout, and use a server-side allowlist for demo marketplaces. Make upload/camera capture the primary path.

### 11. API contract changes during integration

- **Early warning sign:** Frontend uses fields that backend renames, PDF route differs from implementation, or fixture and real responses diverge.
- **Why it matters:** Parallel work becomes rework late in the build.
- **Practical solution:** Create versioned Pydantic response models and generate a canonical fixture JSON from them. Add a backend contract test asserting the real endpoint validates against the same schema. The plan's "fixture response first" approach is correct; make the fixture immutable after Day 1 except through a deliberate version bump.

### 12. In-memory analysis storage breaks the PDF or refresh flow

- **Early warning sign:** Results disappear after reload, server restart, multiple requests, or when `/api/notice/{id}` runs after TTL.
- **Why it matters:** A judge may upload, navigate back, refresh, or take longer than the TTL to inspect findings.
- **Practical solution:** Store each analysis as a self-contained artifact directory: original image, normalized OCR, extracted declarations, findings JSON, and generated PDF. For the prototype, local disk storage is simpler and more reliable than in-memory TTL. If Supabase is available, use it only after the core flow works; persistence is not worth endangering the demo.

### 13. The 3-second performance target is missed

- **Early warning sign:** Gemini calls dominate total time, OCR models cold-start, PDFs block the request.
- **Why it matters:** A staged progress UI does not hide a 10–20 second wait when judges are watching.
- **Practical solution:** Measure cold and warm timings from Day 1. Resize uploaded images to a fixed long edge before OCR/VLM, cache loaded OCR models at startup, generate the report only after results are shown or on demand, and use one Gemini request per image. Set a demo acceptance target of under 8 seconds cold and under 4 seconds warm; the stated <3 s target is not realistic until empirically proven.

### 14. The demo depends on a perfect network or live third-party site

- **Early warning sign:** Wi-Fi is weak, Gemini is slow, the URL page is blocked, or package-image loading fails.
- **Why it matters:** Hackathon judging environments are hostile to cloud-only demos.
- **Practical solution:** Prepare an offline demo route with locally stored source images, OCR output, Gemini JSON, analysis responses, and PDFs. Add a visible "Live analysis / Replay demo" toggle only if needed, but ensure the default polished walkthrough is reproducible without internet.

### 15. The UI is polished but conceals uncertainty

- **Early warning sign:** The canvas draws sharp red boxes even where confidence is weak; users cannot distinguish OCR evidence from AI inference.
- **Why it matters:** Overconfidence is particularly damaging for a legal-tech product.
- **Practical solution:** Make uncertainty a first-class UI element: confidence badges, dashed boxes for inferred regions, muted "not located" state, and a per-finding evidence drawer with OCR text, AI interpretation, rule logic, and calibration status. This turns limitations into a mature product story rather than a flaw.

### 16. There is no time for end-to-end rehearsal

- **Early warning sign:** Individual modules work, but camera upload, API, canvas, PDF download, and navigation fail together.
- **Why it matters:** Integration failures are the most common last-day failure in greenfield hackathon projects.
- **Practical solution:** Set a daily vertical-slice gate: by the end of Day 1, upload → fixture findings → results UI; Day 2, real OCR; Day 3, Gemini plus two deterministic rules; Day 4, PDF; Day 5, only fixes, tests, and rehearsals. No new features after the first clean full run.

## Scope Cuts to Protect Success

For a 4–5 day build, I would define the must-demo path as:

1. Upload one clear product-label image.
2. Extract a constrained set of declarations: net quantity, MRP, tax-inclusive statement, manufacturing date, manufacturer identity/address, and consumer-care details.
3. Reliably flag only 3–4 rules with verified legal references.
4. Show evidence, confidence, and a clear "manual review" state.
5. Generate a preliminary report PDF with image crops and a disclaimer.

Defer or reduce these until the core path passes repeatedly:

- Live e-commerce URL scraping.
- Aggressive glare removal and sophisticated perspective correction.
- Full Form-I legal-notice positioning.
- Automated letter-height findings based solely on barcode calibration.
- Database/audit-history work.
- Broad rule coverage beyond tested, verified checks.

## Recommended Implementation Changes

### 1. Replace binary findings

Use this result model:

```ts
type FindingStatus =
  | "COMPLIANT"
  | "POTENTIAL_NON_COMPLIANCE"
  | "MANUAL_REVIEW"
  | "NOT_ASSESSABLE";
```

This prevents the system from calling an OCR ambiguity or calibration estimate a legal violation.

### 2. Add a rule-evidence contract

Every rule evaluation should output:

```json
{
  "rule_id": "UNIT_NONSTANDARD",
  "status": "POTENTIAL_NON_COMPLIANCE",
  "confidence": 0.94,
  "citation_verified": true,
  "evidence": {
    "source_text": "Net Qty: 500 gms",
    "ocr_confidence": 0.96,
    "bbox": [412, 688, 221, 42],
    "match_method": "exact_normalized"
  },
  "reason": "The extracted quantity uses 'gms'; review against the verified permitted unit."
}
```

This gives the frontend, PDF, and judge a transparent trail from pixels to conclusion.

### 3. Make calibration opt-in

Instead of a slider that silently affects a warning, require a choice:

- "I know the package width: ___ mm."
- "I confirm barcode magnification is approximately: ___%."
- "No physical calibration available."

Only the first two unlock an estimated typography check. Otherwise, render font compliance as `NOT_ASSESSABLE`.

### 4. Build a small adversarial test pack

Use at least 12 local images:

- Clean compliant label.
- 500 gms deliberate unit issue.
- MRP without tax-inclusive wording.
- Missing consumer-care detail.
- No barcode.
- Blurry image.
- Strong glare.
- Curved bottle/jar label.
- Multilingual label.
- Duplicate prices.
- Tiny print.
- Image where OCR reads a number or unit incorrectly.

For each, save the expected result. A repeatable test pack is more valuable than adding more rules.

## Go/No-Go Gates

Use these hard gates to stop fragile work from consuming the schedule:

- **End of Day 1:** Frontend completes upload → fixture response → results → PDF mock.
- **End of Day 2:** OCR returns usable text and boxes on 8 of 12 test images.
- **End of Day 3:** Gemini produces valid schema-conforming output on 10 consecutive calls, with fallback fixture working.
- **End of Day 4:** Three verified rule checks have correct expected outputs across the test pack; report generation works after browser refresh.
- **Final day:** Two full demos run successfully on a clean machine/network condition. No new capability is added after this point.

## Summary

The plan's strongest choices are its fixture-first API contract, separation of semantic extraction from OCR geometry, explicit scale uncertainty, and deterministic rules boundary. The key adjustment is to make the product honest by design: narrow the legal claims, promote manual review where evidence is uncertain, and treat reliable demo execution as more valuable than feature completeness.

---

[1] Plan.md
