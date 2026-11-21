/** Server-only outbound API transport. Browser clients never learn the backend URL. */
import type { AcademicWork, CitationCheck } from "./academic";

type BackendPayload = AcademicWork[] | CitationCheck;

export interface GatewayResult {
  status: number;
  body: BackendPayload | { detail: string };
}

function endpoint(path: string): URL {
  // Only literal paths from our route handlers are passed here. Never user-provided URLs.
  return new URL(path, process.env.BACKEND_API_URL || "http://127.0.0.1:8001");
}

export async function callBackend(path: string, init?: RequestInit): Promise<GatewayResult> {
  try {
    const upstream = await fetch(endpoint(path), {
      ...init,
      headers: { Accept: "application/json", ...(init?.headers || {}) },
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    const payload: unknown = await upstream.json().catch(() => null);
    if (!payload || typeof payload !== "object") {
      return { status: 502, body: { detail: "Unexpected response from research service." } };
    }
    if (!upstream.ok) {
      const value = "detail" in payload ? (payload as { detail: unknown }).detail : null;
      return {
        status: upstream.status >= 400 && upstream.status < 600 ? upstream.status : 502,
        body: { detail: typeof value === "string" ? value : "Research service returned an error." },
      };
    }
    return { status: upstream.status, body: payload as BackendPayload };
  } catch {
    return { status: 502, body: { detail: "Cannot connect to the research service." } };
  }
}
