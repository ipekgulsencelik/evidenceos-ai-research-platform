import assert from "node:assert/strict";
import test from "node:test";

import { ASPECTS, isMethodologyReport } from "./methodology.ts";

const projectId = "a2a8c77a-b3ac-4d17-8e94-1234567890ab";
const entryId = "b2a8c77a-b3ac-4d17-8e94-1234567890ab";

const report = {
  project_id: projectId,
  entry_id: entryId,
  document_title: "Sample study",
  model: "test-model",
  discarded_model_observations: 0,
  caveat: "Preliminary triage only.",
  observations: ASPECTS.map((aspect) => ({
    aspect,
    status: "not_assessable",
    observation: "Not enough detail from this excerpt.",
    review_question: "What does the full article report?",
    sources: [],
  })),
};

test("accepts seven complete unassessable categories", () => {
  assert.equal(isMethodologyReport(report), true);
});

test("rejects invented citations, mismatched categories and missing entries", () => {
  assert.equal(isMethodologyReport({ ...report, project_id: "wrong" }), false);
  assert.equal(isMethodologyReport({
    ...report, observations: report.observations.slice(0, 6),
  }), false);

  const first = {
    ...report.observations[0],
    status: "reported_in_excerpt",
    sources: [{
      reference_id: "f:instruments",
      facet: "instruments",
      quote: "Authors report a scale.",
      locator: "PDF page 2",
    }],
  };
  assert.equal(isMethodologyReport({
    ...report, observations: [first, ...report.observations.slice(1)],
  }), false);
  assert.equal(isMethodologyReport({
    ...report, observations: [{ ...first, sources: [] }, ...report.observations.slice(1)],
  }), false);
});
