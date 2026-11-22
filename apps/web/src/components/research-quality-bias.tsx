"use client";

import { useEffect, useState } from "react";
import { ClipboardList, CircleAlert, History, Save } from "lucide-react";

import {
  defaultQualityDraft, DIMENSION_LABELS, hasUnverifiedJudgment,
  isQualityChecklist, isQualityRevision,
} from "@/lib/quality";
import type {
  QualityChecklist, QualityDimension, QualityDraft, QualityRevision,
} from "@/lib/quality";
import type { LibraryItem } from "@/lib/research-library";

interface Props {
  projectId: string;
  entries: LibraryItem[];
}
function detail(value: unknown, fallback: string): string {
  return value && typeof value === "object" && "detail" in value
    && typeof value.detail === "string" ? value.detail : fallback;
}
const REPORTING_OPTIONS = [
  ["not_assessed", "Not assessed"],
  ["reported_in_full_text", "Reported in full text"],
  ["unclear_after_review", "Unclear after full-text review"],
  ["not_reported_in_full_text", "Not reported in reviewed full text"],
  ["not_applicable", "Not applicable"],
] as const;
const CONCERN_OPTIONS = [
  ["not_assessed", "Not assessed"],
  ["potential_concern", "Potential concern — needs adjudication"],
  ["no_concern_identified", "No concern identified in this review"],
] as const;

export function ResearchQualityBias({ projectId, entries }: Props) {
  const [entryId, setEntryId] = useState("");
  const [checklist, setChecklist] = useState<QualityChecklist | null>(null);
  const [drafts, setDrafts] = useState<Record<string, QualityDraft>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState<QualityDimension | null>(null);
  const [history, setHistory] = useState<QualityRevision[] | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEntryId("");
    setChecklist(null);
    setDrafts({});
    setHistory(null);
    setNotice(null);
    setError(null);
  }, [projectId]);

  useEffect(() => {
    setChecklist(null);
    setDrafts({});
    setHistory(null);
    setError(null);
    setNotice(null);
    if (!entryId) { setLoading(false); return; }
    const controller = new AbortController();
    setLoading(true);
    async function load() {
      try {
        const response = await fetch(
          "/api/projects/" + projectId + "/literature/" + entryId + "/quality-checklist",
          { cache: "no-store", signal: controller.signal },
        );
        const body: unknown = await response.json().catch(() => null);
        if (!response.ok) throw new Error(detail(body, "Unable to load quality checklist."));
        if (!isQualityChecklist(body) || body.entry_id !== entryId || body.project_id !== projectId) {
          throw new Error("Unexpected quality checklist response.");
        }
        if (controller.signal.aborted) return;
        setChecklist(body);
        const draftsByDimension: Record<string, QualityDraft> = {};
        for (const row of body.indicators) {
          const last = body.latest_reviews.find((review) => review.dimension === row.dimension);
          draftsByDimension[row.dimension] = last
            ? {
              reporting: last.reporting, concern: last.concern,
              checked_original: last.checked_original, note: last.note,
            }
            : defaultQualityDraft();
        }
        setDrafts(draftsByDimension);
      } catch (failure) {
        if (!controller.signal.aborted) {
          setError(failure instanceof Error ? failure.message : "Unable to load checklist.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [projectId, entryId]);

  function edit(dimension: QualityDimension, change: Partial<QualityDraft>) {
    setDrafts((previous) => ({
      ...previous,
      [dimension]: { ...(previous[dimension] ?? defaultQualityDraft()), ...change },
    }));
    setNotice(null);
  }

  async function save(dimension: QualityDimension) {
    const draft = drafts[dimension];
    if (!draft || hasUnverifiedJudgment(draft)) {
      setError("Confirm review of the original PDF before giving a reporting or concern judgment.");
      return;
    }
    setSaving(dimension);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(
        "/api/projects/" + projectId + "/literature/" + entryId + "/quality-reviews",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dimension, ...draft }),
        },
      );
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(detail(body, "Unable to save quality review."));
      if (!isQualityRevision(body) || body.entry_id !== entryId
          || body.dimension !== dimension) {
        throw new Error("Unexpected quality review response.");
      }
      setChecklist((previous) => previous
        ? {
          ...previous,
          latest_reviews: [
            body,
            ...previous.latest_reviews.filter((review) => review.dimension !== dimension),
          ],
        }
        : previous);
      setHistory((previous) => previous === null ? null : [body, ...previous]);
      setNotice(DIMENSION_LABELS[dimension] + ": review revision saved to PostgreSQL.");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Unable to save review.");
    } finally {
      setSaving(null);
    }
  }

  async function loadHistory() {
    if (!entryId) return;
    setHistoryLoading(true);
    setError(null);
    try {
      const response = await fetch(
        "/api/projects/" + projectId + "/literature/" + entryId + "/quality-reviews",
        { cache: "no-store" },
      );
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(detail(body, "Unable to load review history."));
      if (!Array.isArray(body) || !body.every(isQualityRevision)) {
        throw new Error("Unexpected review history response.");
      }
      setHistory(body);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Unable to load history.");
    } finally {
      setHistoryLoading(false);
    }
  }

  return (
    <section className="quality-bias-panel" aria-labelledby="quality-bias-title">
      <div className="review-heading">
        <div>
          <h4 className="panel-title" id="quality-bias-title">
            Research Quality & Bias Intelligence
          </h4>
          <p className="panel-subtitle">
            Source availability and human methodological judgments are always separate.
          </p>
        </div>
        <ClipboardList size={20} aria-hidden="true" />
      </div>
      <p className="review-caveat">
        This generic reporting checklist is NOT a validated risk-of-bias instrument or
        quality score. An extracted quotation does not prove an item was reported.
        Missing excerpts do not mean missing content in the full paper.
        Manual concern labels are not an official risk-of-bias classification.
      </p>
      <label htmlFor="quality-study-select" className="field-label">
        Saved study to assess
      </label>
      <select id="quality-study-select" className="field"
        value={entryId} onChange={(e) => setEntryId(e.target.value)}>
        <option value="">Choose a saved analysis…</option>
        {entries.map((item) => (
          <option key={item.entry.id} value={item.entry.id}>
            {item.entry.profile.document_title} · {item.entry.id.slice(0, 8)}
          </option>
        ))}
      </select>
      {loading && <p role="status" className="panel-subtitle">Loading checklist and latest reviews…</p>}
      {notice && <p role="status" className="quality-notice">{notice}</p>}
      {error && <p role="alert" className="alert"><CircleAlert size={15} /> {error}</p>}
      {checklist && (
        <div className="quality-content">
          <p className="review-caveat">{checklist.caveat}</p>
          <div className="quality-grid">
            {checklist.indicators.map((row) => {
              const draft = drafts[row.dimension] ?? defaultQualityDraft();
              const last = checklist.latest_reviews.find(
                (revision) => revision.dimension === row.dimension
              );
              return (
                <article className="quality-indicator" key={row.dimension}>
                  <h5>{DIMENSION_LABELS[row.dimension]}</h5>
                  <p>{row.prompt}</p>
                  <p className="quality-source-status">
                    {row.coverage === "excerpt_available"
                      ? "Saved source excerpts available — reporting NOT verified"
                      : "No grounded excerpt — full text still needs review"}
                  </p>
                  {row.source_excerpts.map((source) => (
                    <details key={source.facet}>
                      <summary>{source.locator} · {source.facet} excerpt</summary>
                      <blockquote>{source.quote}</blockquote>
                    </details>
                  ))}
                  <div className="quality-review-fields">
                    <label>Full-text reporting judgment
                      <select className="field" value={draft.reporting}
                        onChange={(e) => edit(row.dimension, {
                          reporting: e.target.value as QualityDraft["reporting"],
                        })}>
                        {REPORTING_OPTIONS.map(([value, label]) =>
                          <option value={value} key={value}>{label}</option>
                        )}
                      </select>
                    </label>
                    <label>Potential methodological concern — human assessment
                      <select className="field" value={draft.concern}
                        onChange={(e) => edit(row.dimension, {
                          concern: e.target.value as QualityDraft["concern"],
                        })}>
                        {CONCERN_OPTIONS.map(([value, label]) =>
                          <option value={value} key={value}>{label}</option>
                        )}
                      </select>
                    </label>
                    <label>Researcher note
                      <textarea className="field" rows={3} maxLength={1000}
                        value={draft.note} onChange={(e) => edit(row.dimension, {
                          note: e.target.value,
                        })} placeholder="Source interpretation or follow-up questions…" />
                    </label>
                    <label className="quality-confirm">
                      <input type="checkbox" checked={draft.checked_original}
                        onChange={(e) => edit(row.dimension, {
                          checked_original: e.target.checked,
                        })} />
                      I checked the original full PDF for this judgment.
                    </label>
                    <button type="button" className="secondary-btn"
                      disabled={saving !== null || hasUnverifiedJudgment(draft)}
                      onClick={() => { void save(row.dimension); }}>
                      <Save size={14} />{saving === row.dimension ? "Saving…" : "Save review revision"}
                    </button>
                    {last && <small className="quality-last-review">
                      Latest saved: {new Date(last.created_at).toLocaleString()}
                      {" · "}{last.checked_original ? "Original PDF checked" : "Not checked"}
                    </small>}
                  </div>
                </article>
              );
            })}
          </div>
          <div className="quality-history">
            <button type="button" className="secondary-btn" disabled={historyLoading}
              onClick={() => { void loadHistory(); }}>
              <History size={15} />{historyLoading ? "Loading…" : "View saved review history"}
            </button>
            {history && (
              <div className="quality-history-list">
                {history.length === 0 && <p className="panel-subtitle">No reviews saved yet.</p>}
                {history.map((item) => (
                  <article key={item.id}>
                    <strong>{DIMENSION_LABELS[item.dimension]}</strong>
                    <p>{new Date(item.created_at).toLocaleString()} ·
                      {" "}{item.reporting.replaceAll("_", " ")} ·
                      {" "}{item.concern.replaceAll("_", " ")}</p>
                    <p>{item.note || "No reviewer note"}</p>
                  </article>
                ))}
                <p className="panel-subtitle">
                  Shows at most 100 newest revisions. History is append-only.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
