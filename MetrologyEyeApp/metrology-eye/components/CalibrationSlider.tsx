"use client";

import { useState } from "react";
import { ScaleConfidenceTier, ScaleInfo } from "@/lib/types";

interface CalibrationSliderProps {
  scaleInfo: ScaleInfo | null;
  onScaleChange: (pxPerMm: number | null) => void;
}

export function CalibrationSlider({
  scaleInfo,
  onScaleChange,
}: CalibrationSliderProps) {
  const defaultPxPerMm = scaleInfo?.px_per_mm || 7.5;
  const tier: ScaleConfidenceTier = scaleInfo?.tier || "MEDIUM";

  const [pxPerMm, setPxPerMm] = useState<number>(defaultPxPerMm);
  const [isManual, setIsManual] = useState<boolean>(
    scaleInfo?.source === "manual"
  );

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setPxPerMm(val);
    setIsManual(true);
    onScaleChange(val);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    if (!isNaN(val) && val > 0) {
      setPxPerMm(val);
      setIsManual(true);
      onScaleChange(val);
    }
  };

  const handleReset = () => {
    setPxPerMm(defaultPxPerMm);
    setIsManual(false);
    onScaleChange(null);
  };

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 space-y-3 shadow-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">
            Physical Scale Calibration
          </span>
          <span
            className={`text-[10px] font-mono font-medium px-2 py-0.5 rounded-full border ${
              tier === "HIGH"
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900"
                : tier === "MEDIUM"
                ? "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-900"
                : "bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-zinc-300 border-slate-300 dark:border-zinc-700"
            }`}
          >
            Tier: {tier}
          </span>
        </div>

        {isManual && (
          <button
            type="button"
            onClick={handleReset}
            className="text-[11px] font-medium text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200 underline underline-offset-2"
          >
            Reset to Auto
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-center text-xs">
        {/* Source info */}
        <div className="sm:col-span-4 space-y-0.5">
          <div className="text-[11px] text-zinc-500 font-mono">
            Source: {scaleInfo?.source || "auto-detected"}
          </div>
          <p className="text-[10px] text-zinc-400">
            {scaleInfo?.note || "EAN-13 nominal / ID-1 Reference Card scale."}
          </p>
        </div>

        {/* Slider & Input */}
        <div className="sm:col-span-8 flex items-center space-x-3">
          <input
            type="range"
            min="1.0"
            max="20.0"
            step="0.1"
            value={pxPerMm}
            onChange={handleSliderChange}
            className="flex-1 h-1.5 bg-zinc-200 dark:bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-zinc-900 dark:accent-zinc-100"
          />

          <div className="flex items-center space-x-1 font-mono flex-shrink-0">
            <input
              type="number"
              step="0.1"
              min="0.5"
              max="50.0"
              value={pxPerMm.toFixed(1)}
              onChange={handleInputChange}
              className="w-16 px-2 py-1 text-xs bg-zinc-50 dark:bg-zinc-950 border border-zinc-300 dark:border-zinc-700 rounded text-center font-mono font-semibold"
            />
            <span className="text-[10px] text-zinc-400">px/mm</span>
          </div>
        </div>
      </div>
    </div>
  );
}
