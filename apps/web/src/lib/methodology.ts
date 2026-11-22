/** Runtime boundary for source-grounded methodology reviews. */

import { isUuid } from "./workspace";

export type MethodologyAspect =
  | "study_design" | "sampling" | "instruments" | "psychometrics"
  | "statistical_methods" | "effect_reporting" | "limitations";
export type MethodologyStatus =
  | "reported_in_excerpt" | "needs_review" | "not_assessable";

export interface MethodologySource {
  reference_id: string;
  facet: "method" | "sample" | "instruments" | "findings" | "limitations";
  locator: string;
  quote: string;
}
export interface MethodologyObservation {
  aspect: MethodologyAspect;
  status: MethodologyStatus;
  observation: string;
  review_question: string;
  sources: MethodologySource[];
}
export interface MethodologyReport {
  project_id: string;
  entry_id: string;
  document_title: string;
  model: string;
  observations: MethodologyObservation[];
  discarded_model_observations: number;
  caveat: string;
}

export const METHODOLOGY_LABELS: Record<MethodologyAspect, string> = {
  study_design: "Study design",
  sampling: "Sampling and participants",
  instruments: "Measurement instruments",
  psychometrics: "Validity and reliability evidence",
  statistical_methods: "Statistical methods",
  effect_reporting: "Effect sizes and results reporting",
  limitations: "Methodological limitations",
};
export const ASPECTS = Object.keys(METHODOLOGY_LABELS) as MethodologyAspect[];
const STATUS: MethodologyStatus[] = [
  "reported_in_excerpt", "needs_review", "not_assessable",
];

const SOURCE_FACETS: Record<MethodologyAspect, MethodologySource["facet"][]> = {
  study_design: ["method"],
  sampling: ["method", "sample"],
  instruments: ["instruments"],
  psychometrics: ["instruments"],
  statistical_methods: ["method", "findings"],
  effect_reporting: ["findings"],
  limitations: ["limitations"],
};

export function isMethodologyReport(value: unknown): value is MethodologyReport {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const result = value as Partial<MethodologyReport>;
  if (
    typeof result.project_id !== "string" || !isUuid(result.project_id)
    || typeof result.entry_id !== "string" || !isUuid(result.entry_id)
    || typeof result.document_title !== "string"
    || typeof result.model !== "string"
    || typeof result.caveat !== "string"
    || !Number.isInteger(result.discarded_model_observations)
    || (result.discarded_model_observations ?? -1) < 0
    || !Array.isArray(result.observations)
    || result.observations.length !== ASPECTS.length
  ) return false;

  const observed = new Set<MethodologyAspect>();
  return result.observations.every((item: unknown) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return false;
    const row = item as Partial<MethodologyObservation>;
    if (
      !ASPECTS.includes(row.aspect as MethodologyAspect)
      || observed.has(row.aspect as MethodologyAspect)
      || !STATUS.includes(row.status as MethodologyStatus)
      || typeof row.observation !== "string"
      || typeof row.review_question !== "string"
      || !Array.isArray(row.sources)
      || row.sources.length > 3
    ) return false;
    const aspect = row.aspect as MethodologyAspect;
    observed.add(aspect);
    if (row.status === "not_assessable" && row.sources.length !== 0) return false;
    if (row.status !== "not_assessable" && row.sources.length === 0) return false;
    const sourceIds = new Set<string>();
    return row.sources.every((source: unknown) => {
      if (!source || typeof source !== "object" || Array.isArray(source)) return false;
      const src = source as Partial<MethodologySource>;
      if (
        typeof src.reference_id !== "string"
        || sourceIds.has(src.reference_id)
        || !SOURCE_FACETS[aspect].includes(src.facet as MethodologySource["facet"])
        || src.reference_id !== "f:" + src.facet
        || typeof src.locator !== "string" || src.locator.length === 0
        || typeof src.quote !== "string" || src.quote.length === 0
      ) return false;
      sourceIds.add(src.reference_id);
      return true;
    });
  }) && observed.size === ASPECTS.length;
}
