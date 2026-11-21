"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";
import { CheckCircle2, CircleAlert, FileText, LoaderCircle } from "lucide-react";
import { LiteratureReviewMatrix } from "@/components/literature-review-matrix";

import {
  isLiteratureProfile, literatureProfileCsv, validateLiteratureUpload,
} from "@/lib/literature";
import type { HumanReview, HumanReviews, LiteratureProfile } from "@/lib/literature";

const MAX_PROFILES = 5;

export function ScientificLiteratureIntelligence() {
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [profiles, setProfiles] = useState<LiteratureProfile[]>([]);
  const [reviews, setReviews] = useState<HumanReviews>({});
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
      // A new analysis invalidates manual annotations for that PDF.
      setReviews((current) => Object.fromEntries(
        Object.entries(current).filter(([key]) => !key.startsWith(profile.sha256 + ":")),
      ));
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
      ["\uFEFF" + literatureProfileCsv(profiles, reviews)], { type: "text/csv;charset=utf-8" },
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
        <LiteratureReviewMatrix
          profiles={profiles}
          reviews={reviews}
          onReviewChange={(key, change: Partial<HumanReview>) =>
            setReviews((previous) => ({
              ...previous,
              [key]: {
                corrected_value: "",
                note: "",
                reviewed: false,
                ...(previous[key] || {}),
                ...change,
              },
            }))}
          onRemove={(sha) => {
            setProfiles((list) => list.filter((p) => p.sha256 !== sha));
            setReviews((previous) => Object.fromEntries(
              Object.entries(previous).filter(([key]) => !key.startsWith(sha + ":")),
            ));
          }}
          onExport={exportCsv}
        />
      )}

    </section>
  );
}
