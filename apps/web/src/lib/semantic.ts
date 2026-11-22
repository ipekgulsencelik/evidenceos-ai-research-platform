/** Runtime validation for model-proposed, source-identified literature comparisons. */

import { isUuid } from "./workspace";

export type SemanticDimension = "population" | "study_design" | "measurement" | "findings";
export type ComparisonKind =
  | "possible_difference" | "possible_alignment" | "insufficient_context";

export interface SemanticReference {
  reference_id: string;
  entry_id: string;
  document_title: string;
  dimension: SemanticDimension;
  locator: string;
  quote: string;
}

export interface SemanticCandidate {
  dimension: SemanticDimension;
  kind: ComparisonKind;
  summary: string;
  research_question: string;
  references: SemanticReference[];
}

export interface SemanticGapReport {
  project_id: string;
  document_ids: string[];
  model: string;
  candidates: SemanticCandidate[];
  skipped_candidates: number;
  insufficient_dimensions: SemanticDimension[];
  caveat: string;
}

export const SEMANTIC_LABELS: Record<SemanticDimension, string> = {
  population: "Participant populations",
  study_design: "Study methods and design",
  measurement: "Scales and measurements",
  findings: "Research findings",
};

function dimension(value: unknown): value is SemanticDimension {
  return value === "population" || value === "study_design"
    || value === "measurement" || value === "findings";
}

function kind(value: unknown): value is ComparisonKind {
  return value === "possible_difference" || value === "possible_alignment"
    || value === "insufficient_context";
}

function isReference(value: unknown): value is SemanticReference {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const ref = value as Partial<SemanticReference>;
  return typeof ref.reference_id === "string" && ref.reference_id.length > 0
    && typeof ref.entry_id === "string" && isUuid(ref.entry_id)
    && typeof ref.document_title === "string" && dimension(ref.dimension)
    && typeof ref.locator === "string" && ref.locator.length > 0
    && typeof ref.quote === "string" && ref.quote.length > 0;
}

export function isSemanticGapReport(value: unknown): value is SemanticGapReport {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const report = value as Partial<SemanticGapReport>;
  return typeof report.project_id === "string" && isUuid(report.project_id)
    && Array.isArray(report.document_ids) && report.document_ids.length >= 2
    && report.document_ids.length <= 10
    && report.document_ids.every((id) => typeof id === "string" && isUuid(id))
    && typeof report.model === "string" && report.model.length > 0
    && typeof report.caveat === "string" && report.caveat.length > 0
    && typeof report.skipped_candidates === "number"
    && Number.isInteger(report.skipped_candidates) && report.skipped_candidates >= 0
    && Array.isArray(report.insufficient_dimensions)
    && report.insufficient_dimensions.every(dimension)
    && Array.isArray(report.candidates) && report.candidates.length <= 4
    && report.candidates.every((candidate) =>
      candidate !== null && typeof candidate === "object"
      && dimension(candidate.dimension) && kind(candidate.kind)
      && typeof candidate.summary === "string"
      && typeof candidate.research_question === "string"
      && Array.isArray(candidate.references) && candidate.references.length >= 2
      && candidate.references.length <= 10
      && candidate.references.every(isReference)
      && candidate.references.every((ref) => ref.dimension === candidate.dimension)
      && new Set(candidate.references.map((ref) => ref.entry_id)).size >= 2
    );
}
