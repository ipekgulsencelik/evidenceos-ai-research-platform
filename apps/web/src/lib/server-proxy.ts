/** Server-only outbound API transport. Browser clients never learn the backend URL. */
import type { AcademicWork, CitationCheck } from "./academic";
import type { EvidenceReport } from "./evidence";
import type { PdfReview } from "./document";
import type { LiteratureProfile } from "./literature";
import type { ResearchProject, ReviewRevision, SavedLiteratureEntry } from "./workspace";
import type { GapComparison, LibraryItem, LibraryMetadata } from "./research-library";
import type { SemanticGapReport } from "./semantic";
import type { MethodologyReport } from "./methodology";
import type { QualityChecklist, QualityRevision } from "./quality";

type BackendPayload =
  | AcademicWork[] | CitationCheck | EvidenceReport | PdfReview | LiteratureProfile
  | ResearchProject | ResearchProject[] | ReviewRevision | ReviewRevision[]
  | SavedLiteratureEntry | SavedLiteratureEntry[]
  | LibraryItem[] | LibraryMetadata | GapComparison | SemanticGapReport | MethodologyReport | QualityChecklist | QualityRevision | QualityRevision[];

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
      signal: AbortSignal.timeout(path === "/api/v1/evidence/assess" ||
        path.endsWith("/literature/analyze-pdf") ||
        path.endsWith("/semantic-gaps") ||
        path.endsWith("/methodology-review") ? 90000 : 30000),
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
