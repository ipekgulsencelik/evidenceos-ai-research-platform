/** Typed, minimal browser contracts for the localhost-only persistent workspace. */

import type { HumanReview, LiteratureProfile } from "./literature";

export interface ResearchProject {
  id: string;
  title: string;
  domain: "academic" | "legal";
  created_at: string;
}

export interface SavedLiteratureEntry {
  id: string;
  project_id: string;
  created_at: string;
  profile: LiteratureProfile;
}

export interface ReviewRevision {
  id: string;
  entry_id: string;
  facet: "aim" | "method" | "sample" | "instruments" | "findings" | "limitations";
  corrected_value: string;
  note: string;
  reviewed: boolean;
  created_at: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value: string): boolean {
  return UUID.test(value);
}

export function isResearchProject(value: unknown): value is ResearchProject {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const entry = value as Partial<ResearchProject>;
  return typeof entry.id === "string" && isUuid(entry.id)
    && typeof entry.title === "string"
    && (entry.domain === "academic" || entry.domain === "legal")
    && typeof entry.created_at === "string";
}

export function isSavedLiteratureEntry(value: unknown): value is SavedLiteratureEntry {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const entry = value as Partial<SavedLiteratureEntry>;
  // Existing scientific profile boundary checks facet structure and status codes.
  return typeof entry.id === "string" && isUuid(entry.id)
    && typeof entry.project_id === "string" && isUuid(entry.project_id)
    && typeof entry.created_at === "string"
    && isLiteratureProfileShape(entry.profile);
}

function isLiteratureProfileShape(value: unknown): value is LiteratureProfile {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const report = value as Partial<LiteratureProfile>;
  return typeof report.sha256 === "string" && /^[0-9a-f]{64}$/i.test(report.sha256)
    && typeof report.document_title === "string"
    && typeof report.page_count === "number"
    && Array.isArray(report.findings)
    && report.findings.length === 6;
}

export function isReviewRevision(value: unknown): value is ReviewRevision {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const item = value as Partial<ReviewRevision>;
  return typeof item.id === "string" && isUuid(item.id)
    && typeof item.entry_id === "string" && isUuid(item.entry_id)
    && typeof item.facet === "string"
    && ["aim", "method", "sample", "instruments", "findings", "limitations"]
      .includes(item.facet)
    && typeof item.corrected_value === "string"
    && typeof item.note === "string"
    && typeof item.reviewed === "boolean"
    && typeof item.created_at === "string";
}

export function latestReviews(revisions: ReviewRevision[]): Record<ReviewRevision["facet"], HumanReview | undefined> {
  const found: Partial<Record<ReviewRevision["facet"], HumanReview>> = {};
  for (const revision of revisions) {
    if (!found[revision.facet]) {
      found[revision.facet] = {
        corrected_value: revision.corrected_value,
        note: revision.note,
        reviewed: revision.reviewed,
      };
    }
  }
  return found as Record<ReviewRevision["facet"], HumanReview | undefined>;
}

export function validateProjectTitle(title: string): string | null {
  return title.trim().length >= 3 && title.trim().length <= 160
    ? null : "Project title must contain 3–160 characters.";
}
