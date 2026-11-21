/** Public API contracts. They mirror the existing FastAPI schemas, not provider payloads. */
export interface AcademicWork {
  source_id: string;
  title: string;
  doi: string | null;
  publication_year: number | null;
  authors: string[];
  source_url: string;
}

export type CitationStatus = "verified" | "title_mismatch" | "not_found_in_crossref";

export interface CitationMetadata {
  doi: string;
  title: string;
  publication_year: number | null;
  source_url: string;
}

export interface CitationCheck {
  doi: string;
  status: CitationStatus;
  metadata: CitationMetadata | null;
}

export function validateSearch(query: string, limit: number): string | null {
  const cleaned = query.trim();
  if (cleaned.length < 3 || cleaned.length > 200) {
    return "Enter a research topic between 3 and 200 characters.";
  }
  if (!Number.isInteger(limit) || limit < 1 || limit > 25) {
    return "Choose between 1 and 25 results.";
  }
  return null;
}

export function validateCitation(doi: string, title: string): string | null {
  const cleaned = doi.trim();
  if (cleaned.length < 7 || cleaned.length > 300) {
    return "Enter a DOI between 7 and 300 characters.";
  }
  if (title.trim().length > 500) {
    return "Title must be at most 500 characters.";
  }
  return null;
}

export function getPublicationRange(works: AcademicWork[]): string {
  const years = works
    .map((work) => work.publication_year)
    .filter((value): value is number => value !== null && Number.isFinite(value));
  if (years.length === 0) return "—";
  const start = Math.min(...years);
  const end = Math.max(...years);
  return start === end ? String(start) : `${start}–${end}`;
}

export function getShortAuthors(authors: string[]): string {
  if (!authors.length) return "Authors not listed";
  if (authors.length <= 2) return authors.join(", ");
  return `${authors[0]} et al.`;
}

export function getResponseError(status: number, detail?: string): string {
  if (status === 503) return "OpenAlex is not configured. Add your API key to the local .env file and restart the API.";
  if (status === 502 || status === 504) return "The research provider is temporarily unavailable. Try again later.";
  if (status === 429) return "Too many requests. Please try again later.";
  if (status === 400 || status === 422) return detail || "Please check the submitted fields.";
  return "The request could not be completed. Please try again.";
}
