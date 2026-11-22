/** Runtime contracts for project-bound local research catalog and gap comparison. */

import { isSavedLiteratureEntry, isUuid } from "./workspace";
import type { SavedLiteratureEntry } from "./workspace";

export type ReadingStatus = "to_read" | "reading" | "reviewed";

export interface LibraryMetadata {
  entry_id: string;
  status: ReadingStatus;
  tags: string[];
  updated_at: string;
}

export interface LibraryItem {
  entry: SavedLiteratureEntry;
  metadata: LibraryMetadata;
}

export interface GapReference {
  entry_id: string;
  document_title: string;
  locator: string;
  quote: string;
  interpretation: string;
}

export interface GapCandidate {
  facet: "aim" | "method" | "sample" | "instruments" | "findings" | "limitations";
  grounded_count: number;
  total_count: number;
  not_identified_entry_ids: string[];
  rejected_entry_ids: string[];
  references: GapReference[];
  recommendation: string;
}

export interface GapComparison {
  project_id: string;
  document_ids: string[];
  candidates: GapCandidate[];
  caveat: string;
}

export function isLibraryMetadata(value: unknown): value is LibraryMetadata {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const data = value as Partial<LibraryMetadata>;
  return typeof data.entry_id === "string" && isUuid(data.entry_id)
    && ["to_read", "reading", "reviewed"].includes(data.status || "")
    && Array.isArray(data.tags) && data.tags.length <= 8
    && data.tags.every((tag) => typeof tag === "string" && tag.length <= 32)
    && typeof data.updated_at === "string";
}

export function isLibraryItem(value: unknown): value is LibraryItem {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const obj = value as Partial<LibraryItem>;
  return isSavedLiteratureEntry(obj.entry) && isLibraryMetadata(obj.metadata)
    && obj.entry.id === obj.metadata.entry_id;
}

export function isGapComparison(value: unknown): value is GapComparison {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const obj = value as Partial<GapComparison>;
  return typeof obj.project_id === "string" && isUuid(obj.project_id)
    && Array.isArray(obj.document_ids) && obj.document_ids.length >= 2
    && obj.document_ids.every((id) => typeof id === "string" && isUuid(id))
    && typeof obj.caveat === "string" && Array.isArray(obj.candidates)
    && obj.candidates.length <= 6 && obj.candidates.every((c) =>
      c && ["aim", "method", "sample", "instruments", "findings", "limitations"].includes(c.facet)
      && typeof c.grounded_count === "number" && typeof c.total_count === "number"
      && typeof c.recommendation === "string"
      && Array.isArray(c.not_identified_entry_ids) && Array.isArray(c.rejected_entry_ids)
      && Array.isArray(c.references)
      && c.references.every((r) => r && typeof r.quote === "string"
        && typeof r.locator === "string" && typeof r.document_title === "string"
        && typeof r.entry_id === "string" && isUuid(r.entry_id))
    );
}

export function validateTags(tags: string[]): string | null {
  if (tags.length > 8) return "Use up to 8 tags.";
  if (tags.some((tag) => !/^[\p{L}\p{N}_\- ]{1,32}$/u.test(tag.trim()))) {
    return "Each tag must have 1–32 letters, digits, spaces, _ or -.";
  }
  return null;
}

export function filterLibrary(
  rows: LibraryItem[], query: string, status: ReadingStatus | "all", tag: string,
): LibraryItem[] {
  const q = query.trim().toLocaleLowerCase();
  const t = tag.trim().toLocaleLowerCase();
  return rows.filter((item) =>
    (!q || item.entry.profile.document_title.toLocaleLowerCase().includes(q))
    && (status === "all" || item.metadata.status === status)
    && (!t || item.metadata.tags.some((label) => label.toLocaleLowerCase() === t))
  );
}
