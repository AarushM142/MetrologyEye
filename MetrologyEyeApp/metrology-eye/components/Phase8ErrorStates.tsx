"use client";

interface QualityGateErrorProps {
  reason: "blurry" | "glare" | "low_res";
  onRetake: () => void;
}

export function QualityGateError({ reason, onRetake }: QualityGateErrorProps) {
  const title =
    reason === "blurry"
      ? "Optical Blur Detected"
      : reason === "glare"
      ? "Specular Glare Detected"
      : "Low Resolution Image";

  const message =
    reason === "blurry"
      ? "The captured photo is out of focus or motion-blurred. Text recognition accuracy will be severely compromised."
      : reason === "glare"
      ? "Bright reflections are obscuring mandatory declarations on glossy packaging."
      : "Image resolution is too low to resolve statutory fine print (MRP & net quantity).";

  return (
    <div className="p-6 bg-rose-50/90 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 rounded-xl space-y-4 text-center max-w-lg mx-auto shadow-xs">
      <div className="w-12 h-12 rounded-full bg-rose-100 dark:bg-rose-900/60 flex items-center justify-center mx-auto text-rose-600 dark:text-rose-300 text-xl font-bold">
        📷
      </div>
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-rose-900 dark:text-rose-200">
          {title} — Retake Recommended
        </h3>
        <p className="text-xs text-rose-700 dark:text-rose-300 leading-relaxed">
          {message}
        </p>
      </div>
      <button
        type="button"
        onClick={onRetake}
        className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-medium rounded-lg transition-colors shadow-xs"
      >
        Retake Photo →
      </button>
    </div>
  );
}

interface ScaleMissingNoticeProps {
  onAddScaleReference?: () => void;
}

export function ScaleMissingNotice({ onAddScaleReference }: ScaleMissingNoticeProps) {
  return (
    <div className="p-4 bg-slate-100 dark:bg-zinc-800/80 border border-slate-300 dark:border-zinc-700 rounded-xl flex items-start space-x-3 text-slate-800 dark:text-zinc-200">
      <span className="text-lg leading-none mt-0.5">📏</span>
      <div className="space-y-1 flex-1">
        <h4 className="text-xs font-semibold">
          Scale Reference Missing — Font Height Suppressed
        </h4>
        <p className="text-[11px] text-slate-600 dark:text-zinc-400">
          Neither an EAN-13 barcode nor a standard ID-1 card scale reference was detected in frame. Statutory typography height checks are suppressed to prevent false non-compliance calls.
        </p>
      </div>
      {onAddScaleReference && (
        <button
          type="button"
          onClick={onAddScaleReference}
          className="text-xs font-medium text-slate-700 dark:text-zinc-200 underline underline-offset-2 hover:opacity-80"
        >
          Add Scale
        </button>
      )}
    </div>
  );
}

interface ExtractionFallbackNoticeProps {
  onUseDemoMode?: () => void;
}

export function ExtractionFallbackNotice({ onUseDemoMode }: ExtractionFallbackNoticeProps) {
  return (
    <div className="p-4 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 rounded-xl flex items-start justify-between gap-3 text-amber-900 dark:text-amber-200">
      <div className="flex items-start space-x-3">
        <span className="text-lg leading-none mt-0.5">🤖</span>
        <div className="space-y-1">
          <h4 className="text-xs font-semibold">
            AI Extraction Offline — Fallback Active
          </h4>
          <p className="text-[11px] opacity-90">
            Gemini vision API service timed out or key not configured. Pipeline running with local deterministic fixture mode.
          </p>
        </div>
      </div>
      {onUseDemoMode && (
        <button
          type="button"
          onClick={onUseDemoMode}
          className="px-3 py-1 bg-amber-600 text-white text-xs font-medium rounded hover:bg-amber-700 transition-colors flex-shrink-0"
        >
          View Demo Fixture
        </button>
      )}
    </div>
  );
}
