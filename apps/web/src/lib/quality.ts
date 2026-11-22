/** Explicitly human-reviewed reporting and potential concern records. */

import { isUuid } from "./workspace";

export const DIMENSIONS = [
  "design", "sampling", "measurement", "psychometrics",
  "analysis", "precision", "limitations",
] as const;
export type QualityDimension = typeof DIMENSIONS[number];
export type ReportingJudgment =
  | "not_assessed" | "reported_in_full_text" | "unclear_after_review"
  | "not_reported_in_full_text" | "not_applicable";
export type ConcernJudgment =
  | "not_assessed" | "potential_concern" | "no_concern_identified";

export const DIMENSION_LABELS: Record<QualityDimension, string> = {
  design: "Study design",
  sampling: "Sampling and selection",
  measurement: "Measurement reporting",
  psychometrics: "Validity and reliability reporting",
  analysis: "Statistical methods and assumptions",
  precision: "Effect estimates and precision",
  limitations: "Limitations and possible biases",
};

export interface QualitySource {
  facet: "aim" | "method" | "sample" | "instruments" | "findings" | "limitations";
  locator: string;
  quote: string;
}
export interface QualityIndicator {
  dimension: QualityDimension;
  prompt: string;
  coverage: "excerpt_available" | "not_assessable_from_excerpts";
  source_excerpts: QualitySource[];
}
export interface QualityRevision {
  id: string;
  entry_id: string;
  dimension: QualityDimension;
  reporting: ReportingJudgment;
  concern: ConcernJudgment;
  checked_original: boolean;
  note: string;
  created_at: string;
}
export interface QualityChecklist {
  project_id: string;
  entry_id: string;
  document_title: string;
  indicators: QualityIndicator[];
  latest_reviews: QualityRevision[];
  caveat: string;
}

export interface QualityDraft {
  reporting: ReportingJudgment;
  concern: ConcernJudgment;
  checked_original: boolean;
  note: string;
}

export function defaultQualityDraft(): QualityDraft {
  return {
    reporting: "not_assessed", concern: "not_assessed",
    checked_original: false, note: "",
  };
}

export function isQualityRevision(value: unknown): value is QualityRevision {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const row = value as Partial<QualityRevision>;
  return typeof row.id === "string" && isUuid(row.id)
    && typeof row.entry_id === "string" && isUuid(row.entry_id)
    && DIMENSIONS.includes(row.dimension as QualityDimension)
    && ["not_assessed", "reported_in_full_text", "unclear_after_review",
      "not_reported_in_full_text", "not_applicable"].includes(row.reporting || "")
    && ["not_assessed", "potential_concern", "no_concern_identified"].includes(row.concern || "")
    && typeof row.checked_original === "boolean"
    && typeof row.note === "string" && row.note.length <= 1000
    && typeof row.created_at === "string";
}

export function isQualityChecklist(value: unknown): value is QualityChecklist {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const row = value as Partial<QualityChecklist>;
  if (
    typeof row.project_id !== "string" || !isUuid(row.project_id)
    || typeof row.entry_id !== "string" || !isUuid(row.entry_id)
    || typeof row.document_title !== "string"
    || typeof row.caveat !== "string"
    || !Array.isArray(row.latest_reviews) || !row.latest_reviews.every(isQualityRevision)
    || !Array.isArray(row.indicators) || row.indicators.length !== DIMENSIONS.length
  ) return false;
  const seen = new Set<QualityDimension>();
  return row.indicators.every((indicator: unknown) => {
    if (!indicator || typeof indicator !== "object" || Array.isArray(indicator)) return false;
    const item = indicator as Partial<QualityIndicator>;
    const dim = item.dimension as QualityDimension;
    if (
      !DIMENSIONS.includes(dim) || seen.has(dim)
      || typeof item.prompt !== "string"
      || !["excerpt_available", "not_assessable_from_excerpts"].includes(item.coverage || "")
      || !Array.isArray(item.source_excerpts) || item.source_excerpts.length > 2
    ) return false;
    seen.add(dim);
    return item.source_excerpts.every((source: unknown) => {
      if (!source || typeof source !== "object") return false;
      const src = source as Partial<QualitySource>;
      return ["aim", "method", "sample", "instruments", "findings", "limitations"]
        .includes(src.facet || "")
        && typeof src.locator === "string" && src.locator.length > 0
        && typeof src.quote === "string" && src.quote.length > 0;
    }) && (item.coverage === "excerpt_available" ? item.source_excerpts.length > 0
      : item.source_excerpts.length === 0);
  }) && seen.size === DIMENSIONS.length;
}

export function hasUnverifiedJudgment(draft: QualityDraft): boolean {
  return !draft.checked_original && (
    draft.reporting !== "not_assessed" || draft.concern !== "not_assessed"
  );
}

/**
 * An epoch-based guard for asynchronous review requests. Each study or project
 * selection invalidates every in-flight response, including A → B → A changes.
 */
export interface QualitySelectionToken {
  readonly generation: number;
  readonly projectId: string;
  readonly entryId: string;
}

export class QualitySelectionGuard {
  private generation = 0;

  capture(projectId: string, entryId: string): QualitySelectionToken {
    return { generation: this.generation, projectId, entryId };
  }

  invalidate(): void {
    this.generation += 1;
  }

  isCurrent(
    token: QualitySelectionToken,
    projectId: string,
    entryId: string,
  ): boolean {
    return token.generation === this.generation
      && token.projectId === projectId
      && token.entryId === entryId;
  }
}
