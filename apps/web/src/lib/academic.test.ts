import assert from "node:assert/strict";
import test from "node:test";

import { getPublicationRange, getResponseError, getShortAuthors, validateCitation, validateSearch } from "./academic.ts";
import type { AcademicWork } from "./academic.ts";

test("search requires bounded query and result limit", () => {
  assert.match(validateSearch(" ", 10) || "", /between 3 and 200/);
  assert.equal(validateSearch("adolescent AI", 5), null);
  assert.match(validateSearch("ab", 5) || "", /between/);
  assert.match(validateSearch("research", 0) || "", /between 1 and 25/);
  assert.match(validateSearch("research", 26) || "", /between 1 and 25/);
});

test("citation requires a DOI and accepts a missing expected title", () => {
  assert.equal(validateCitation("10.1016/j.test", ""), null);
  assert.match(validateCitation("short", "") || "", /DOI/);
});

test("publication range handles missing years", () => {
  const make = (year: number | null) => ({ publication_year: year } as AcademicWork);
  assert.equal(getPublicationRange([make(null)]), "—");
  assert.equal(getPublicationRange([make(2024)]), "2024");
  assert.equal(getPublicationRange([make(2021), make(null), make(2025)]), "2021–2025");
});

test("author truncation is consistent", () => {
  assert.equal(getShortAuthors([]), "Authors not listed");
  assert.equal(getShortAuthors(["A", "B"]), "A, B");
  assert.equal(getShortAuthors(["A", "B", "C"]), "A et al.");
});

test("upstream and configuration errors are actionable", () => {
  assert.match(getResponseError(503), /API key/);
  assert.match(getResponseError(502), /unavailable/);
  assert.equal(getResponseError(422, "Invalid DOI"), "Invalid DOI");
});
