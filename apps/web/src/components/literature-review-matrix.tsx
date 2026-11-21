"use client";

import { useState } from "react";
import { CircleAlert, Download } from "lucide-react";

import {
  FACETS, REJECTION_MESSAGES, selectMatrixRows,
} from "@/lib/literature";
import type {
  FacetFilter, HumanReview, HumanReviews, LiteratureFacet,
  LiteratureProfile, MatrixRow, StatusFilter,
} from "@/lib/literature";
import type { ReviewRevision } from "@/lib/workspace";

interface Props {
  profiles: LiteratureProfile[];
  reviews: HumanReviews;
  onReviewChange: (key: string, change: Partial<HumanReview>) => void;
  onRemove: (sha256: string) => void;
  onExport: () => void;
  persistent?: boolean;
  onSaveReview?: (row: MatrixRow) => void;
  onLoadHistory?: (row: MatrixRow) => void;
  history?: Record<string, ReviewRevision[]>;
  savingKey?: string | null;
  savedKey?: string | null;
}

function EvidenceCell({ row }: { row: MatrixRow }) {
  const finding = row.finding;
  if (finding.status === "not_identified") {
    return <p className="literature-empty">Not identified in the selected source excerpts.
      This does not mean the full paper lacks the information.</p>;
  }
  if (finding.status === "rejected_quote") {
    const reason = finding.rejection_reason;
    return (
      <div className="literature-rejection">
        <span className="literature-invalid"><CircleAlert size={14} /> Quotation rejected</span>
        <p>{reason ? REJECTION_MESSAGES[reason] : "Source verification failed."}</p>
        <p className="literature-subnote">
          The model text was discarded; inspect the original PDF before entering a correction.
        </p>
      </div>
    );
  }
  return (
    <div className="literature-cell">
      <p>{finding.value}</p>
      <span className="literature-locator">{finding.locator}</span>
      {finding.locator_repaired && (
        <p className="literature-corrected-locator">
          Page locator corrected using a verbatim match in selected PDF text.
        </p>
      )}
      <details>
        <summary>Inspect exact source quotation</summary>
        <blockquote>{finding.quote}</blockquote>
      </details>
    </div>
  );
}

function ReviewCell({
  row, review, onChange, onSave, onLoadHistory, revisions, saving, saved,
}: {
  row: MatrixRow;
  review: HumanReview | undefined;
  onChange: (change: Partial<HumanReview>) => void;
  onSave?: () => void;
  onLoadHistory?: () => void;
  revisions?: ReviewRevision[];
  saving?: boolean;
  saved?: boolean;
}) {
  const id = row.key.replaceAll(":", "-");
  return (
    <div className="literature-review-cell">
      {review?.corrected_value && (
        <p className="literature-human-value">
          <strong>Researcher correction (not automatically verified):</strong>
          {" "}{review.corrected_value}
        </p>
      )}
      {review?.reviewed && (
        <p className="literature-review-tag">Researcher marked as checked against PDF</p>
      )}
      <details>
        <summary>Edit researcher review</summary>
        <div className="literature-review-editor">
          <label htmlFor={"correction-" + id}>Manual correction (optional)</label>
          <textarea
            id={"correction-" + id}
            className="field review-textarea"
            maxLength={500}
            value={review?.corrected_value || ""}
            onChange={(event) => onChange({ corrected_value: event.target.value })}
            placeholder="Your interpretation; not a verified AI quotation"
          />
          <label htmlFor={"note-" + id}>Review notes</label>
          <textarea
            id={"note-" + id}
            className="field review-textarea"
            maxLength={1000}
            value={review?.note || ""}
            onChange={(event) => onChange({ note: event.target.value })}
            placeholder="What to check in the original PDF"
          />
          <label className="literature-checked-label">
            <input type="checkbox" checked={review?.reviewed || false}
              onChange={(event) => onChange({ reviewed: event.target.checked })} />
            I reviewed this field against the original PDF
          </label>
          <small>Manual notes never change the model result or its verified source quote.</small>
          {onSave && (
            <button type="button" className="secondary-btn" onClick={onSave}
              disabled={Boolean(saving)}>
              {saving ? "Saving…" : "Save review revision"}
            </button>
          )}
          {saved && <small role="status">Review saved to PostgreSQL.</small>}
          {onLoadHistory && (
            <button type="button" className="link-btn" onClick={onLoadHistory}>
              View saved review history
            </button>
          )}
          {revisions && (
            <div className="literature-saved-history">
              {revisions.length === 0 && <small>No review history yet.</small>}
              {revisions.map((item) => (
                <div key={item.id} className="literature-history-entry">
                  <small>{new Date(item.created_at).toLocaleString()} ·
                    {item.reviewed ? " Marked reviewed" : " Not reviewed"}</small>
                  <p>{item.corrected_value || "No correction"}</p>
                  {item.note && <p>{item.note}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      </details>
    </div>
  );
}

export function LiteratureReviewMatrix({
  profiles, reviews, onReviewChange, onRemove, onExport, persistent,
  onSaveReview, onLoadHistory, history, savingKey, savedKey,
}: Props) {
  const [query, setQuery] = useState("");
  const [facet, setFacet] = useState<FacetFilter>("all");
  const [status, setStatus] = useState<StatusFilter>("all");
  const rows = selectMatrixRows(profiles, reviews, { query, facet, status });

  const facetLabels: Record<LiteratureFacet, string> = Object.fromEntries(
    FACETS.map(({ key, label }) => [key, label]),
  ) as Record<LiteratureFacet, string>;

  return (
    <div className="literature-results" aria-live="polite">
      <div className="review-heading">
        <div>
          <h4 className="panel-title">Source-grounded study comparison</h4>
          <p className="panel-subtitle">
            {profiles.length} of 5 documents. Review and edits remain separate from
            the AI-extracted evidence.
          </p>
        </div>
        <button className="secondary-btn" type="button" onClick={onExport}>
          <Download size={15} /> Export matrix and reviews CSV
        </button>
      </div>
      <div className="literature-filters">
        <label>
          <span>Search articles and notes</span>
          <input type="search" className="field" value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Document or extracted field…" />
        </label>
        <label>
          <span>Research field</span>
          <select className="field" value={facet}
            onChange={(event) => setFacet(event.target.value as FacetFilter)}>
            <option value="all">All fields</option>
            {FACETS.map(({ key, label }) => <option key={key} value={key}>{label}</option>)}
          </select>
        </label>
        <label>
          <span>AI extraction status</span>
          <select className="field" value={status}
            onChange={(event) => setStatus(event.target.value as StatusFilter)}>
            <option value="all">All statuses</option>
            <option value="grounded">Quote matched</option>
            <option value="rejected_quote">Quote rejected</option>
            <option value="not_identified">Not identified</option>
          </select>
        </label>
      </div>
      <p className="literature-match-count" role="status">
        Showing {rows.length} of {profiles.length * FACETS.length} fields.
        Filters affect the view only; CSV exports all documents.
      </p>
      <div className="review-table-scroll literature-readable-scroll">
        <table className="review-table literature-readable-table">
          <thead>
            <tr>
              <th scope="col">Document</th>
              <th scope="col">Research field</th>
              <th scope="col">AI extraction and provenance</th>
              <th scope="col">Researcher review</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <th scope="row">
                  <strong>{row.profile.document_title}</strong>
                  <span className="literature-subnote">
                    {row.profile.text_page_count}/{row.profile.page_count} searchable PDF pages
                  </span>
                  <button type="button" className="link-btn"
                    onClick={() => onRemove(row.profile.sha256)}>
                    {persistent ? "Hide from comparison" : "Remove document"}
                  </button>
                </th>
                <td><strong>{facetLabels[row.finding.facet]}</strong></td>
                <td><EvidenceCell row={row} /></td>
                <td>
                  <ReviewCell
                    row={row}
                    review={reviews[row.key]}
                    onChange={(change) => onReviewChange(row.key, change)}
                    onSave={onSaveReview ? () => onSaveReview(row) : undefined}
                    onLoadHistory={onLoadHistory ? () => onLoadHistory(row) : undefined}
                    revisions={history?.[row.key]}
                    saving={savingKey === row.key}
                    saved={savedKey === row.key}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && (
          <p className="literature-no-results">No fields match these filters.</p>
        )}
      </div>
      <p className="review-caveat">
        "Quote matched" verifies literal text in selected excerpts, not whether a study
        supports the AI interpretation. Check the original PDF before using the matrix
        in research. Corrections and notes are session-only and exported separately.
      </p>
    </div>
  );
}
