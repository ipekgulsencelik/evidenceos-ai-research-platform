import assert from "node:assert/strict";
import test from "node:test";

import {
  FACETS, isLiteratureProfile, literatureProfileCsv, selectMatrixRows,
  validateLiteratureUpload, reviewKey,
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
    rejection_reason: null,
    locator_repaired: false,
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


test("status and facet filtering retain only requested comparison rows", () => {
  const rows = selectMatrixRows([sample], {}, {
    query: "", facet: "aim", status: "grounded",
  });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].finding.facet, "aim");
  const rejected = selectMatrixRows([sample], {}, {
    query: "", facet: "all", status: "rejected_quote",
  });
  assert.equal(rejected.length, 0);
  const queryMatch = selectMatrixRows([sample], {}, {
    query: "objective", facet: "all", status: "all",
  });
  assert.equal(queryMatch.length, 1);
});

test("researcher corrections remain separate from model provenance", () => {
  const reviews = {
    [reviewKey(sample.sha256, "aim")]: {
      corrected_value: "=SUM(A1:A5)",
      note: "+START formula",
      reviewed: true,
    },
  };
  const unchanged = sample.findings[0].value;
  const csv = literatureProfileCsv([sample], reviews);
  assert.equal(sample.findings[0].value, unchanged);
  assert.ok(csv.includes('"' + "'=SUM(A1:A5)" + '"'));
  assert.ok(csv.includes('"' + "'+START formula" + '"'));
  assert.ok(csv.includes('"yes"'));
  assert.ok(csv.includes("researcher correction (unverified)"));
  assert.equal(selectMatrixRows([sample], reviews, {
    query: "SUM(A1", facet: "all", status: "all",
  }).length, 1);
});

test("invalid or unknown rejection codes are rejected by web boundary", () => {
  assert.equal(isLiteratureProfile({
    ...sample,
    findings: sample.findings.map((item) => ({
      ...item, rejection_reason: "unexpected_code",
    })),
  }), false);
});
