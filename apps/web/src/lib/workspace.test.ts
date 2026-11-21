import assert from "node:assert/strict";
import test from "node:test";

import {
  isResearchProject, isReviewRevision, isSavedLiteratureEntry,
  isUuid, latestReviews, validateProjectTitle,
} from "./workspace.ts";

test("project and UUID validation", () => {
  const id = "b2a8c77a-b3ac-4d17-8e94-1234567890ab";
  assert.equal(isUuid(id), true);
  assert.equal(isUuid("../etc/passwd"), false);
  assert.equal(isResearchProject({ id, title: "My thesis", domain: "academic", created_at: "" }), true);
  assert.equal(isResearchProject({ id: "wrong", title: "X", domain: "academic" }), false);
  assert.match(validateProjectTitle("x") || "", /3–160/);
  assert.equal(validateProjectTitle("AI in adolescence"), null);
});

test("workspace response guards reject malformed profiles and revisions", () => {
  const id = "b2a8c77a-b3ac-4d17-8e94-1234567890ab";
  assert.equal(isSavedLiteratureEntry({ id, project_id: id, profile: null }), false);
  const sample = {
    id, entry_id: id, facet: "limitations",
    corrected_value: "Corrected", note: "Check PDF",
    reviewed: true, created_at: "2026-11-22T00:00:00+00:00",
  };
  assert.equal(isReviewRevision(sample), true);
  assert.equal(isReviewRevision({ ...sample, facet: "made-up" }), false);
  assert.equal(isReviewRevision({ ...sample, reviewed: "true" }), false);
});

test("latest revisions win without overwriting other facets", () => {
  const id = "b2a8c77a-b3ac-4d17-8e94-1234567890ab";
  const make = (text: string) => ({
    id, entry_id: id, facet: "aim" as const, corrected_value: text,
    note: "", reviewed: false, created_at: "2026-11-22T00:00:00+00:00",
  });
  const reviews = latestReviews([make("newer"), make("older")]);
  assert.equal(reviews.aim?.corrected_value, "newer");
  assert.equal(reviews.limitations, undefined);
});
