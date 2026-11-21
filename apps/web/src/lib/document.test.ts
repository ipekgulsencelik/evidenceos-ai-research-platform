import assert from "node:assert/strict";
import test from "node:test";

import { isPdfReview, MAX_PDF_BYTES, validatePdfUpload } from "./document.ts";

const valid = { name: "paper.pdf", size: 1000 };
const claim = "Chatbot use in adolescents predicts wellbeing";

test("PDF validation requires a meaningful claim and bounded PDF", () => {
  assert.equal(validatePdfUpload(valid, claim), null);
  assert.match(validatePdfUpload(null, claim) || "", /Select a PDF/);
  assert.match(validatePdfUpload(valid, "short") || "", /claim/);
  assert.match(validatePdfUpload({ name: "paper.docx", size: 10 }, claim) || "", /pdf/);
  assert.match(validatePdfUpload({ name: "paper.pdf", size: MAX_PDF_BYTES + 1 }, claim) || "", /8 MiB/);
  assert.match(validatePdfUpload({ name: "paper.PDF", size: 200 }, claim) || "", /^$/);
});

test("document review response rejects unexpected payloads", () => {
  assert.equal(isPdfReview(null), false);
  assert.equal(isPdfReview({ title: "demo.pdf", passages: "not an array" }), false);
  const payload = {
    title: "paper.pdf", sha256: "abc", page_count: 1, text_page_count: 1,
    caveat: "Not verified", passages: [{
      source_id: "pdf-abc-p1-s1", title: "paper.pdf", locator: "PDF page 1",
      passage: "An exact quote from the user's PDF", matched_terms: ["chatbot"],
      lexical_score: 0.5,
    }],
  };
  assert.equal(isPdfReview(payload), true);
  assert.equal(isPdfReview({ ...payload, passages: [{ ...payload.passages[0], passage: 17 }] }), false);
});
