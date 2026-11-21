import type { AcademicWork } from "./academic";

export type Verdict = "supports" | "contradicts" | "insufficient";
export interface EvidenceSource {
  source_id: string;
  title: string;
  passage: string;
  locator: string | null;
}
export interface EvidenceRequest {
  claim: string;
  sources: EvidenceSource[];
}
export interface EvidenceRow {
  source_id: string;
  title: string;
  locator: string | null;
  verdict: Verdict;
  quote: string | null;
  explanation: string;
}
export interface EvidenceReport {
  claim: string;
  model: string;
  rows: EvidenceRow[];
  caveat: string;
}

export function validateEvidenceRequest(input: unknown): string | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return "Expected a JSON object.";
  const value = input as Record<string, unknown>;
  if (typeof value.claim !== "string" || value.claim.trim().length < 10 || value.claim.trim().length > 500)
    return "Claim must be between 10 and 500 characters.";
  if (!Array.isArray(value.sources) || value.sources.length < 1 || value.sources.length > 3)
    return "Provide one to three source passages.";
  const seen = new Set<string>();
  for (const source of value.sources) {
    if (!source || typeof source !== "object" || Array.isArray(source)) return "Invalid source.";
    const item = source as Record<string, unknown>;
    if (typeof item.source_id !== "string" || item.source_id.trim().length < 1 ||
        item.source_id.length > 150 || seen.has(item.source_id))
      return "Each source needs a unique identifier (max 150 characters).";
    seen.add(item.source_id);
    if (typeof item.title !== "string" || item.title.trim().length < 3 || item.title.trim().length > 300)
      return "Each title must contain 3–300 characters.";
    if (typeof item.passage !== "string" || item.passage.trim().length < 30 ||
        item.passage.trim().length > 4000)
      return "Each passage must contain 30–4000 characters.";
    if (item.locator !== null && item.locator !== undefined &&
        (typeof item.locator !== "string" || item.locator.length > 200))
      return "Source location must be text (max 200 characters).";
  }
  return null;
}

function csvCell(value: string): string {
  // Prevent spreadsheet formula injection from untrusted publication metadata.
  const safe = /^[\s]*[=+@-]/.test(value) ? "'" + value : value;
  return '"' + safe.replaceAll('"', '""') + '"';
}

export function literatureCsv(works: AcademicWork[]): string {
  const rows = works.map((work) => [
    work.title,
    work.authors.join("; "),
    work.publication_year === null ? "" : String(work.publication_year),
    work.doi || "",
    work.source_url,
  ]);
  return [["Title", "Authors", "Year", "DOI", "Source"], ...rows]
    .map((row) => row.map(csvCell).join(",")).join("\r\n") + "\r\n";
}
