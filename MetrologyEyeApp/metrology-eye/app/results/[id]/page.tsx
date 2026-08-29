"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Header } from "@/components/Header";
import { EvidenceCanvas } from "@/components/EvidenceCanvas";
import { DegradationBanner } from "@/components/DegradationBanner";
import { FindingsBadge } from "@/components/FindingsBadge";
import { CalibrationSlider } from "@/components/CalibrationSlider";
import { ScaleMissingNotice } from "@/components/Phase8ErrorStates";
import { getAnalysis, getImageUrl } from "@/lib/api";
import {
  AnalyzeResponse,
  DECLARATION_FIELD_LABELS,
  DeclarationField,
  Finding,
} from "@/lib/types";

export default function ResultsPage() {
  const params = useParams();
  const id = (params?.id as string) || "demo-suraj-oil-500g";

  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [showCalibration, setShowCalibration] = useState<boolean>(false);

  useEffect(() => {
    let mounted = true;
    async function fetchResult() {
      setLoading(true);
      const data = await getAnalysis(id);
      if (mounted) {
        setAnalysis(data);
        setLoading(false);
      }
    }
    fetchResult();
    return () => {
      mounted = false;
    };
  }, [id]);

  if (loading || !analysis) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 flex flex-col font-sans">
        <Header />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2">
            <div className="w-5 h-5 border-2 border-zinc-900 dark:border-zinc-100 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-zinc-500 font-mono">Loading inspection...</p>
          </div>
        </div>
      </div>
    );
  }

  const { summary, findings, declarations, image, degraded, manual_inspection_required, scale } = analysis;
  const imageUrl = getImageUrl(analysis.analysis_id);

  // Group findings by field
  const findingsByField = new Map<string, Finding>();
  findings.forEach((f) => {
    if (f.field) findingsByField.set(f.field, f);
  });

  // Commodity title
  const commodityDecl = declarations.find((d) => d.field === "commodity_name");
  const title = commodityDecl?.value || "Packaged Commodity Label";

  // Mandatory fields list
  const allFields: DeclarationField[] = [
    "commodity_name",
    "net_quantity",
    "mrp",
    "manufacture_date",
    "manufacturer_name",
    "manufacturer_address",
    "consumer_care",
    "country_of_origin",
    "best_before",
    "fssai_number",
  ];

  const overallSeverity =
    summary.violations > 0
      ? "VIOLATION"
      : summary.warnings > 0
      ? "WARNING"
      : (summary.manual_required || 0) > 0
      ? "MANUAL_REQUIRED"
      : "COMPLIANT";

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 flex flex-col font-sans">
      <Header />

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-6 space-y-5">
        {/* Top Header Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-zinc-200 dark:border-zinc-800">
          <div className="space-y-1">
            <div className="flex items-center space-x-2 text-xs text-zinc-400">
              <Link href="/" className="hover:text-zinc-900 dark:hover:text-zinc-100">
                ← Upload
              </Link>
              <span>/</span>
              <span className="font-mono">{analysis.analysis_id.slice(0, 14)}</span>
            </div>
            <div className="flex items-center space-x-3">
              <h1 className="text-xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
                {title}
              </h1>
              <FindingsBadge severity={overallSeverity} />
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={() => setShowCalibration(!showCalibration)}
              className="px-3 py-2 text-xs text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 border border-zinc-200 dark:border-zinc-700 rounded-lg transition-colors"
            >
              📐 {showCalibration ? "Hide Calibration" : "Scale Options"}
            </button>
            <Link
              href={`/notice-preview/${analysis.analysis_id}`}
              className="px-4 py-2 bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 text-xs font-medium rounded-lg hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors shadow-xs"
            >
              Generate Form-I Notice →
            </Link>
          </div>
        </div>

        {/* Degradation & Quality Warnings */}
        <DegradationBanner
          degraded={degraded}
          manualInspectionRequired={manual_inspection_required}
          onRetryOrCalibrate={() => setShowCalibration(true)}
        />

        {/* Missing Scale Warning Banner */}
        {scale?.tier === "MANUAL_REQUIRED" && (
          <ScaleMissingNotice onAddScaleReference={() => setShowCalibration(true)} />
        )}

        {/* Calibration Slider Drawer */}
        {showCalibration && (
          <CalibrationSlider
            scaleInfo={scale}
            onScaleChange={(val) => {
              console.log("Updated scale value:", val);
            }}
          />
        )}

        {/* 2-Column Inspection Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left: Canvas Evidence Viewer (7 Cols) */}
          <div className="lg:col-span-7 h-[580px]">
            <EvidenceCanvas
              imageUrl={imageUrl}
              imageWidth={image.width}
              imageHeight={image.height}
              findings={findings}
              selectedField={selectedField}
              onSelectField={(field) => setSelectedField(field)}
            />
          </div>

          {/* Right: Inspection Checklist (5 Cols) */}
          <div className="lg:col-span-5 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 sm:p-5 h-[580px] flex flex-col shadow-xs">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-100 dark:border-zinc-800">
              <h2 className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 uppercase tracking-wider">
                Mandatory Declarations Checklist
              </h2>
              <div className="flex items-center space-x-2 text-xs font-mono text-zinc-500">
                <span>{declarations.length} Detected</span>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto divide-y divide-zinc-100 dark:divide-zinc-800/80 pr-1 mt-1 space-y-1">
              {allFields.map((fieldKey) => {
                const decl = declarations.find((d) => d.field === fieldKey);
                const finding = findingsByField.get(fieldKey);
                const severity = finding?.severity || (decl ? "COMPLIANT" : "VIOLATION");
                const isSelected = selectedField === fieldKey;

                if (!decl && !finding) return null;

                return (
                  <div
                    key={fieldKey}
                    onClick={() =>
                      setSelectedField(isSelected ? null : fieldKey)
                    }
                    className={`py-2.5 px-3 rounded-lg transition-colors cursor-pointer ${
                      isSelected
                        ? "bg-zinc-100 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700"
                        : "hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-0.5 flex-1">
                        <div className="flex items-center space-x-2">
                          <span
                            className={`w-2 h-2 rounded-full flex-shrink-0 ${
                              severity === "VIOLATION"
                                ? "bg-rose-500"
                                : severity === "WARNING"
                                ? "bg-amber-500"
                                : severity === "MANUAL_REQUIRED"
                                ? "bg-slate-500"
                                : "bg-emerald-500"
                            }`}
                          />
                          <span className="text-xs font-medium text-zinc-900 dark:text-zinc-100">
                            {DECLARATION_FIELD_LABELS[fieldKey] || fieldKey}
                          </span>
                        </div>

                        {decl ? (
                          <div className="text-xs font-mono text-zinc-600 dark:text-zinc-400 pl-4 truncate">
                            {decl.value}
                          </div>
                        ) : (
                          <div className="text-xs text-rose-600 dark:text-rose-400 pl-4 font-medium">
                            Missing from packaging
                          </div>
                        )}
                      </div>

                      <FindingsBadge severity={severity} size="sm" />
                    </div>

                    {finding && (
                      <div
                        className={`mt-2 ml-4 p-2 rounded text-[11px] border ${
                          finding.severity === "VIOLATION"
                            ? "bg-rose-50/70 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900 text-rose-900 dark:text-rose-200"
                            : finding.severity === "WARNING"
                            ? "bg-amber-50/70 dark:bg-amber-950/40 border-amber-200 dark:border-amber-900 text-amber-900 dark:text-amber-200"
                            : "bg-slate-50 dark:bg-zinc-800 border-slate-200 dark:border-zinc-700 text-slate-800 dark:text-zinc-200"
                        }`}
                      >
                        <div>{finding.message}</div>
                        <div className="mt-1 text-[10px] opacity-80 font-mono">
                          Citation: {finding.citation}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
