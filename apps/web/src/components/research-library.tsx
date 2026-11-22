"use client";

import { useEffect, useMemo, useState } from "react";
import { BookOpen, CircleAlert, FileSearch, LoaderCircle, Save } from "lucide-react";
import { SemanticGapIntelligence } from "@/components/semantic-gap-intelligence";

import { FACETS } from "@/lib/literature";
import {
  filterLibrary, isGapComparison, isLibraryItem, isLibraryMetadata, validateTags,
} from "@/lib/research-library";
import type { GapComparison, LibraryItem, ReadingStatus } from "@/lib/research-library";

interface Props {
  projectId: string;
  refreshToken: number;
}

interface Draft {
  status: ReadingStatus;
  tags: string;
}

function serviceError(value: unknown, fallback: string): string {
  if (value && typeof value === "object" && "detail" in value
    && typeof value.detail === "string") return value.detail;
  return fallback;
}

function titleForFacet(key: string): string {
  return FACETS.find((facet) => facet.key === key)?.label || key;
}

export function ResearchLibrary({ projectId, refreshToken }: Props) {
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [selected, setSelected] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ReadingStatus | "all">("all");
  const [tag, setTag] = useState("");
  const [busy, setBusy] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [comparing, setComparing] = useState(false);
  const [report, setReport] = useState<GapComparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    setItems([]);
    setDrafts({});
    setSelected([]);
    setReport(null);
    setError(null);
    setNotice(null);
    if (!projectId) { setBusy(false); return; }
    const controller = new AbortController();
    setBusy(true);
    async function load() {
      try {
        const response = await fetch("/api/projects/" + projectId + "/library", {
          cache: "no-store", signal: controller.signal,
        });
        const payload: unknown = await response.json().catch(() => null);
        if (!response.ok) throw new Error(serviceError(payload, "Unable to load research library."));
        if (!Array.isArray(payload) || !payload.every(isLibraryItem)) {
          throw new Error("Unexpected research library response.");
        }
        if (controller.signal.aborted) return;
        setItems(payload);
        setDrafts(Object.fromEntries(payload.map((item) => [
          item.entry.id,
          { status: item.metadata.status, tags: item.metadata.tags.join(", ") },
        ])));
      } catch (failure) {
        if (!controller.signal.aborted) {
          setError(failure instanceof Error ? failure.message : "Unable to load the library.");
        }
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [projectId, refreshToken]);

  const shown = useMemo(
    () => filterLibrary(items, query, status, tag),
    [items, query, status, tag],
  );

  function setDraft(id: string, changes: Partial<Draft>) {
    setDrafts((previous) => ({
      ...previous,
      [id]: {
        ...(previous[id] ?? { status: "to_read" as ReadingStatus, tags: "" }),
        ...changes,
      },
    }));
    setNotice(null);
  }

  function toggle(id: string) {
    setSelected((previous) => previous.includes(id)
      ? previous.filter((entry) => entry !== id)
      : previous.length >= 10 ? previous : [...previous, id]);
    setReport(null);
  }

  async function saveMetadata(item: LibraryItem) {
    const draft = drafts[item.entry.id];
    if (!draft) return;
    const tags = draft.tags.split(",").map((t) => t.trim()).filter(Boolean);
    const problem = validateTags(tags);
    if (problem) { setError(problem); return; }
    setSavingId(item.entry.id);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(
        "/api/projects/" + projectId + "/library/" + item.entry.id,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: draft.status, tags }),
        },
      );
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(serviceError(data, "Unable to update library metadata."));
      if (!isLibraryMetadata(data) || data.entry_id !== item.entry.id) {
        throw new Error("Unexpected library update response.");
      }
      setItems((previous) => previous.map((entry) =>
        entry.entry.id === item.entry.id ? { ...entry, metadata: data } : entry,
      ));
      setDrafts((previous) => ({
        ...previous, [item.entry.id]: { status: data.status, tags: data.tags.join(", ") },
      }));
      setNotice("Saved reading status and tags for " + item.entry.profile.document_title);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Unable to save tags.");
    } finally {
      setSavingId(null);
    }
  }

  async function compare() {
    if (selected.length < 2) {
      setError("Select at least two saved analyses.");
      return;
    }
    const selectedItems = selected.map((id) => items.find((item) => item.entry.id === id));
    if (selectedItems.some((item) => !item) ||
        new Set(selectedItems.map((item) => item?.entry.profile.sha256)).size < 2) {
      setError("Select analyses of at least two different PDF documents.");
      return;
    }
    setComparing(true);
    setReport(null);
    setError(null);
    try {
      const response = await fetch("/api/projects/" + projectId + "/research-gaps", {
        method: "POST", cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entry_ids: selected }),
      });
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(serviceError(data, "Coverage comparison failed."));
      if (!isGapComparison(data) || data.project_id !== projectId) {
        throw new Error("Unexpected comparison response.");
      }
      setReport(data);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Coverage comparison failed.");
    } finally {
      setComparing(false);
    }
  }

  if (!projectId) return null;

  return (
    <section className="literature-project-picker research-library-panel" aria-labelledby="research-library-title">
      <div className="review-heading">
        <div>
          <h4 className="panel-title" id="research-library-title">Research Library</h4>
          <p className="panel-subtitle">
            Search saved analyses, organize tags and reading status, and compare extraction coverage.
          </p>
        </div>
        <BookOpen size={20} aria-hidden="true" />
      </div>
      <p className="review-caveat">
        Shows up to 100 newest analysis snapshots in this project, including repeated PDF
        versions. No PDF binaries are stored. Catalog tags and status are saved to PostgreSQL.
      </p>
      <div className="research-library-filters">
        <label>Search document title
          <input type="search" className="field" value={query}
            onChange={(e) => setQuery(e.target.value)} placeholder="e.g. adolescent AI" />
        </label>
        <label>Reading status
          <select className="field" value={status}
            onChange={(e) => setStatus(e.target.value as ReadingStatus | "all")}>
            <option value="all">All statuses</option>
            <option value="to_read">To read</option>
            <option value="reading">Reading</option>
            <option value="reviewed">Reviewed</option>
          </select>
        </label>
        <label>Exact tag
          <input className="field" value={tag} onChange={(e) => setTag(e.target.value)}
            placeholder="e.g. Methods" />
        </label>
      </div>
      {busy && <p role="status">Loading project library…</p>}
      {error && <p role="alert" className="alert"><CircleAlert size={15} />{error}</p>}
      {notice && <p role="status" className="research-library-notice">{notice}</p>}
      {!busy && <p className="panel-subtitle">
        Showing {shown.length} of {items.length} loaded saved analyses.
      </p>}
      <div className="research-library-items">
        {shown.map((item) => {
          const draft = drafts[item.entry.id] || { status: item.metadata.status, tags: "" };
          const checked = selected.includes(item.entry.id);
          return (
            <article className="research-library-item" key={item.entry.id}>
              <div className="research-library-item-heading">
                <label className="research-library-choice">
                  <input type="checkbox" checked={checked} onChange={() => toggle(item.entry.id)}
                    disabled={!checked && selected.length >= 10} />
                  <span>{item.entry.profile.document_title}</span>
                </label>
                <small>{new Date(item.entry.created_at).toLocaleString()}</small>
              </div>
              <div className="research-library-meta">
                <label>Reading status
                  <select className="field" value={draft.status}
                    onChange={(e) => setDraft(item.entry.id, {
                      status: e.target.value as ReadingStatus,
                    })}>
                    <option value="to_read">To read</option>
                    <option value="reading">Reading</option>
                    <option value="reviewed">Reviewed</option>
                  </select>
                </label>
                <label>Tags (comma separated, up to 8)
                  <input className="field" maxLength={320} value={draft.tags}
                    onChange={(e) => setDraft(item.entry.id, { tags: e.target.value })}
                    placeholder="adolescents, methods" />
                </label>
                <button type="button" className="secondary-btn"
                  onClick={() => { void saveMetadata(item); }}
                  disabled={savingId !== null}>
                  <Save size={14} />{savingId === item.entry.id ? "Saving…" : "Save metadata"}
                </button>
              </div>
              <small className="research-library-footnote">
                {item.entry.profile.findings.filter((f) => f.status === "grounded").length}/6
                {" "}fields with matched source quotations · {item.entry.id.slice(0, 8)}
              </small>
            </article>
          );
        })}
        {!busy && shown.length === 0 && <p className="panel-subtitle">
          No saved analyses match this view. Analyze a PDF in the selected project below.
        </p>}
      </div>

      <div className="research-gap-panel">
        <div className="review-heading">
          <div>
            <h4 className="panel-title">Research Gap Detection — evidence coverage</h4>
            <p className="panel-subtitle">
              Select 2–10 saved analyses of different PDFs, then compare which fields
              have source quotations. No model call is made.
            </p>
          </div>
          <FileSearch size={20} aria-hidden="true" />
        </div>
        <button className="primary-btn" type="button" disabled={comparing || selected.length < 2}
          onClick={() => { void compare(); }}>
          {comparing ? <LoaderCircle size={15} className="spinner" /> : <FileSearch size={15} />}
          {comparing ? "Comparing…" : "Compare " + selected.length + " selected analyses"}
        </button>
        <p className="review-caveat">
          Missing or rejected AI-extracted fields suggest a manual verification task,
          not a proven research gap. A genuine gap requires a comprehensive literature search.
        </p>
        {report && (
          <div className="research-gap-results" aria-live="polite">
            <h5>Evidence coverage candidates</h5>
            <p className="review-caveat">{report.caveat}</p>
            {report.candidates.length === 0 && (
              <p className="panel-subtitle">
                All six fields have source quotations across this selection.
                This does not establish that no research gaps exist.
              </p>
            )}
            {report.candidates.map((candidate) => (
              <article className="research-gap-result" key={candidate.facet}>
                <h6>{titleForFacet(candidate.facet)}</h6>
                <p><strong>{candidate.grounded_count}/{candidate.total_count}</strong>
                  {" "}documents have extracted quotations.
                  {" "}{candidate.not_identified_entry_ids.length} not identified;
                  {" "}{candidate.rejected_entry_ids.length} rejected.
                </p>
                <p>{candidate.recommendation}</p>
                {candidate.references.map((reference) => (
                  <details key={reference.entry_id}>
                    <summary>{reference.document_title} — {reference.locator}</summary>
                    <blockquote>{reference.quote}</blockquote>
                    <p className="panel-subtitle">AI interpretation: {reference.interpretation}</p>
                  </details>
                ))}
              </article>
            ))}
          </div>
        )}
      </div>
      <SemanticGapIntelligence
        projectId={projectId}
        selectedIds={selected}
        selectedHashes={selected.map(
          (id) => items.find((item) => item.entry.id === id)?.entry.profile.sha256 || ""
        )}
      />
    </section>
  );
}
