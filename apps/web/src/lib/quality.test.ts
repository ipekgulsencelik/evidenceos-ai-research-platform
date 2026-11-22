import assert from "node:assert/strict";
import test from "node:test";

import {
  defaultQualityDraft, DIMENSIONS, hasUnverifiedJudgment,
  isQualityChecklist, isQualityRevision, QualitySelectionGuard,
} from "./quality.ts";

const project = "a2a8c77a-b3ac-4d17-8e94-1234567890ab";
const entry = "b2a8c77a-b3ac-4d17-8e94-1234567890ab";
const checklist = {
  project_id: project, entry_id: entry, document_title: "Sample",
  latest_reviews: [], caveat: "Not a quality score.",
  indicators: DIMENSIONS.map((dimension) => ({
    dimension, prompt: "Check the full text",
    coverage: "not_assessable_from_excerpts", source_excerpts: [],
  })),
};

test("accepts a complete seven-dimension checklist", () => {
  assert.equal(isQualityChecklist(checklist), true);
  assert.equal(isQualityChecklist({
    ...checklist, indicators: checklist.indicators.slice(0, 6),
  }), false);
});

test("rejects conflicting or invented quote coverage", () => {
  assert.equal(isQualityChecklist({
    ...checklist,
    indicators: [{ ...checklist.indicators[0], coverage: "excerpt_available" },
      ...checklist.indicators.slice(1)],
  }), false);
  assert.equal(isQualityRevision({ id: "bad" }), false);
});

test("human judgments require explicit original-paper check", () => {
  assert.equal(hasUnverifiedJudgment(defaultQualityDraft()), false);
  assert.equal(hasUnverifiedJudgment({
    ...defaultQualityDraft(), reporting: "not_reported_in_full_text",
  }), true);
  assert.equal(hasUnverifiedJudgment({
    ...defaultQualityDraft(),
    checked_original: true, concern: "potential_concern",
  }), false);
});

test("async selection guard discards previous studies and project responses", () => {
  const gate = new QualitySelectionGuard();
  const first = gate.capture(project, entry);
  assert.equal(gate.isCurrent(first, project, entry), true);
  assert.equal(gate.isCurrent(first, project, "another-entry"), false);
  assert.equal(gate.isCurrent(first, "another-project", entry), false);

  gate.invalidate(); // A → B
  assert.equal(gate.isCurrent(first, project, entry), false);
  const second = gate.capture(project, "another-entry");
  assert.equal(gate.isCurrent(second, project, "another-entry"), true);

  gate.invalidate(); // B → A: matching IDs must not revive an old response
  const returned = gate.capture(project, entry);
  assert.equal(gate.isCurrent(first, project, entry), false);
  assert.equal(gate.isCurrent(second, project, "another-entry"), false);
  assert.equal(gate.isCurrent(returned, project, entry), true);

  gate.invalidate(); // Switch project while the same study ID is still selected
  assert.equal(gate.isCurrent(returned, project, entry), false);
});
