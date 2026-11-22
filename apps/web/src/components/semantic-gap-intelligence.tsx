"use client";

import { useEffect, useState } from "react";
import { BrainCircuit, CircleAlert, FileSearch, LoaderCircle } from "lucide-react";

import { isSemanticGapReport, SEMANTIC_LABELS } from "@/lib/semantic";
import type { SemanticGapReport } from "@/lib/semantic";

interface Props {
  projectId: string;
  selectedIds: string[];
  selectedHashes: string[];
}

function problem(value: unknown, fallback: string): string {
  if (value && typeof value === "object" && "detail" in value
      && typeof value.detail === "string") return value.detail;
  return fallback;
}

export function SemanticGapIntelligence({
  projectId, selectedIds, selectedHashes,
}: Props) {
  const [consent, setConsent] = useState(false);
  const [report, setReport] = useState<SemanticGapReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const selectedKey = selectedIds.join(",");

  // Choosing other papers requires a fresh explicit consent and new analysis.
  useEffect(() => {
    setConsent(false);
    setReport(null);
    setError(null);
  }, [projectId, selectedKey]);

  const distinct = selectedHashes.length === selectedIds.length
    && new Set(selectedHashes).size === selectedHashes.length;
  const validSelection = selectedIds.length >= 2 && selectedIds.length <= 10 && distinct;

  async function compare() {
    if (!validSelection || !consent || pending) return;
    setPending(true);
    setError(null);
    setReport(null);
    try {
      const response = await fetch(
        "/api/projects/" + projectId + "/semantic-gaps",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
          body: JSON.stringify({
            entry_ids: selectedIds,
            consent_to_share_quotes: true,
          }),
        },
      );
      const value: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(problem(value, "Semantic comparison failed."));
      if (!isSemanticGapReport(value) || value.project_id !== projectId) {
        throw new Error("Unexpected semantic comparison response.");
      }
      if (selectedIds.some((id) => !value.document_ids.includes(id))) {
        throw new Error("Returned comparison does not match the selected analyses.");
      }
      setReport(value);
      setConsent(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Comparison failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="semantic-comparison-panel">
      <div className="review-heading">
        <div>
          <h4 className="panel-title">Semantic Research Gap Intelligence</h4>
          <p className="panel-subtitle">
            AI-assisted comparisons of participant groups, methods, instruments and findings.
          </p>
        </div>
        <BrainCircuit size={20} aria-hidden="true" />
      </div>
      <p className="review-caveat">
        Only exact source quotations, PDF page locators and document titles from the
        selected saved analyses are sent to Groq. No PDF binary is sent.
        This is preliminary interpretation, NOT verified scientific truth or a proven research gap.
      </p>
      <label className="semantic-consent">
        <input type="checkbox" checked={consent} disabled={pending}
          onChange={(event) => setConsent(event.target.checked)} />
        I have permission to process these sources and explicitly agree to send their
        selected quotations and document titles to Groq for AI comparison.
      </label>
      {!distinct && selectedIds.length > 1 && (
        <p className="panel-subtitle" role="status">Select different PDF documents.</p>
      )}
      <button type="button" className="primary-btn" disabled={!validSelection || !consent || pending}
        onClick={() => { void compare(); }}>
        {pending ? <LoaderCircle size={15} className="spinner" /> : <FileSearch size={15} />}
        {pending ? "Analyzing selected quotations…" : "Compare scientific content with AI"}
      </button>
      {error && <p role="alert" className="alert"><CircleAlert size={15} />{error}</p>}
      {report && (
        <section className="semantic-comparison-results" aria-live="polite">
          <p className="panel-subtitle">Model: {report.model}</p>
          <p className="review-caveat">{report.caveat}</p>
          {report.skipped_candidates > 0 && (
            <p className="panel-subtitle">
              {report.skipped_candidates} proposed comparisons were discarded because
              their source references or fields could not be verified.
            </p>
          )}
          {report.insufficient_dimensions.length > 0 && (
            <p className="panel-subtitle">
              Not enough paired quotations: {report.insufficient_dimensions
                .map((dimension) => SEMANTIC_LABELS[dimension]).join(", ")}.
            </p>
          )}
          {report.candidates.length === 0 && (
            <p className="panel-subtitle">
              No source-linked semantic comparison candidates could be accepted.
              This is not a conclusion about the literature.
            </p>
          )}
          {report.candidates.map((candidate) => (
            <article className="semantic-comparison-item" key={candidate.dimension}>
              <h5>{SEMANTIC_LABELS[candidate.dimension]}</h5>
              <p className="semantic-kind">
                {candidate.kind === "possible_difference"
                  ? "Possible difference — needs verification"
                  : candidate.kind === "possible_alignment"
                    ? "Possible alignment — needs verification"
                    : "Insufficient context for comparison"}
              </p>
              <p>{candidate.summary}</p>
              <p><strong>Question for researcher review:</strong> {candidate.research_question}</p>
              <div className="semantic-quote-grid">
                {candidate.references.map((ref) => (
                  <details key={ref.reference_id}>
                    <summary>{ref.document_title} — {ref.locator}</summary>
                    <blockquote>{ref.quote}</blockquote>
                  </details>
                ))}
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
