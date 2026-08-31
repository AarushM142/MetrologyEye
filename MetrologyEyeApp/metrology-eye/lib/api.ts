import { AnalyzeResponse, HealthResponse, NoticeRequest } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// In-memory cache for client-side navigation (real results only)
const clientCache = new Map<string, AnalyzeResponse>();

export async function checkBackendHealth(): Promise<HealthResponse | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, {
      method: "GET",
      signal: AbortSignal.timeout(2000),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function analyzeUpload(
  file: File,
  manualPxPerMm?: number
): Promise<AnalyzeResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (manualPxPerMm && manualPxPerMm > 0) {
    formData.append("manual_px_per_mm", manualPxPerMm.toString());
  }

  const url = `${API_BASE_URL}/api/analyze`;
  console.log(`[MetrologyEye] POST ${url} | file=${file.name} size=${file.size}`);

  const res = await fetch(url, {
    method: "POST",
    body: formData,
    signal: AbortSignal.timeout(120000),
  });

  console.log(`[MetrologyEye] Response: ${res.status} ${res.statusText}`);

  if (!res.ok) {
    const errorText = await res.text();
    console.error(`[MetrologyEye] Error body: ${errorText}`);
    throw new Error(`Server returned ${res.status}: ${errorText}`);
  }

  const data: AnalyzeResponse = await res.json();
  console.log(`[MetrologyEye] ✓ Analysis ID: ${data.analysis_id}`);
  clientCache.set(data.analysis_id, data);
  return data;
}

export async function analyzeUrl(url: string): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE_URL}/api/analyze/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
    signal: AbortSignal.timeout(60000),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Server returned ${res.status}: ${errorText}`);
  }

  const data: AnalyzeResponse = await res.json();
  clientCache.set(data.analysis_id, data);
  return data;
}

export async function getAnalysis(analysisId: string): Promise<AnalyzeResponse> {
  if (clientCache.has(analysisId)) {
    return clientCache.get(analysisId)!;
  }

  const res = await fetch(`${API_BASE_URL}/api/analysis/${analysisId}`, {
    method: "GET",
    signal: AbortSignal.timeout(10000),
  });

  if (!res.ok) {
    throw new Error(`Analysis not found (${res.status})`);
  }

  const data: AnalyzeResponse = await res.json();
  clientCache.set(data.analysis_id, data);
  return data;
}

export function getImageUrl(analysisId: string): string {
  return `${API_BASE_URL}/api/image/${analysisId}`;
}

export async function generateNoticePdf(request: NoticeRequest): Promise<Blob> {
  const res = await fetch(`${API_BASE_URL}/api/notice`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: AbortSignal.timeout(15000),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Notice generation failed (${res.status}): ${errorText}`);
  }

  return await res.blob();
}
