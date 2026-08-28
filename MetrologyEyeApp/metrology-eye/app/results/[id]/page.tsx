"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Header } from "@/components/Header";
import { EvidenceCanvas } from "@/components/EvidenceCanvas";
import { getAnalysis, getImageUrl } from "@/lib/api";
import {
  AnalyzeResponse,
  DECLARATION_FIELD_LABELS,
  DeclarationField,
} from "@/lib/types";

export default function ResultsPage() {
  const params = useParams();
  const id = (params?.id as string) || "demo-suraj-oil-500g";

  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedField, setSelectedField] = useState<string | null>(null);

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

  const { summary, findings, declarations, image } = analysis;
  const imageUrl = getImageUrl(analysis.analysis_id);

  // Group findings by field
  const findingsByField = new Map<string, typeof findings[0]>();
  findings.forEach((f) => {
    if (f.field) findingsByField.set(f.field, f);
  });

  // Find commodity name if present
  const commodityDecl = declarations.find((d) => d.field === "commodity_name");
  const title = commodityDecl?.value || "Packaged Commodity Label";

  // Build unified checklist
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

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 flex flex-col font-sans">
      <Header />

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Clean Header Bar */}
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
              {summary.violations > 0 ? (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200 dark:border-rose-900">
                  {summary.violations} Non-Compliances
                </span>
              ) : (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900">
                  Compliant
                </span>
              )}
            </div>
          </div>

          <Link
            href={`/notice-preview/${analysis.analysis_id}`}
            className="self-start sm:self-auto px-4 py-2 bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 text-xs font-medium rounded-lg hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors shadow-xs"
          >
            Generate Form-I Notice →
          </Link>
        </div>

        {/* 2-Column Inspection Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left: Canvas Viewer (7 Cols) */}
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

          {/* Right: Clean Inspection Checklist (5 Cols) */}
          <div className="lg:col-span-5 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 sm:p-5 h-[580px] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-100 dark:border-zinc-800">
              <h2 className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 uppercase tracking-wider">
                Mandatory Declarations Checklist
              </h2>
              <span className="text-xs text-zinc-400 font-mono">
                {declarations.length} Detected
              </span>
            </div>

            <div className="flex-1 overflow-y-auto divide-y divide-zinc-100 dark:divide-zinc-800/80 pr-1 mt-1">
              {allFields.map((fieldKey) => {
                const decl = declarations.find((d) => d.field === fieldKey);
                const finding = findingsByField.get(fieldKey);
                const isViolation = finding?.severity === "VIOLATION";
                const isSelected = selectedField === fieldKey;

                // Don't render optional absent fields if not in declarations or findings
                if (!decl && !finding) return null;

                return (
                  <div
                    key={fieldKey}
                    onClick={() =>
                      setSelectedField(isSelected ? null : fieldKey)
                    }
                    className={`py-3 px-2 rounded-lg transition-colors cursor-pointer ${
                      isSelected
                        ? "bg-zinc-100 dark:bg-zinc-800"
                        : "hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-0.5 flex-1">
                        <div className="flex items-center space-x-2">
                          <span
                            className={`w-2 h-2 rounded-full flex-shrink-0 ${
                              isViolation
                                ? "bg-rose-500"
                                : decl
                                ? "bg-emerald-500"
                                : "bg-amber-500"
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

                      {finding && isViolation && (
                        <span className="text-[11px] font-medium text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/60 px-2 py-0.5 rounded border border-rose-200 dark:border-rose-900 flex-shrink-0">
                          Non-compliant
                        </span>
                      )}
                    </div>

                    {finding && isViolation && (
                      <div className="mt-2 ml-4 p-2 bg-rose-50/60 dark:bg-rose-950/30 border border-rose-200/80 dark:border-rose-900/60 rounded text-[11px] text-rose-900 dark:text-rose-300">
                        {finding.message}
                        <div className="mt-1 text-[10px] text-rose-700 dark:text-rose-400 font-mono">
                          {finding.citation}
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
