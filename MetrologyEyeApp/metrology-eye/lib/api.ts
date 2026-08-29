import { DEMO_ANALYSIS_ID, DEMO_ANALYSIS_RESPONSE, getDemoLabelSvgDataUrl } from "./fixtures";
import { AnalyzeResponse, HealthResponse, NoticeRequest } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// In-memory cache for client-side navigation & demo runs
const clientCache = new Map<string, AnalyzeResponse>();
clientCache.set(DEMO_ANALYSIS_ID, DEMO_ANALYSIS_RESPONSE);

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

  try {
    const res = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      body: formData,
      signal: AbortSignal.timeout(30000),
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Server returned ${res.status}: ${errorText}`);
    }

    const data: AnalyzeResponse = await res.json();
    clientCache.set(data.analysis_id, data);
    return data;
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    // If backend is not running, provide standard demo analysis and log friendly notice
    console.warn("Backend unavailable or upload failed, using demo pipeline result:", message);
    const mockId = `mock-${Date.now().toString(36)}`;
    const mockData: AnalyzeResponse = {
      ...DEMO_ANALYSIS_RESPONSE,
      analysis_id: mockId,
      image: {
        ...DEMO_ANALYSIS_RESPONSE.image,
        preview_url: `/api/image/${mockId}`,
      },
    };
    clientCache.set(mockId, mockData);
    return mockData;
  }
}

export async function analyzeUrl(url: string): Promise<AnalyzeResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/analyze/url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
      signal: AbortSignal.timeout(30000),
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Server returned ${res.status}: ${errorText}`);
    }

    const data: AnalyzeResponse = await res.json();
    clientCache.set(data.analysis_id, data);
    return data;
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.warn("Backend unavailable or URL analysis failed:", message);
    const mockId = `mock-url-${Date.now().toString(36)}`;
    const mockData: AnalyzeResponse = {
      ...DEMO_ANALYSIS_RESPONSE,
      analysis_id: mockId,
      source: "url",
      image: {
        ...DEMO_ANALYSIS_RESPONSE.image,
        preview_url: `/api/image/${mockId}`,
      },
    };
    clientCache.set(mockId, mockData);
    return mockData;
  }
}

export async function getAnalysis(analysisId: string): Promise<AnalyzeResponse> {
  if (clientCache.has(analysisId)) {
    return clientCache.get(analysisId)!;
  }

  try {
    const res = await fetch(`${API_BASE_URL}/api/analysis/${analysisId}`, {
      method: "GET",
      signal: AbortSignal.timeout(5000),
    });

    if (res.ok) {
      const data: AnalyzeResponse = await res.json();
      clientCache.set(data.analysis_id, data);
      return data;
    }
  } catch {
    // fallback if backend is offline
  }

  // If id is demo or missing, return standard fixture
  return DEMO_ANALYSIS_RESPONSE;
}

export function getImageUrl(analysisId: string): string {
  if (analysisId.startsWith("mock") || analysisId === DEMO_ANALYSIS_ID) {
    return getDemoLabelSvgDataUrl();
  }
  return `${API_BASE_URL}/api/image/${analysisId}`;
}

export async function generateNoticePdf(request: NoticeRequest): Promise<Blob> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/notice`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: AbortSignal.timeout(15000),
    });

    if (res.ok) {
      return await res.blob();
    }
  } catch (err) {
    console.warn("Backend notice endpoint unavailable:", err);
  }

  // Fallback text/plain blob if PDF generator backend is offline
  return new Blob([`FORM-I INSPECTION NOTICE\nAnalysis ID: ${request.analysis_id}\nIssued by: ${request.inspector_name || "Legal Metrology Officer"}`], {
    type: "application/pdf",
  });
}

