"use client";

import { useState } from "react";
import { DEGRADATION_DESCRIPTIONS, DegradationFlag } from "@/lib/types";

interface DegradationBannerProps {
  degraded: DegradationFlag[];
  manualInspectionRequired: boolean;
  onRetryOrCalibrate?: () => void;
}

export function DegradationBanner({
  degraded,
  manualInspectionRequired,
  onRetryOrCalibrate,
}: DegradationBannerProps) {
  const [expanded, setExpanded] = useState<boolean>(false);

  if ((!degraded || degraded.length === 0) && !manualInspectionRequired) {
    return null;
  }

  const isSevere =
    manualInspectionRequired ||
    degraded.some((flag) =>
      [
        "extract_failed",
        "ocr_unavailable",
        "quality_gate_failed",
        "no_scale_reference",
      ].includes(flag)
    );

  return (
    <div
      className={`rounded-xl border p-4 transition-all ${
        isSevere
          ? "bg-amber-50/80 dark:bg-amber-950/40 border-amber-200 dark:border-amber-900/60 text-amber-900 dark:text-amber-200"
          : "bg-slate-50 dark:bg-zinc-900/80 border-slate-200 dark:border-zinc-800 text-slate-800 dark:text-zinc-300"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start space-x-3">
          <div className="mt-0.5 flex-shrink-0">
            {isSevere ? (
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400 font-bold text-xs">
                ⚠️
              </span>
            ) : (
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-500/20 text-slate-600 dark:text-slate-400 font-bold text-xs">
                ℹ️
              </span>
            )}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-xs font-semibold tracking-tight">
                {manualInspectionRequired
                  ? "Manual Officer Inspection Recommended"
                  : "Analysis Quality Notice"}
              </h3>
              <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-white/80 dark:bg-zinc-800 border border-amber-200/60 dark:border-zinc-700">
                {degraded.length} Flag{degraded.length !== 1 ? "s" : ""}
              </span>
            </div>
            <p className="mt-0.5 text-[11px] opacity-90">
              {manualInspectionRequired
                ? "Some statutory measurements or OCR fields degraded during processing. Verify values against physical packaging."
                : "Operational flags detected during automated processing."}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {onRetryOrCalibrate && (
            <button
              type="button"
              onClick={onRetryOrCalibrate}
              className="text-[11px] font-medium px-2.5 py-1 rounded bg-white/90 dark:bg-zinc-800 border border-amber-300/80 dark:border-zinc-700 hover:bg-amber-100 dark:hover:bg-zinc-700 transition-colors"
            >
              Calibrate / Retake
            </button>
          )}
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="text-[11px] font-medium underline underline-offset-2 opacity-80 hover:opacity-100"
          >
            {expanded ? "Hide details" : "View details"}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-amber-200/50 dark:border-zinc-800/80 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
          {degraded.map((flag) => {
            const desc = DEGRADATION_DESCRIPTIONS[flag] || {
              title: flag.replace("_", " "),
              detail: "System flag asserted during pipeline execution.",
            };
            return (
              <div
                key={flag}
                className="p-2.5 rounded-lg bg-white/60 dark:bg-zinc-950/40 border border-amber-200/40 dark:border-zinc-800 space-y-0.5"
              >
                <div className="font-semibold text-[11px] flex items-center space-x-1">
                  <span>•</span>
                  <span>{desc.title}</span>
                </div>
                <p className="text-[10px] text-zinc-600 dark:text-zinc-400">
                  {desc.detail}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
