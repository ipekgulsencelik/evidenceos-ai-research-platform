"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";
import { CheckCircle2, CircleAlert, Download, FileText, LoaderCircle } from "lucide-react";

import {
  FACETS, isLiteratureProfile, literatureProfileCsv, validateLiteratureUpload,
} from "@/lib/literature";
import type { LiteratureProfile } from "@/lib/literature";

const MAX_PROFILES = 5;

function FindingCell({ report, facet }: {
  report: LiteratureProfile;
  facet: (typeof FACETS)[number]["key"];
}) {
  const finding = report.findings.find((f) => f.facet === facet);
  if (!finding || finding.status === "not_identified") {
    return <span className="literature-empty">Not identified in selected excerpts</span>;
  }
  if (finding.status === "rejected_quote") {
    return <span className="literature-invalid">Unverifiable quotation discarded</span>;
  }
  return (
    <div className="literature-cell">
      <p>{finding.value}</p>
      <small>{finding.locator}</small>
      <details>
        <summary>Source quotation</summary>
        <blockquote>{finding.quote}</blockquote>
      </details>
    </div>
  );
}

export function ScientificLiteratureIntelligence() {
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [profiles, setProfiles] = useState<LiteratureProfile[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function changeFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] || null);
    setConsent(false);
    setError(null);
  }

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const invalid = validateLiteratureUpload(file, consent);
    if (invalid) { setError(invalid); return; }
    if (!file) return;
    if (profiles.length >= MAX_PROFILES && !profiles.some((p) =>
      p.document_title === file.name)) {
      setError("The comparison supports up to five documents. Remove a row to continue.");
      return;
    }
    const form = new FormData();
    form.append("file", file);
    form.append("share_excerpts_with_ai", "true");
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/literature/analyze-pdf", {
        method: "POST", body: form, cache: "no-store",
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = body && typeof body === "object" && "detail" in body
          && typeof body.detail === "string" ? body.detail : "Literature extraction failed.";
        throw new Error(detail);
      }
      if (!isLiteratureProfile(body)) {
        throw new Error("Unexpected literature service response.");
      }
      const profile = body;
      setProfiles((current) => {
        const other = current.filter((p) => p.sha256 !== profile.sha256);
        return [...other, profile].slice(-MAX_PROFILES);
      });
      setConsent(false);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Literature extraction failed.");
    } finally {
      setBusy(false);
    }
  }

  function exportCsv() {
    if (!profiles.length) return;
    const url = URL.createObjectURL(new Blob(
      ["\uFEFF" + literatureProfileCsv(profiles)], { type: "text/csv;charset=utf-8" },
    ));
    const link = document.createElement("a");
    link.href = url;
    link.download = "evidenceos-literature-extraction.csv";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <section className="card panel-pad literature-intelligence" aria-labelledby="literature-title">
      <div className="review-heading">
        <div>
          <h3 className="panel-title" id="literature-title">Scientific Literature Intelligence</h3>
          <p className="panel-subtitle">
            Extract six research fields from page-referenced PDF excerpts and compare documents.
          </p>
        </div>
        <FileText size={21} aria-hidden="true" />
      </div>
      <p className="review-caveat">
        This sends up to 12 selected text windows (not the full PDF) to Groq, an external AI
        provider, after your explicit consent. Preliminary AI extraction only. Check all
        quotations in the original publication. Never upload confidential, identifiable,
        patient, or unauthorized documents. 8 MiB / 30 pages, selectable-text PDFs only.
      </p>

      <form onSubmit={analyze} className="literature-form">
        <label className="field-label" htmlFor="literature-pdf">Scientific article PDF</label>
        <input id="literature-pdf" className="field" type="file" accept=".pdf,application/pdf"
          onChange={changeFile} />
        <label className="literature-consent">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          <span>I have permission to process this document and agree to send selected
          extracts to Groq for preliminary scientific literature analysis.</span>
        </label>
        <button className="primary-btn" type="submit" disabled={busy}>
          {busy ? <LoaderCircle size={16} className="spinner" /> : <CheckCircle2 size={16} />}
          {busy ? "Extracting research fields…" : "Analyze document with AI"}
        </button>
      </form>
      {error && <p className="alert" role="alert"><CircleAlert size={16} />{error}</p>}

      {profiles.length > 0 && (
        <div className="literature-results" aria-live="polite">
          <div className="review-heading">
            <div><h4 className="panel-title">Source-grounded study comparison</h4>
              <p className="panel-subtitle">
                {profiles.length} of {MAX_PROFILES} document slots. Not identified does not mean
                absent from the paper.
              </p>
            </div>
            <button className="secondary-btn" type="button" onClick={exportCsv}>
              <Download size={15} /> Export study matrix CSV
            </button>
          </div>
          <div className="review-table-scroll literature-table-scroll">
            <table className="review-table literature-table">
              <thead><tr>
                <th>Document</th>
                {FACETS.map(({ key, label }) => <th key={key}>{label}</th>)}
              </tr></thead>
              <tbody>
                {profiles.map((report) => (
                  <tr key={report.sha256}>
                    <th scope="row">
                      <strong>{report.document_title}</strong>
                      <span className="literature-subnote">
                        {report.text_page_count}/{report.page_count} searchable pages
                      </span>
                      <span className="literature-subnote">{report.model}</span>
                      <button type="button" className="link-btn"
                        onClick={() => setProfiles((items) =>
                          items.filter((p) => p.sha256 !== report.sha256))}>
                        Remove
                      </button>
                    </th>
                    {FACETS.map(({ key }) => (
                      <td key={key}><FindingCell report={report} facet={key} /></td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="review-caveat">
            The AI can misinterpret even an exact quotation. Review the source pages and
            study methods before using these entries in a thesis or systematic review.
            Results are held in the browser session, not saved as permanent literature records.
          </p>
        </div>
      )}
    </section>
  );
}
