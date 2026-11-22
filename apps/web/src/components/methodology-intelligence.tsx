"use client";

import { useEffect, useState } from "react";
import { ClipboardCheck, CircleAlert, LoaderCircle } from "lucide-react";

import { isMethodologyReport, METHODOLOGY_LABELS } from "@/lib/methodology";
import type { MethodologyReport, MethodologyStatus } from "@/lib/methodology";
import type { LibraryItem } from "@/lib/research-library";

interface Props {
  projectId: string;
  entries: LibraryItem[];
}

function explainStatus(status: MethodologyStatus): string {
  if (status === "reported_in_excerpt") return "AI identifies reporting in an excerpt";
  if (status === "needs_review") return "Needs review of original methods";
  return "Not assessable from saved excerpts";
}

function apiError(value: unknown): string {
  if (value && typeof value === "object" && "detail" in value
    && typeof value.detail === "string") return value.detail;
  return "Methodology review failed.";
}

export function MethodologyIntelligence({ projectId, entries }: Props) {
  const [entryId, setEntryId] = useState("");
  const [consent, setConsent] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<MethodologyReport | null>(null);

  useEffect(() => {
    setEntryId("");
    setConsent(false);
    setPending(false);
    setError(null);
    setReport(null);
  }, [projectId]);

  function pickStudy(id: string) {
    setEntryId(id);
    setConsent(false);
    setError(null);
    setReport(null);
  }

  async function assess() {
    if (!entryId || !consent || pending || !entries.some((row) => row.entry.id === entryId)) {
      return;
    }
    setPending(true);
    setError(null);
    setReport(null);
    try {
      const response = await fetch(
        "/api/projects/" + projectId + "/literature/" + entryId + "/methodology-review",
        {
          method: "POST", cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ consent_to_share_quotes: true }),
        },
      );
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(apiError(payload));
      if (
        !isMethodologyReport(payload) || payload.project_id !== projectId
        || payload.entry_id !== entryId
      ) {
        throw new Error("Unexpected methodology report response.");
      }
      setReport(payload);
      setConsent(false);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Methodology review failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="methodology-panel" aria-labelledby="methodology-intelligence-title">
      <div className="review-heading">
        <div>
          <h4 className="panel-title" id="methodology-intelligence-title">
            Research Methodology Intelligence
          </h4>
          <p className="panel-subtitle">
            Review a saved study's design, sampling, measurement, psychometrics,
            analysis reporting and limitations.
          </p>
        </div>
        <ClipboardCheck size={20} aria-hidden="true" />
      </div>
      <p className="review-caveat">
        Source-limited assessment, NOT a validated quality score or full-paper review.
        When the saved quotations do not establish a detail, the system will say
        "Not assessable" instead of guessing. This review is not saved to PostgreSQL.
      </p>
      <label className="field-label" htmlFor="methodology-study">
        Study to review
      </label>
      <select id="methodology-study" className="field" value={entryId}
        disabled={pending} onChange={(event) => pickStudy(event.target.value)}>
        <option value="">Choose a saved analysis…</option>
        {entries.map((row) => (
          <option key={row.entry.id} value={row.entry.id}>
            {row.entry.profile.document_title} · {row.entry.id.slice(0, 8)}
          </option>
        ))}
      </select>
      <label className="semantic-consent">
        <input type="checkbox" checked={consent} disabled={!entryId || pending}
          onChange={(event) => setConsent(event.target.checked)} />
        I have permission to process this study and explicitly agree to send
        selected source quotations and page locations to Groq for preliminary
        methodology assessment. No PDF binary or reviewer notes are sent.
      </label>
      <button type="button" className="primary-btn"
        disabled={!entryId || !consent || pending}
        onClick={() => { void assess(); }}>
        {pending ? <LoaderCircle size={15} className="spinner" />
          : <ClipboardCheck size={15} />}
        {pending ? "Reviewing saved excerpts…" : "Review study methodology with AI"}
      </button>
      {error && <p role="alert" className="alert">
        <CircleAlert size={15} />{error}
      </p>}
      {report && (
        <div className="methodology-report" aria-live="polite">
          <h5>{report.document_title}</h5>
          <p className="panel-subtitle">Model: {report.model}</p>
          <p className="review-caveat">{report.caveat}</p>
          {report.discarded_model_observations > 0 && (
            <p className="panel-subtitle">
              {report.discarded_model_observations} unsupported or malformed
              proposed observations were discarded.
            </p>
          )}
          <div className="methodology-grid">
            {report.observations.map((item) => (
              <article key={item.aspect} className="methodology-item">
                <h6>{METHODOLOGY_LABELS[item.aspect]}</h6>
                <p className="methodology-status">{explainStatus(item.status)}</p>
                <p>{item.observation}</p>
                <p><strong>Researcher check:</strong> {item.review_question}</p>
                {item.sources.map((source) => (
                  <details key={source.reference_id}>
                    <summary>{source.locator} · {source.facet} source quote</summary>
                    <blockquote>{source.quote}</blockquote>
                  </details>
                ))}
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
