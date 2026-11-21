import assert from "node:assert/strict";
import test from "node:test";

import { literatureCsv, validateEvidenceRequest } from "./evidence.ts";
import type { AcademicWork } from "./academic.ts";

const valid = {
  claim: "The study reported an association between measured variables.",
  sources: [{
    source_id: "s1",
    title: "Research study",
    passage: "The research reports an association between two measured variables.",
    locator: null,
  }],
};

test("evidence request enforces bounds and unique source identifiers", () => {
  assert.equal(validateEvidenceRequest(valid), null);
  assert.match(validateEvidenceRequest({ ...valid, claim: "x" }) || "", /10 and 500/);
  assert.match(validateEvidenceRequest({ ...valid, sources: [] }) || "", /one to three/);
  assert.match(validateEvidenceRequest({ ...valid, sources: [valid.sources[0], valid.sources[0]] }) || "", /unique/);
  assert.match(validateEvidenceRequest({ ...valid, sources: [{ ...valid.sources[0], passage: "short" }] }) || "", /30/);
});

test("export escapes CSV quotes and spreadsheet formulas", () => {
  const work: AcademicWork = {
    source_id: "W1", title: '=SUM(1, 2)', doi: null, publication_year: null,
    authors: ['A. "Tester"'], source_url: "https://openalex.org/W1",
  };
  const csv = literatureCsv([work]);
  assert.ok(csv.includes('"\'=SUM(1, 2)"'));
  assert.ok(csv.includes('A. ""Tester""'));
  assert.ok(csv.includes('"https://openalex.org/W1"'));
});
