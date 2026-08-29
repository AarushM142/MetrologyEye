"use client";

import { useState } from "react";

interface DropzoneProps {
  selectedFile: File | null;
  previewUrl: string | null;
  loading: boolean;
  onFileSelect: (file: File) => void;
  onClear: () => void;
  onAnalyze: () => void;
  onUrlAnalyze: (url: string) => void;
}

export function Dropzone({
  selectedFile,
  previewUrl,
  loading,
  onFileSelect,
  onClear,
  onAnalyze,
  onUrlAnalyze,
}: DropzoneProps) {
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [urlMode, setUrlMode] = useState<boolean>(false);
  const [urlInput, setUrlInput] = useState<string>("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const validateAndProcessFile = (file: File) => {
    setValidationError(null);
    const validTypes = ["image/jpeg", "image/png", "image/webp", "image/jpg"];
    if (!validTypes.includes(file.type)) {
      setValidationError("Invalid file type. Please upload a PNG, JPG, or WebP image.");
      return;
    }
    const maxSizeBytes = 12 * 1024 * 1024; // 12 MB
    if (file.size > maxSizeBytes) {
      setValidationError("File size exceeds 12 MB limit.");
      return;
    }
    onFileSelect(file);
  };

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
      validateAndProcessFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndProcessFile(e.target.files[0]);
    }
  };

  const handleUrlSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!urlInput.trim()) return;
    onUrlAnalyze(urlInput.trim());
  };

  return (
    <div className="w-full space-y-4">
      {validationError && (
        <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 rounded-lg text-xs text-rose-800 dark:text-rose-300 flex items-center justify-between">
          <span>{validationError}</span>
          <button
            type="button"
            onClick={() => setValidationError(null)}
            className="text-rose-600 hover:text-rose-900 dark:hover:text-rose-100"
          >
            ✕
          </button>
        </div>
      )}

      {!urlMode ? (
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-8 sm:p-10 transition-all flex flex-col items-center justify-center text-center ${
            dragActive
              ? "border-zinc-900 dark:border-zinc-100 bg-zinc-100/60 dark:bg-zinc-800/60 scale-[1.01]"
              : "border-zinc-200 dark:border-zinc-800 hover:border-zinc-400 dark:hover:border-zinc-600 bg-white dark:bg-zinc-900"
          }`}
        >
          {previewUrl ? (
            <div className="w-full flex flex-col items-center space-y-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl}
                alt="Label preview"
                className="max-h-60 rounded-lg border border-zinc-200 dark:border-zinc-800 object-contain shadow-xs"
              />
              <div className="text-xs font-mono text-zinc-500 flex items-center space-x-2">
                <span>{selectedFile?.name}</span>
                {selectedFile && (
                  <span className="text-[10px] text-zinc-400">
                    ({(selectedFile.size / (1024 * 1024)).toFixed(2)} MB)
                  </span>
                )}
              </div>
              <div className="flex items-center space-x-3 pt-2">
                <button
                  type="button"
                  onClick={onClear}
                  disabled={loading}
                  className="px-3.5 py-1.5 text-xs text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 border border-zinc-200 dark:border-zinc-700 rounded-lg transition-colors disabled:opacity-50"
                >
                  Clear
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={onAnalyze}
                  className="px-6 py-1.5 text-xs font-medium bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 rounded-lg transition-colors disabled:opacity-50 shadow-xs flex items-center space-x-2"
                >
                  {loading && (
                    <span className="w-3 h-3 border-2 border-white dark:border-zinc-950 border-t-transparent rounded-full animate-spin" />
                  )}
                  <span>{loading ? "Analyzing..." : "Analyze Label →"}</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="w-12 h-12 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center mx-auto text-zinc-600 dark:text-zinc-300">
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.75}
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                  />
                </svg>
              </div>

              <div className="space-y-1">
                <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                  Drop package photo here, or browse
                </p>
                <p className="text-xs text-zinc-400">
                  PNG, JPG, WebP up to 12 MB
                </p>
              </div>

              <div className="flex items-center justify-center space-x-3 pt-1">
                <label className="cursor-pointer px-4 py-2 text-xs font-medium bg-zinc-950 dark:bg-zinc-100 text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 rounded-lg transition-colors shadow-xs">
                  Choose File
                  <input
                    type="file"
                    accept="image/png, image/jpeg, image/webp"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </label>
                <label className="cursor-pointer px-4 py-2 text-xs font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-lg transition-colors">
                  📷 Camera
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
        <form onSubmit={handleUrlSubmit} className="space-y-4 bg-white dark:bg-zinc-900 p-6 rounded-xl border border-zinc-200 dark:border-zinc-800 shadow-xs">
          <div className="space-y-1.5">
            <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300">
              Product Image URL
            </label>
            <input
              type="url"
              placeholder="https://example.com/product-image.jpg"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-zinc-50 dark:bg-zinc-950 border border-zinc-300 dark:border-zinc-700 rounded-lg text-zinc-900 dark:text-zinc-100 focus:outline-none focus:border-zinc-900 dark:focus:border-zinc-100"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !urlInput.trim()}
            className="w-full py-2 text-xs font-medium bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center space-x-2"
          >
            {loading && (
              <span className="w-3 h-3 border-2 border-white dark:border-zinc-950 border-t-transparent rounded-full animate-spin" />
            )}
            <span>{loading ? "Processing..." : "Analyze Image URL →"}</span>
          </button>
        </form>
      )}

      {/* Helper Toggle */}
      <div className="flex items-center justify-between text-xs text-zinc-500 pt-1">
        <button
          type="button"
          onClick={() => setUrlMode(!urlMode)}
          className="hover:text-zinc-900 dark:hover:text-zinc-200 underline underline-offset-2 transition-colors"
        >
          {urlMode ? "← Upload file instead" : "Use Image URL"}
        </button>
        <span className="text-[11px] text-zinc-400">
          Supports ID-1 Calibration Card & EAN-13 Barcode Scale
        </span>
      </div>
    </div>
  );
}
