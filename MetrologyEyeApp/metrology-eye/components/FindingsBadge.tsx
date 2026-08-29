"use client";

import { Severity } from "@/lib/types";

interface FindingsBadgeProps {
  severity: Severity;
  label?: string;
  count?: number;
  size?: "sm" | "md" | "lg";
}

export function FindingsBadge({
  severity,
  label,
  count,
  size = "md",
}: FindingsBadgeProps) {
  let colorClasses = "";
  let icon = "";
  let defaultLabel = "";

  switch (severity) {
    case "VIOLATION":
      colorClasses =
        "bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border-rose-200 dark:border-rose-900";
      icon = "❌";
      defaultLabel = "Non-Compliant";
      break;
    case "WARNING":
      colorClasses =
        "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-900";
      icon = "⚠️";
      defaultLabel = "Warning";
      break;
    case "MANUAL_REQUIRED":
      colorClasses =
        "bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-zinc-300 border-slate-300 dark:border-zinc-700";
      icon = "🔍";
      defaultLabel = "Manual Review Required";
      break;
    case "COMPLIANT":
    default:
      colorClasses =
        "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900";
      icon = "✓";
      defaultLabel = "Compliant";
      break;
  }

  const sizeClasses =
    size === "sm"
      ? "px-2 py-0.5 text-[10px]"
      : size === "lg"
      ? "px-3.5 py-1 text-sm font-bold"
      : "px-2.5 py-0.5 text-xs font-semibold";

  return (
    <span
      className={`inline-flex items-center space-x-1.5 rounded-full border shadow-2xs font-mono transition-colors ${colorClasses} ${sizeClasses}`}
    >
      <span className="text-[10px] leading-none">{icon}</span>
      <span>{label || defaultLabel}</span>
      {typeof count === "number" && (
        <span className="ml-1 px-1.5 py-0.2 rounded-full bg-white/60 dark:bg-black/30 text-[10px]">
          {count}
        </span>
      )}
    </span>
  );
}
