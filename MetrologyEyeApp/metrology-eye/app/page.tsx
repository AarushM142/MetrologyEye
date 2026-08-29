"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/Header";
import { Dropzone } from "@/components/Dropzone";
import { CalibrationSlider } from "@/components/CalibrationSlider";
import { ExtractionFallbackNotice } from "@/components/Phase8ErrorStates";
import { analyzeUpload, analyzeUrl } from "@/lib/api";
import { DEMO_ANALYSIS_ID } from "@/lib/fixtures";

export default function UploadPage() {
  const router = useRouter();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [showOptions, setShowOptions] = useState<boolean>(false);
  const [manualPxPerMm, setManualPxPerMm] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showFallbackNotice, setShowFallbackNotice] = useState<boolean>(false);

  const handleFileSelect = (file: File) => {
    setErrorMessage(null);
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleClear = () => {
    setSelectedFile(null);
    setPreviewUrl(null);
    setErrorMessage(null);
  };

  const handleAnalyzeUpload = async () => {
    if (!selectedFile) return;
    setLoading(true);
    setErrorMessage(null);

    try {
      const res = await analyzeUpload(selectedFile, manualPxPerMm || undefined);
      if (res.manual_fallback) {
        setShowFallbackNotice(true);
      }
      router.push(`/results/${res.analysis_id}`);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to analyze image");
      setLoading(false);
    }
  };

  const handleAnalyzeUrl = async (url: string) => {
    setLoading(true);
    setErrorMessage(null);

    try {
      const res = await analyzeUrl(url);
      if (res.manual_fallback) {
        setShowFallbackNotice(true);
      }
      router.push(`/results/${res.analysis_id}`);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to process image URL");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 flex flex-col font-sans">
      <Header />

      <main className="flex-1 max-w-2xl w-full mx-auto px-4 sm:px-6 py-10 flex flex-col justify-center space-y-6">
        {/* Header */}
        <div className="text-center space-y-1.5">
          <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
            Scan Package Label
          </h1>
          <p className="text-xs sm:text-sm text-zinc-500 dark:text-zinc-400">
            Photograph packaging to extract mandatory declarations and test LMPC legal compliance.
          </p>
        </div>

        {errorMessage && (
          <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 rounded-lg text-xs text-rose-800 dark:text-rose-300 text-center">
            {errorMessage}
          </div>
        )}

        {showFallbackNotice && (
          <ExtractionFallbackNotice
            onUseDemoMode={() => router.push(`/results/${DEMO_ANALYSIS_ID}`)}
          />
        )}

        {/* Dropzone Uploader */}
        <Dropzone
          selectedFile={selectedFile}
          previewUrl={previewUrl}
          loading={loading}
          onFileSelect={handleFileSelect}
          onClear={handleClear}
          onAnalyze={handleAnalyzeUpload}
          onUrlAnalyze={handleAnalyzeUrl}
        />

        {/* Scale Calibration Toggle & Slider */}
        <div className="space-y-3">
          <div className="flex items-center justify-end">
            <button
              type="button"
              onClick={() => setShowOptions(!showOptions)}
              className="text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200 flex items-center space-x-1"
            >
              <span>⚙️</span>
              <span>{showOptions ? "Hide Scale Options" : "Scale Calibration Options"}</span>
            </button>
          </div>

          {showOptions && (
            <CalibrationSlider
              scaleInfo={
                manualPxPerMm
                  ? {
                      px_per_mm: manualPxPerMm,
                      confidence: 1.0,
                      source: "manual",
                      assumed_magnification: 1.0,
                      barcode_value: null,
                      note: "Manual override slider applied",
                      tier: "HIGH",
                    }
                  : null
              }
              onScaleChange={(val) => setManualPxPerMm(val)}
            />
          )}
        </div>

        {/* Quick Demo Link */}
        <div className="text-center pt-2">
          <button
            type="button"
            onClick={() => router.push(`/results/${DEMO_ANALYSIS_ID}`)}
            className="text-xs text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 font-medium transition-colors"
          >
            Or view demo inspection (Suraj Oil 500g) →
          </button>
        </div>
      </main>
    </div>
  );
}
