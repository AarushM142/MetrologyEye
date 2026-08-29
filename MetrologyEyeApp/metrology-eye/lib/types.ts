/**
 * TypeScript definitions generated from MetrologyEye backend OpenAPI / Pydantic schemas.
 * Sources: app.schemas.analysis and app.schemas.violations
 */

/**
 * Coordinate box [x, y, width, height] in pixels within the preprocessed image frame.
 */
export type BBox = [number, number, number, number];

export type Severity = "VIOLATION" | "WARNING" | "COMPLIANT" | "MANUAL_REQUIRED";

export type DeclarationField =
  | "commodity_name"
  | "manufacturer_name"
  | "manufacturer_address"
  | "net_quantity"
  | "mrp"
  | "manufacture_date"
  | "best_before"
  | "consumer_care"
  | "country_of_origin"
  | "fssai_number";

export type ScaleSource = "ean13" | "reference_object" | "manual" | "none";
export type ScaleConfidenceTier = "HIGH" | "MEDIUM" | "MANUAL_REQUIRED";

export interface BarcodeScale {
  px_per_mm: number;
  confidence: number;
  assumed_magnification: number;
  barcode_value?: string | null;
}

export interface ReferenceObjectScale {
  px_per_mm: number;
  confidence: number;
  type?: string;
}

export interface ScaleInfo {
  px_per_mm: number;
  confidence: number;
  source: ScaleSource;
  assumed_magnification: number;
  barcode_value: string | null;
  note: string;
  tier?: ScaleConfidenceTier;
  barcode?: BarcodeScale | null;
  reference_object?: ReferenceObjectScale | null;
}

export type GeometrySource = "ocr" | "vlm" | "none";

export interface Declaration {
  field: DeclarationField;
  value: string;
  bbox: BBox | null;
  confidence: number;
  geometry_source: GeometrySource;
  text_height_mm?: number | null;
  ocr_confidence?: number;
  extract_confidence?: number;
  needs_review?: boolean;
}

export interface ImageMeta {
  width: number;
  height: number;
  preview_url: string;
}

export interface Summary {
  violations: number;
  warnings: number;
  compliant: number;
  manual_required?: number;
}

export interface Timings {
  preprocess: number;
  scale: number;
  ocr: number;
  extract: number;
  rules: number;
  total: number;
}

export type DegradationFlag =
  | "no_barcode"
  | "blurry_image"
  | "low_resolution"
  | "ocr_unavailable"
  | "extract_mocked"
  | "extract_failed"
  | "partial_text"
  | "quality_gate_failed"
  | "glare_detected"
  | "no_scale_reference";

export interface Finding {
  rule_id: string;
  severity: Severity;
  citation: string;
  verified_citation: boolean;
  message: string;
  field: DeclarationField | null;
  bbox: BBox | null;
  observed: string | null;
  expected: string | null;
}

export interface AnalyzeResponse {
  analysis_id: string;
  source: "upload" | "url";
  image: ImageMeta;
  scale: ScaleInfo | null;
  declarations: Declaration[];
  findings: Finding[];
  summary: Summary;
  timings_ms: Timings;
  degraded: DegradationFlag[];
  manual_inspection_required: boolean;
  extraction_status?: "ok" | "unavailable";
  manual_fallback?: boolean;
}

export interface UrlIngestRequest {
  url: string;
}

export interface NoticeRequest {
  analysis_id: string;
  inspector_name?: string | null;
  inspector_designation?: string | null;
  premises?: string | null;
}

export interface HealthResponse {
  status: string;
  extraction: "gemini" | "mocked" | string;
  gemini_model: string | null;
  ocr: string;
}

export const DECLARATION_FIELD_LABELS: Record<DeclarationField, string> = {
  commodity_name: "Name of Commodity",
  manufacturer_name: "Manufacturer / Packer Name",
  manufacturer_address: "Manufacturer / Packer Address",
  net_quantity: "Net Quantity",
  mrp: "Maximum Retail Price (MRP)",
  manufacture_date: "Date of Manufacture / Packing",
  best_before: "Best Before / Expiry",
  consumer_care: "Consumer Care Details",
  country_of_origin: "Country of Origin",
  fssai_number: "FSSAI Licence Number",
};

export const DEGRADATION_DESCRIPTIONS: Record<DegradationFlag, { title: string; detail: string }> = {
  no_barcode: {
    title: "No Barcode Detected",
    detail: "Millimetre scale could not be derived automatically from EAN-13 barcode.",
  },
  blurry_image: {
    title: "Blurry Image Quality",
    detail: "High optical blur detected. Text accuracy may be degraded; manual inspection recommended.",
  },
  low_resolution: {
    title: "Low Resolution Input",
    detail: "Image resolution is below optimal OCR density; small fine print may be missed.",
  },
  ocr_unavailable: {
    title: "OCR Engine Offline",
    detail: "Character bounding boxes are unavailable; falling back to semantic analysis.",
  },
  extract_mocked: {
    title: "Offline / Demo Fixture Mode",
    detail: "AI extraction key not configured; processing with standardized test fixture data.",
  },
  extract_failed: {
    title: "AI Extraction Error",
    detail: "Semantic parser encountered an issue reading label fields.",
  },
  partial_text: {
    title: "Incomplete Text Capture",
    detail: "Portions of mandatory declarations appear truncated or occluded.",
  },
  quality_gate_failed: {
    title: "Quality Gate Triggered",
    detail: "Photo quality check flagged issues with focus or illumination. Retake recommended.",
  },
  glare_detected: {
    title: "Specular Glare Detected",
    detail: "Overexposed reflective highlights detected on package surface.",
  },
  no_scale_reference: {
    title: "No Physical Scale Reference",
    detail: "Neither barcode nor reference card resolved in frame. Typography height checks suppressed.",
  },
};

