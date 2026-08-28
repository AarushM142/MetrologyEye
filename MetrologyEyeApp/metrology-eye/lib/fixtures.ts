import { AnalyzeResponse } from "./types";

/**
 * Generates an SVG data URL representing the sample preprocessed label image.
 * Provides a crisp, realistic backdrop for the evidence canvas in offline/demo mode.
 */
export function getDemoLabelSvgDataUrl(): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1600" width="1200" height="1600">
    <defs>
      <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e4e4e7" stroke-width="1"/>
      </pattern>
    </defs>
    <!-- Background -->
    <rect width="1200" height="1600" fill="#fcfcfc" />
    <rect width="1200" height="1600" fill="url(#grid)" opacity="0.4" />
    
    <!-- Package Label Card Frame -->
    <rect x="80" y="80" width="1040" height="1440" rx="8" fill="#ffffff" stroke="#d4d4d8" stroke-width="2" />
    
    <!-- Top Header Banner -->
    <rect x="120" y="120" width="960" height="70" fill="#18181b" rx="4" />
    <text x="600" y="165" font-family="system-ui, -apple-system, sans-serif" font-size="26" font-weight="700" fill="#ffffff" text-anchor="middle" letter-spacing="4">PREMIUM EDIBLE OIL</text>
    
    <!-- Commodity Name -->
    <text x="160" y="275" font-family="system-ui, -apple-system, sans-serif" font-size="44" font-weight="800" fill="#09090b">SURAJ Refined Sunflower Oil</text>
    
    <!-- Net Quantity Box -->
    <rect x="150" y="350" width="410" height="85" fill="#f4f4f5" rx="4" stroke="#e4e4e7" stroke-width="1"/>
    <text x="175" y="385" font-family="system-ui, -apple-system, sans-serif" font-size="16" font-weight="600" fill="#71717a">DECLARATION OF QUANTITY</text>
    <text x="175" y="418" font-family="system-ui, -apple-system, sans-serif" font-size="28" font-weight="700" fill="#09090b">Net Qty: <tspan fill="#e11d48">500 gms</tspan></text>
    
    <!-- MRP Box -->
    <rect x="150" y="470" width="440" height="85" fill="#f4f4f5" rx="4" stroke="#e4e4e7" stroke-width="1"/>
    <text x="175" y="505" font-family="system-ui, -apple-system, sans-serif" font-size="16" font-weight="600" fill="#71717a">RETAIL SALE PRICE</text>
    <text x="175" y="538" font-family="system-ui, -apple-system, sans-serif" font-size="28" font-weight="700" fill="#09090b">MRP <tspan fill="#e11d48">Rs. 145.00</tspan></text>
    
    <!-- Mfg Date Box -->
    <rect x="150" y="590" width="360" height="75" fill="#f4f4f5" rx="4" stroke="#e4e4e7" stroke-width="1"/>
    <text x="175" y="622" font-family="system-ui, -apple-system, sans-serif" font-size="15" font-weight="600" fill="#71717a">DATE OF PACKAGING</text>
    <text x="175" y="650" font-family="system-ui, -apple-system, sans-serif" font-size="22" font-weight="700" fill="#09090b">Mfd: 03/2026</text>
    
    <!-- Best Before -->
    <text x="160" y="730" font-family="system-ui, -apple-system, sans-serif" font-size="20" font-weight="500" fill="#27272a">Best before 9 months from packaging</text>
    
    <line x1="150" y1="780" x2="1050" y2="780" stroke="#e4e4e7" stroke-width="1" />
    
    <!-- Manufacturer Name & Address -->
    <text x="160" y="825" font-family="system-ui, -apple-system, sans-serif" font-size="16" font-weight="600" fill="#71717a">MANUFACTURED &amp; PACKED BY</text>
    <text x="160" y="858" font-family="system-ui, -apple-system, sans-serif" font-size="22" font-weight="700" fill="#09090b">Suraj Foods Private Limited</text>
    <text x="160" y="922" font-family="system-ui, -apple-system, sans-serif" font-size="19" font-weight="400" fill="#3f3f46">Plot 14, MIDC Industrial Area, Nashik, Maharashtra 422007</text>
    
    <!-- Consumer Care -->
    <text x="160" y="1025" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="500" fill="#3f3f46">Consumer care: care@surajfoods.example / 1800-000-000</text>
    
    <!-- FSSAI -->
    <text x="160" y="1125" font-family="system-ui, -apple-system, sans-serif" font-size="19" font-weight="600" fill="#18181b">FSSAI Lic. No. 10012043000123</text>
    
    <!-- Barcode simulation on right side -->
    <g transform="translate(680, 360)">
      <rect x="0" y="0" width="370" height="240" fill="#ffffff" stroke="#d4d4d8" stroke-width="1" rx="4"/>
      <rect x="25" y="30" width="6" height="130" fill="#09090b"/>
      <rect x="37" y="30" width="10" height="130" fill="#09090b"/>
      <rect x="55" y="30" width="4" height="130" fill="#09090b"/>
      <rect x="65" y="30" width="14" height="130" fill="#09090b"/>
      <rect x="85" y="30" width="6" height="130" fill="#09090b"/>
      <rect x="98" y="30" width="12" height="130" fill="#09090b"/>
      <rect x="116" y="30" width="4" height="130" fill="#09090b"/>
      <rect x="127" y="30" width="16" height="130" fill="#09090b"/>
      <rect x="150" y="30" width="6" height="145" fill="#09090b"/>
      <rect x="162" y="30" width="6" height="145" fill="#09090b"/>
      <rect x="175" y="30" width="10" height="130" fill="#09090b"/>
      <rect x="192" y="30" width="4" height="130" fill="#09090b"/>
      <rect x="204" y="30" width="14" height="130" fill="#09090b"/>
      <rect x="225" y="30" width="6" height="130" fill="#09090b"/>
      <rect x="238" y="30" width="12" height="130" fill="#09090b"/>
      <rect x="256" y="30" width="8" height="130" fill="#09090b"/>
      <rect x="270" y="30" width="14" height="130" fill="#09090b"/>
      <rect x="290" y="30" width="4" height="130" fill="#09090b"/>
      <rect x="300" y="30" width="10" height="130" fill="#09090b"/>
      <rect x="318" y="30" width="6" height="145" fill="#09090b"/>
      <rect x="330" y="30" width="6" height="145" fill="#09090b"/>
      <text x="185" y="200" font-family="monospace" font-size="20" font-weight="700" fill="#09090b" text-anchor="middle" letter-spacing="4">8901234567890</text>
    </g>
    
    <!-- Storage condition -->
    <text x="160" y="1210" font-family="system-ui, -apple-system, sans-serif" font-size="16" font-style="italic" fill="#71717a">Store in a cool dry place away from direct sunlight</text>
  </svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

export const DEMO_ANALYSIS_ID = "demo-suraj-oil-500g";

export const DEMO_ANALYSIS_RESPONSE: AnalyzeResponse = {
  analysis_id: DEMO_ANALYSIS_ID,
  source: "upload",
  image: {
    width: 1200,
    height: 1600,
    preview_url: `/api/image/${DEMO_ANALYSIS_ID}`,
  },
  scale: {
    px_per_mm: 7.42,
    confidence: 0.85,
    source: "ean13",
    assumed_magnification: 1.0,
    barcode_value: "8901234567890",
    note: "Scale derived from EAN-13 nominal width (37.29 mm) assuming 100% print magnification. Font-size findings are advisory warnings, not violations.",
  },
  declarations: [
    {
      field: "commodity_name",
      value: "Refined Sunflower Oil",
      bbox: [160, 235, 780, 55],
      confidence: 0.96,
      geometry_source: "ocr",
      text_height_mm: 5.2,
    },
    {
      field: "net_quantity",
      value: "500 gms",
      bbox: [150, 350, 410, 85],
      confidence: 0.95,
      geometry_source: "ocr",
      text_height_mm: 4.8,
    },
    {
      field: "mrp",
      value: "Rs. 145.00",
      bbox: [150, 470, 440, 85],
      confidence: 0.93,
      geometry_source: "ocr",
      text_height_mm: 4.2,
    },
    {
      field: "manufacture_date",
      value: "03/2026",
      bbox: [150, 590, 360, 75],
      confidence: 0.91,
      geometry_source: "ocr",
      text_height_mm: 3.4,
    },
    {
      field: "best_before",
      value: "Best before 9 months from packaging",
      bbox: [160, 705, 580, 35],
      confidence: 0.89,
      geometry_source: "ocr",
      text_height_mm: 2.9,
    },
    {
      field: "manufacturer_name",
      value: "Suraj Foods Private Limited",
      bbox: [160, 830, 520, 38],
      confidence: 0.94,
      geometry_source: "ocr",
      text_height_mm: 3.1,
    },
    {
      field: "manufacturer_address",
      value: "Plot 14, MIDC Industrial Area, Nashik, Maharashtra 422007",
      bbox: [160, 895, 875, 38],
      confidence: 0.92,
      geometry_source: "ocr",
      text_height_mm: 2.8,
    },
    {
      field: "consumer_care",
      value: "care@surajfoods.example / 1800-000-000",
      bbox: [160, 1000, 720, 35],
      confidence: 0.9,
      geometry_source: "ocr",
      text_height_mm: 2.7,
    },
    {
      field: "fssai_number",
      value: "10012043000123",
      bbox: [160, 1100, 420, 35],
      confidence: 0.93,
      geometry_source: "ocr",
      text_height_mm: 2.6,
    },
  ],
  findings: [
    {
      rule_id: "UNIT_NONSTANDARD",
      severity: "VIOLATION",
      citation: "Rule 13, Legal Metrology (Packaged Commodities) Rules, 2011",
      verified_citation: false,
      message: "Net quantity uses non-standard unit 'gms'. The permitted symbol is 'g'.",
      field: "net_quantity",
      bbox: [150, 350, 410, 85],
      observed: "500 gms",
      expected: "500 g",
    },
    {
      rule_id: "MRP_TAX_WORDING_MISSING",
      severity: "VIOLATION",
      citation: "Rule 6(1)(e), Legal Metrology (Packaged Commodities) Rules, 2011",
      verified_citation: false,
      message: "MRP is declared without the required 'inclusive of all taxes' wording.",
      field: "mrp",
      bbox: [150, 470, 440, 85],
      observed: "Rs. 145.00",
      expected: "MRP Rs. 145.00 (inclusive of all taxes)",
    },
    {
      rule_id: "MISSING_DECLARATION",
      severity: "VIOLATION",
      citation: "Rule 6(1), Legal Metrology (Packaged Commodities) Rules, 2011",
      verified_citation: false,
      message: "Mandatory declaration 'Country of Origin' is not present on the label.",
      field: "country_of_origin",
      bbox: null,
      observed: null,
      expected: "Declaration must be present",
    },
    {
      rule_id: "DECLARATION_PRESENT",
      severity: "COMPLIANT",
      citation: "Rule 6(1), Legal Metrology (Packaged Commodities) Rules, 2011",
      verified_citation: false,
      message: "'Name of Commodity' is present and passed all applicable checks.",
      field: "commodity_name",
      bbox: [160, 235, 780, 55],
      observed: "Refined Sunflower Oil",
      expected: "Present",
    },
    {
      rule_id: "DECLARATION_PRESENT",
      severity: "COMPLIANT",
      citation: "Rule 6(1), Legal Metrology (Packaged Commodities) Rules, 2011",
      verified_citation: false,
      message: "'Manufacturer Name' is present and passed all applicable checks.",
      field: "manufacturer_name",
      bbox: [160, 830, 520, 38],
      observed: "Suraj Foods Private Limited",
      expected: "Present",
    },
    {
      rule_id: "DECLARATION_PRESENT",
      severity: "COMPLIANT",
      citation: "Rule 6(1), Legal Metrology (Packaged Commodities) Rules, 2011",
      verified_citation: false,
      message: "'Manufacturer Address' is present and passed all applicable checks.",
      field: "manufacturer_address",
      bbox: [160, 895, 875, 38],
      observed: "Plot 14, MIDC Industrial Area, Nashik, Maharashtra 422007",
      expected: "Present",
    },
    {
      rule_id: "DECLARATION_PRESENT",
      severity: "COMPLIANT",
      citation: "Rule 6(1), Legal Metrology (Packaged Commodities) Rules, 2011",
      verified_citation: false,
      message: "'Date of Manufacture' is present and passed all applicable checks.",
      field: "manufacture_date",
      bbox: [150, 590, 360, 75],
      observed: "03/2026",
      expected: "Valid date",
    },
    {
      rule_id: "DECLARATION_PRESENT",
      severity: "COMPLIANT",
      citation: "Rule 6(1), Legal Metrology (Packaged Commodities) Rules, 2011",
      verified_citation: false,
      message: "'Consumer Care Details' is present and passed all applicable checks.",
      field: "consumer_care",
      bbox: [160, 1000, 720, 35],
      observed: "care@surajfoods.example / 1800-000-000",
      expected: "Present",
    },
    {
      rule_id: "DECLARATION_PRESENT",
      severity: "COMPLIANT",
      citation: "Rule 6(1), Legal Metrology (Packaged Commodities) Rules, 2011",
      verified_citation: false,
      message: "'FSSAI Licence Number' is present and passed all applicable checks.",
      field: "fssai_number",
      bbox: [160, 1100, 420, 35],
      observed: "10012043000123",
      expected: "Present",
    },
  ],
  summary: {
    violations: 3,
    warnings: 0,
    compliant: 6,
  },
  timings_ms: {
    preprocess: 110,
    scale: 48,
    ocr: 340,
    extract: 890,
    rules: 6,
    total: 1394,
  },
  degraded: ["extract_mocked"],
  manual_inspection_required: false,
};

