import assert from "node:assert/strict";
import test from "node:test";

import {
  filterLibrary, isGapComparison, isLibraryItem, validateTags,
} from "./research-library.ts";
import type { LibraryItem } from "./research-library.ts";

const id = "b2a8c77a-b3ac-4d17-8e94-1234567890ab";

test("reject invalid catalog or gap server responses", () => {
  assert.equal(isLibraryItem(null), false);
  assert.equal(isLibraryItem({ entry: {}, metadata: {} }), false);
  assert.equal(isGapComparison({
    project_id: id, document_ids: [id, id], candidates: [], caveat: "test",
  }), true);
  assert.equal(isGapComparison({
    project_id: id, document_ids: [id], candidates: [], caveat: "test",
  }), false);
});

test("validate tags and filter by reading state", () => {
  assert.equal(validateTags(["adolescent", "AI-ethics"]), null);
  assert.match(validateTags(["<script>"]) || "", /tag/);
  assert.match(validateTags(Array(9).fill("tag")) || "", /8 tags/);

  const row = {
    entry: { id, profile: { document_title: "Adolescent AI" } },
    metadata: { entry_id: id, status: "reviewed", tags: ["Ethics"] },
  } as LibraryItem;
  assert.deepEqual(filterLibrary([row], "adolescent", "reviewed", "ethics"), [row]);
  assert.deepEqual(filterLibrary([row], "other", "reviewed", "ethics"), []);
  assert.deepEqual(filterLibrary([row], "", "reading", ""), []);
});
