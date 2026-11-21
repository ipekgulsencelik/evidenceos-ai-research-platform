/** Untrusted, page-grounded PDF retrieval metadata. No claim verification. */

import type { EvidenceSource } from "./evidence";

export const MAX_PDF_BYTES = 8 * 1024 * 1024;

export interface PdfCandidate extends EvidenceSource {
  matched_terms: string[];
  lexical_score: number;
}

export interface PdfReview {
  title: string;
  sha256: string;
  page_count: number;
  text_page_count: number;
  passages: PdfCandidate[];
  caveat: string;
}

export function validatePdfUpload(
  file: Pick<File, "name" | "size"> | null,
  claim: string,
): string | null {
  if (claim.trim().length < 10 || claim.trim().length > 500)
    return "Write a research claim between 10 and 500 characters first.";
  if (!file) return "Select a PDF before extracting passages.";
  if (!file.name.toLowerCase().endsWith(".pdf"))
    return "Select a .pdf document.";
  if (file.size === 0 || file.size > MAX_PDF_BYTES)
    return "PDF must be nonempty and at most 8 MiB.";
  return null;
}

export function isPdfReview(value: unknown): value is PdfReview {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const item = value as Partial<PdfReview>;
  return typeof item.title === "string" && typeof item.page_count === "number"
    && typeof item.caveat === "string" && Array.isArray(item.passages)
    && item.passages.length <= 3 && item.passages.every((p) =>
      p && typeof p.source_id === "string" && typeof p.title === "string"
      && typeof p.passage === "string" && typeof p.locator === "string"
      && typeof p.lexical_score === "number" && Array.isArray(p.matched_terms)
    );
}
