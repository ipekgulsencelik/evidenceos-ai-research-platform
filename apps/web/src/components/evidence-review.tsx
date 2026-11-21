"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowRight, CheckCircle2, CircleAlert, LoaderCircle, Plus, Trash2 } from "lucide-react";

import type { AcademicWork } from "@/lib/academic";
import { literatureCsv, validateEvidenceRequest } from "@/lib/evidence";
import type { EvidenceReport, EvidenceRequest, EvidenceSource } from "@/lib/evidence";

type DraftSource = EvidenceSource & { localId: number };
const blank: DraftSource = {
  localId: 1, source_id: "manual-1", title: "", passage: "", locator: null,
};

export function EvidenceReview({
  works, selectedWork,
}: {
  works: AcademicWork[];
  selectedWork: AcademicWork | null;
}) {
  const [claim, setClaim] = useState("");
  const [sources, setSources] = useState<DraftSource[]>([blank]);
  const nextSource = useRef(2);
  const [report, setReport] = useState<EvidenceReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedWork) return;
    setSources((items) => items.map((item, index) => index === 0
      ? {
          ...item, source_id: selectedWork.source_id.slice(0, 150),
          title: selectedWork.title, passage: "", locator: null,
        } : item));
    setReport(null);
  }, [selectedWork]);

  function updateSource(id: number, field: "title" | "passage" | "locator", value: string) {
    setSources((items) => items.map((item) => item.localId === id
      ? { ...item, [field]: field === "locator" ? (value || null) : value }
      : item));
    setReport(null);
  }

  function addSource() {
    if (sources.length >= 3) return;
    const id = nextSource.current++;
    setSources((items) => [...items, {
      localId: id, source_id: "manual-" + id, title: "", passage: "", locator: null,
    }]);
  }

  function exportCsv() {
    if (!works.length) return;
    const blob = new Blob(["\uFEFF" + literatureCsv(works)], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "evidenceos-literature-metadata.csv";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function assess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload: EvidenceRequest = {
      claim: claim.trim(),
      sources: sources.map(({ source_id, title, passage, locator }) => ({
        source_id, title: title.trim(), passage: passage.trim(),
        locator: locator?.trim() || null,
      })),
    };
    const invalid = validateEvidenceRequest(payload);
    if (invalid) { setError(invalid); return; }
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      const response = await fetch("/api/evidence/assess", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload), cache: "no-store",
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = body && typeof body === "object" && "detail" in body &&
          typeof body.detail === "string" ? body.detail : "Model review failed.";
        throw new Error(detail);
      }
      if (!body || typeof body !== "object" || !("rows" in body) ||
          !Array.isArray(body.rows)) throw new Error("Invalid evidence service response.");
      setReport(body as EvidenceReport);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Review failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="review-section" id="evidence-review" aria-labelledby="review-title">
      <div className="section-heading">
        <div><h2 id="review-title">Literature matrix &amp; AI evidence review</h2>
          <p>Compare metadata, then evaluate the exact passages you supply.</p></div>
      </div>
      <div className="card panel-pad">
        <div className="review-heading">
          <div><h3 className="panel-title">Publication comparison matrix</h3>
            <p className="panel-subtitle">Bibliographic metadata only; research findings not extracted.</p></div>
          <button type="button" className="secondary-btn" disabled={!works.length} onClick={exportCsv}>
            Export CSV
          </button>
        </div>
        {works.length ? (
          <div className="review-table-scroll">
            <table className="review-table">
              <thead><tr><th>Publication</th><th>Year</th><th>DOI</th><th>Authors</th></tr></thead>
              <tbody>{works.map((work) => (
                <tr key={work.source_id}>
                  <td>{work.title}</td><td>{work.publication_year ?? "Unknown"}</td>
                  <td>{work.doi || "Not listed"}</td>
                  <td>{work.authors.join(", ") || "Not listed"}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className="panel-subtitle">Search for papers to populate this metadata matrix.</p>}
      </div>

      <div className="card panel-pad">
        <h3 className="panel-title">AI-assisted claim assessment</h3>
        <p className="panel-subtitle">
          Paste actual source excerpts. A model assesses whether each passage
          supports, contradicts or is insufficient for the claim.
        </p>
        <p className="review-caveat">
          Pressing Assess sends your claim and excerpts to Groq, an external AI provider.
          Do not include confidential, identifying, sensitive or unauthorized text.
          These outputs are preliminary model judgments, not verified scientific facts.
        </p>
        <form onSubmit={assess}>
          <label className="field-label" htmlFor="evidence-claim">Research claim</label>
          <textarea id="evidence-claim" className="field review-textarea"
            value={claim} onChange={(e) => { setClaim(e.target.value); setReport(null); }}
            minLength={10} maxLength={500} required
            placeholder="Write a precise, testable statement based on the sources." />
          {sources.map((source, index) => (
            <div key={source.localId} className="review-source">
              <div className="review-heading">
                <strong>Source {index + 1}</strong>
                {sources.length > 1 && <button className="secondary-btn" type="button"
                  onClick={() => setSources((items) =>
                    items.filter((item) => item.localId !== source.localId))}>
                  <Trash2 size={14} /> Remove
                </button>}
              </div>
              <label className="field-label" htmlFor={"title-" + source.localId}>Publication title</label>
              <input className="field" id={"title-" + source.localId}
                value={source.title} onChange={(e) => updateSource(source.localId, "title", e.target.value)}
                minLength={3} maxLength={300} required />
              <label className="field-label" htmlFor={"locator-" + source.localId}>Page or section (optional)</label>
              <input className="field" id={"locator-" + source.localId}
                value={source.locator || ""} onChange={(e) => updateSource(source.localId, "locator", e.target.value)}
                maxLength={200} placeholder="Results, page 4…" />
              <label className="field-label" htmlFor={"passage-" + source.localId}>Exact excerpt</label>
              <textarea className="field review-textarea" id={"passage-" + source.localId}
                value={source.passage} onChange={(e) => updateSource(source.localId, "passage", e.target.value)}
                minLength={30} maxLength={4000} required
                placeholder="Paste an excerpt from a document you are permitted to use." />
            </div>
          ))}
          <div className="review-actions">
            <button className="secondary-btn" type="button" onClick={addSource}
              disabled={sources.length >= 3}><Plus size={14} /> Add passage</button>
            <button type="submit" className="primary-btn" disabled={busy}>
              {busy ? <LoaderCircle className="spinner" size={15} /> : <CheckCircle2 size={15} />}
              {busy ? "Assessing…" : "Assess claim"} <ArrowRight size={14} />
            </button>
          </div>
        </form>
        {error && <div role="alert" className="alert"><CircleAlert size={15} /> {error}</div>}
        {report && <div className="review-report" aria-live="polite">
          <h4>Initial evidence assessment <small>{report.model}</small></h4>
          {report.rows.map((row) => (
            <article className="review-result" key={row.source_id}>
              <div className="review-heading"><strong>{row.title}</strong>
                <span className={"review-verdict verdict-" + row.verdict}>{row.verdict}</span>
              </div>
              {row.locator && <p>Provided locator: {row.locator}</p>}
              {row.quote && <blockquote>{row.quote}</blockquote>}
              <p>{row.explanation}</p>
            </article>
          ))}
          <p className="review-caveat">{report.caveat}</p>
        </div>}
      </div>
    </section>
  );
}
