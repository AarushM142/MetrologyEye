"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/Header";
import { analyzeUpload, analyzeUrl } from "@/lib/api";
import { DEMO_ANALYSIS_ID } from "@/lib/fixtures";

export default function UploadPage() {
  const router = useRouter();

  const [dragActive, setDragActive] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [urlMode, setUrlMode] = useState<boolean>(false);
  const [urlInput, setUrlInput] = useState<string>("");
  const [showOptions, setShowOptions] = useState<boolean>(false);
  const [manualPxPerMm, setManualPxPerMm] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const processFile = (file: File) => {
    setErrorMessage(null);
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleAnalyzeUpload = async () => {
    if (!selectedFile) return;
    setLoading(true);
    setErrorMessage(null);

    try {
      const scaleValue = manualPxPerMm ? parseFloat(manualPxPerMm) : undefined;
      const res = await analyzeUpload(selectedFile, scaleValue);
      router.push(`/results/${res.analysis_id}`);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to analyze image");
      setLoading(false);
    }
  };

  const handleAnalyzeUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!urlInput.trim()) return;
    setLoading(true);
    setErrorMessage(null);

    try {
      const res = await analyzeUrl(urlInput.trim());
      router.push(`/results/${res.analysis_id}`);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to process image URL");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 flex flex-col font-sans">
      <Header />

      <main className="flex-1 max-w-2xl w-full mx-auto px-4 sm:px-6 py-12 flex flex-col justify-center">
        {/* Clean Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
            Scan Package Label
          </h1>
          <p className="mt-1.5 text-sm text-zinc-500 dark:text-zinc-400">
            Upload a photo to extract mandatory declarations and check LMPC compliance.
          </p>
        </div>

        {errorMessage && (
          <div className="mb-5 p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 rounded text-xs text-rose-800 dark:text-rose-300 text-center">
            {errorMessage}
          </div>
        )}

        {/* Upload Container */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 sm:p-8 shadow-xs space-y-6">
          {!urlMode ? (
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-lg p-8 sm:p-10 transition-colors flex flex-col items-center justify-center text-center ${
                dragActive
                  ? "border-zinc-900 dark:border-zinc-100 bg-zinc-50 dark:bg-zinc-800/50"
                  : "border-zinc-200 dark:border-zinc-800 hover:border-zinc-400 dark:hover:border-zinc-600"
              }`}
            >
              {previewUrl ? (
                <div className="w-full flex flex-col items-center space-y-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={previewUrl}
                    alt="Label preview"
                    className="max-h-56 rounded border border-zinc-200 dark:border-zinc-800 object-contain"
                  />
                  <div className="text-xs font-mono text-zinc-500">
                    {selectedFile?.name}
                  </div>
                  <div className="flex items-center space-x-3 pt-2">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedFile(null);
                        setPreviewUrl(null);
                      }}
                      className="px-3 py-1.5 text-xs text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 border border-zinc-200 dark:border-zinc-700 rounded transition-colors"
                    >
                      Clear
                    </button>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={handleAnalyzeUpload}
                      className="px-5 py-1.5 text-xs font-medium bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 rounded transition-colors disabled:opacity-50"
                    >
                      {loading ? "Analyzing..." : "Analyze Label →"}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      Drop package photo here, or browse
                    </p>
                    <p className="text-xs text-zinc-400">
                      PNG, JPG, WebP up to 12 MB
                    </p>
                  </div>

                  <div className="flex items-center justify-center space-x-3 pt-1">
                    <label className="cursor-pointer px-4 py-2 text-xs font-medium bg-zinc-950 dark:bg-zinc-100 text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 rounded transition-colors">
                      Choose File
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleFileChange}
                        className="hidden"
                      />
                    </label>
                    <label className="cursor-pointer px-4 py-2 text-xs font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded transition-colors">
                      Camera
                      <input
                        type="file"
                        accept="image/*"
                        capture="environment"
                        onChange={handleFileChange}
                        className="hidden"
                      />
                    </label>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <form onSubmit={handleAnalyzeUrl} className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300">
                  Product Image URL
                </label>
                <input
                  type="url"
                  placeholder="https://example.com/product-image.jpg"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-zinc-50 dark:bg-zinc-950 border border-zinc-300 dark:border-zinc-700 rounded text-zinc-900 dark:text-zinc-100 focus:outline-none focus:border-zinc-900 dark:focus:border-zinc-100"
                />
              </div>
              <button
                type="submit"
                disabled={loading || !urlInput.trim()}
                className="w-full py-2 text-xs font-medium bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 rounded transition-colors disabled:opacity-50"
              >
                {loading ? "Processing..." : "Analyze Image URL →"}
              </button>
            </form>
          )}

          {/* Bottom helper toggles */}
          <div className="flex items-center justify-between text-xs text-zinc-500 pt-2 border-t border-zinc-100 dark:border-zinc-800">
            <button
              type="button"
              onClick={() => setUrlMode(!urlMode)}
              className="hover:text-zinc-900 dark:hover:text-zinc-200 underline underline-offset-2"
            >
              {urlMode ? "← Upload file instead" : "Use Image URL"}
            </button>

            <button
              type="button"
              onClick={() => setShowOptions(!showOptions)}
              className="hover:text-zinc-900 dark:hover:text-zinc-200"
            >
              {showOptions ? "Hide options" : "Scale calibration"}
            </button>
          </div>

          {showOptions && (
            <div className="p-3 bg-zinc-50 dark:bg-zinc-950 rounded border border-zinc-200 dark:border-zinc-800 flex items-center space-x-3 text-xs">
              <span className="text-zinc-600 dark:text-zinc-400 font-mono">
                px/mm override:
              </span>
              <input
                type="number"
                step="0.1"
                min="0.5"
                placeholder="Auto (EAN-13)"
                value={manualPxPerMm}
                onChange={(e) => setManualPxPerMm(e.target.value)}
                className="w-28 px-2 py-1 text-xs font-mono bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded text-zinc-900 dark:text-zinc-100"
              />
            </div>
          )}
        </div>

        {/* Quick Demo Link */}
        <div className="text-center mt-6">
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
