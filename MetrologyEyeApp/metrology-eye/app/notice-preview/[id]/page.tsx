"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Header } from "@/components/Header";
import { generateNoticePdf, getAnalysis } from "@/lib/api";
import { AnalyzeResponse, DECLARATION_FIELD_LABELS } from "@/lib/types";

export default function NoticePreviewPage() {
  const params = useParams();
  const id = (params?.id as string) || "demo-suraj-oil-500g";

  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [inspectorName, setInspectorName] = useState<string>("A. Deshmukh");
  const [designation, setDesignation] = useState<string>("Legal Metrology Officer");
  const [premises, setPremises] = useState<string>("Retail Outlet, MIDC, Nashik");
  const [downloading, setDownloading] = useState<boolean>(false);

  useEffect(() => {
    let mounted = true;
    async function loadData() {
      setLoading(true);
      const data = await getAnalysis(id);
      if (mounted) {
        setAnalysis(data);
        setLoading(false);
      }
    }
    loadData();
    return () => {
      mounted = false;
    };
  }, [id]);

  const handleDownloadPdf = async () => {
    if (!analysis) return;
    setDownloading(true);
    try {
      const blob = await generateNoticePdf({
        analysis_id: analysis.analysis_id,
        inspector_name: inspectorName,
        inspector_designation: designation,
        premises: premises,
      });

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `form-i-notice-${analysis.analysis_id.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PDF download failed:", err);
    } finally {
      setDownloading(false);
    }
  };

  if (loading || !analysis) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 flex flex-col font-sans">
        <Header />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2">
            <div className="w-6 h-6 border-2 border-zinc-900 dark:border-zinc-100 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-zinc-500 font-mono">Preparing notice...</p>
          </div>
        </div>
      </div>
    );
  }

  const violations = analysis.findings.filter((f) => f.severity === "VIOLATION");
  const currentDate = new Date().toLocaleDateString("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 flex flex-col font-sans">
      <div className="print:hidden">
        <Header />
      </div>

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-6 space-y-5">
        {/* Top Action & Configuration Bar */}
        <div className="print:hidden bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <Link
              href={`/results/${analysis.analysis_id}`}
              className="text-xs font-medium text-zinc-600 hover:text-zinc-950 dark:text-zinc-400 dark:hover:text-zinc-100"
            >
              ← Back to Results
            </Link>

            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => window.print()}
                className="px-3 py-1.5 text-xs font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded transition-colors"
              >
                Print
              </button>
              <button
                type="button"
                disabled={downloading}
                onClick={handleDownloadPdf}
                className="px-4 py-1.5 text-xs font-medium bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 rounded transition-colors disabled:opacity-50"
              >
                {downloading ? "Exporting..." : "Download PDF →"}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-2 border-t border-zinc-100 dark:border-zinc-800">
            <div>
              <label className="block text-[10px] font-mono text-zinc-400 mb-0.5">
                INSPECTOR NAME
              </label>
              <input
                type="text"
                value={inspectorName}
                onChange={(e) => setInspectorName(e.target.value)}
                className="w-full px-2 py-1 text-xs bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded text-zinc-900 dark:text-zinc-100"
              />
            </div>
            <div>
              <label className="block text-[10px] font-mono text-zinc-400 mb-0.5">
                DESIGNATION
              </label>
              <input
                type="text"
                value={designation}
                onChange={(e) => setDesignation(e.target.value)}
                className="w-full px-2 py-1 text-xs bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded text-zinc-900 dark:text-zinc-100"
              />
            </div>
            <div>
              <label className="block text-[10px] font-mono text-zinc-400 mb-0.5">
                PREMISES
              </label>
              <input
                type="text"
                value={premises}
                onChange={(e) => setPremises(e.target.value)}
                className="w-full px-2 py-1 text-xs bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded text-zinc-900 dark:text-zinc-100"
              />
            </div>
          </div>
        </div>

        {/* Clean Form-I Notice Paper */}
        <div className="bg-white text-zinc-950 border border-zinc-200 rounded-lg p-8 sm:p-10 shadow-xs space-y-6 print:border-none print:shadow-none print:p-0">
          {/* Header */}
          <div className="border-b border-zinc-900 pb-4 text-center space-y-1">
            <div className="text-[11px] font-mono font-semibold tracking-widest text-zinc-500 uppercase">
              GOVERNMENT OF INDIA • DEPARTMENT OF LEGAL METROLOGY
            </div>
            <h2 className="text-lg font-bold uppercase tracking-tight">
              FORM-I: STATUTORY INSPECTION NOTICE
            </h2>
            <div className="text-xs text-zinc-500 font-mono">
              Under Rule 6 &amp; Section 15, Legal Metrology (Packaged Commodities) Rules, 2011
            </div>
          </div>

          {/* Metadata */}
          <div className="grid grid-cols-2 text-xs border-b border-zinc-200 pb-3 gap-2">
            <div>
              <div><span className="font-semibold text-zinc-700">Date:</span> {currentDate}</div>
              <div><span className="font-semibold text-zinc-700">Premises:</span> {premises}</div>
            </div>
            <div className="text-right">
              <div><span className="font-semibold text-zinc-700">Officer:</span> {inspectorName}</div>
              <div><span className="font-semibold text-zinc-700">Designation:</span> {designation}</div>
            </div>
          </div>

          {/* Schedule of Violations */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900">
              Statutory Deficiencies ({violations.length})
            </h3>
            <div className="space-y-2">
              {violations.map((v, idx) => (
                <div key={idx} className="p-3 bg-zinc-50 border border-zinc-200 rounded text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-rose-700 font-mono text-[11px]">
                      {v.rule_id}
                    </span>
                    <span className="font-mono text-zinc-500 text-[11px]">{v.citation}</span>
                  </div>
                  <p className="text-zinc-800 leading-snug">{v.message}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Declarations Summary Table */}
          <div className="space-y-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900">
              Extracted Declarations
            </h3>
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-zinc-500 font-mono text-[10px]">
                  <th className="py-1">Field</th>
                  <th className="py-1">Observed Value</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {analysis.declarations.map((d, idx) => (
                  <tr key={idx}>
                    <td className="py-1.5 font-medium text-zinc-700">
                      {DECLARATION_FIELD_LABELS[d.field] || d.field}
                    </td>
                    <td className="py-1.5 font-mono text-zinc-900">{d.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Signature Block */}
          <div className="pt-8 grid grid-cols-2 text-xs">
            <div className="border-t border-zinc-300 pt-2 text-zinc-500">
              Retailer / Packer Signature
            </div>
            <div className="border-t border-zinc-300 pt-2 text-right text-zinc-800 font-medium">
              {inspectorName}
              <div className="text-[11px] text-zinc-500">{designation}</div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

