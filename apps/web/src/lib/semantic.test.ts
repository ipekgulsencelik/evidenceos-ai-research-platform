import assert from "node:assert/strict";
import test from "node:test";

import { isSemanticGapReport, SEMANTIC_LABELS } from "./semantic.ts";

const project = "a2a8c77a-b3ac-4d17-8e94-1234567890ab";
const a = "b2a8c77a-b3ac-4d17-8e94-1234567890ab";
const b = "c2a8c77a-b3ac-4d17-8e94-1234567890ab";
const report = {
  project_id: project,
  document_ids: [a, b],
  model: "test",
  skipped_candidates: 0,
  insufficient_dimensions: ["measurement"],
  caveat: "Not a genuine literature gap.",
  candidates: [{
    dimension: "population",
    kind: "possible_difference",
    summary: "Different groups may be described.",
    research_question: "Are participant groups comparable?",
    references: [
      { reference_id: "s1:sample", entry_id: a, document_title: "A",
        dimension: "population", locator: "PDF page 1", quote: "first quote" },
      { reference_id: "s2:sample", entry_id: b, document_title: "B",
        dimension: "population", locator: "PDF page 2", quote: "second quote" },
    ],
  }],
};

test("valid semantic reports preserve the source references", () => {
  assert.equal(isSemanticGapReport(report), true);
  assert.equal(SEMANTIC_LABELS.population, "Participant populations");
});

test("reject invented source IDs, missing evidence and wrong categories", () => {
  assert.equal(isSemanticGapReport({ ...report, project_id: "invalid" }), false);
  assert.equal(isSemanticGapReport({ ...report, candidates: [
    { ...report.candidates[0], references: [report.candidates[0].references[0]] },
  ] }), false);
  assert.equal(isSemanticGapReport({ ...report, candidates: [
    { ...report.candidates[0], references: [
      report.candidates[0].references[0],
      { ...report.candidates[0].references[1], dimension: "findings" },
    ] },
  ] }), false);
  assert.equal(isSemanticGapReport({ ...report, candidates: [
    { ...report.candidates[0], references: [
      report.candidates[0].references[0],
      { ...report.candidates[0].references[1], entry_id: a },
    ] },
  ] }), false);
});
