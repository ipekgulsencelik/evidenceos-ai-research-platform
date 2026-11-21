import assert from "node:assert/strict";
import test from "node:test";

import {
  FACETS, isLiteratureProfile, literatureProfileCsv, validateLiteratureUpload,
} from "./literature.ts";
import type { LiteratureProfile } from "./literature.ts";

const sample: LiteratureProfile = {
  document_title: "=DANGEROUS",
  sha256: "abc",
  page_count: 2,
  text_page_count: 2,
  model: "example-model",
  caveat: "Researcher review required.",
  findings: FACETS.map(({ key }) => ({
    facet: key, status: key === "aim" ? "grounded" : "not_identified",
    value: key === "aim" ? "+A1" : null,
    quote: key === "aim" ? "The objective was to test this" : null,
    locator: key === "aim" ? "PDF page 1" : null,
  })),
};

test("PDF upload requires explicit consent and bounded size", () => {
  const file = { name: "paper.pdf", size: 2000 };
  assert.equal(validateLiteratureUpload(file, true), null);
  assert.match(validateLiteratureUpload(file, false) || "", /confirm/);
  assert.match(validateLiteratureUpload(null, true) || "", /Choose/);
  assert.match(
    validateLiteratureUpload({ name: "notes.txt", size: 100 }, true) || "", /PDF/,
  );
  assert.match(
    validateLiteratureUpload({ name: "paper.pdf", size: 9 * 1024 * 1024 }, true) || "",
    /8 MiB/,
  );
});

test("literature profile runtime boundary validates six field states", () => {
  assert.equal(isLiteratureProfile(sample), true);
  assert.equal(isLiteratureProfile(null), false);
  assert.equal(isLiteratureProfile({ ...sample, findings: [] }), false);
  assert.equal(
    isLiteratureProfile({ ...sample, findings: [{ ...sample.findings[0], value: 2 }] }),
    false,
  );
});

test("comparison export includes exact page references and sanitizes formulas", () => {
  const csv = literatureProfileCsv([sample]);
  const apostrophe = "'";
  assert.ok(csv.includes('"' + apostrophe + '=DANGEROUS"'));
  assert.ok(csv.includes('"' + apostrophe + '+A1"'));
  assert.ok(csv.includes('"PDF page 1"'));
  assert.ok(csv.includes("The objective was to test this"));
});
