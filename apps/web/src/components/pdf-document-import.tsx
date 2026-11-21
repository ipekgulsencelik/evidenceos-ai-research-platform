"use client";

import { useState, type ChangeEvent } from "react";
import { Check, CircleAlert, FileSearch, FileUp, LoaderCircle } from "lucide-react";

import type { EvidenceSource } from "@/lib/evidence";
import { isPdfReview, validatePdfUpload } from "@/lib/document";
import type { PdfReview } from "@/lib/document";

interface Props {
  claim: string;
  onUse: (passages: EvidenceSource[]) => void;
}

export function PdfDocumentImport({ claim, onUse }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<PdfReview | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function changeFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    setResult(null);
    setSelected([]);
    setError(null);
  }

  async function extract() {
    const issue = validatePdfUpload(file, claim);
    if (issue) { setError(issue); return; }
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("claim", claim.trim());
      const response = await fetch("/api/documents/retrieve-passages", {
        method: "POST",
        body,
        cache: "no-store",
      });
      const output: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = output && typeof output === "object" && "detail" in output
          && typeof output.detail === "string" ? output.detail : "PDF extraction failed.";
        throw new Error(detail);
      }
      if (!isPdfReview(output)) throw new Error("Unexpected PDF extraction response.");
      setResult(output);
      setSelected(output.passages.map((candidate) => candidate.source_id));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "PDF extraction failed.");
    } finally {
      setLoading(false);
    }
  }

  function useSelected() {
    if (!result) return;
    const picked = result.passages
      .filter((candidate) => selected.includes(candidate.source_id))
      .map(({ source_id, title, locator, passage }): EvidenceSource => ({
        source_id, title, locator, passage,
      }));
    if (picked.length === 0) {
      setError("Select at least one candidate passage.");
      return;
    }
    onUse(picked);
    setError(null);
    document.getElementById("evidence-claim")?.scrollIntoView({
      behavior: "smooth", block: "center",
    });
  }

  function toggle(id: string) {
    setSelected((ids) => ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id]);
  }

  return (
    <section className="pdf-import" aria-labelledby="pdf-import-heading">
      <div className="review-heading">
        <div>
          <h4 className="panel-title" id="pdf-import-heading">Import evidence passages from PDF</h4>
          <p className="panel-subtitle">
            Write your claim above, select a searchable PDF, and retrieve candidate excerpts by page.
          </p>
        </div>
        <FileUp size={22} aria-hidden="true" />
      </div>
      <p className="review-caveat">
        Local text extraction only: no upload is stored and no PDF text goes to Groq here.
        Up to 8 MiB / 30 pages. Scanned files require OCR and are not supported.
        Only upload documents you are permitted to process.
      </p>
      <div className="pdf-upload-controls">
        <label htmlFor="pdf-upload" className="field-label">PDF document</label>
        <input id="pdf-upload" className="field" type="file" accept=".pdf,application/pdf"
          onChange={changeFile} aria-describedby="pdf-import-hint" />
        <button type="button" className="secondary-btn" onClick={extract} disabled={loading}>
          {loading ? <LoaderCircle size={15} className="spinner" /> : <FileSearch size={15} />}
          {loading ? "Finding passages…" : "Find passages"}
        </button>
      </div>
      <p className="panel-subtitle" id="pdf-import-hint">
        Candidate ranking uses keyword overlap, not an AI confidence score.
      </p>
      {error && <div className="alert" role="alert"><CircleAlert size={16} />{error}</div>}
      {result && <div aria-live="polite" className="pdf-retrieval-result">
        <p className="pdf-summary">
          <strong>{result.title}</strong> — {result.text_page_count}/{result.page_count}
          {" "}pages with extractable text; {result.passages.length} candidate(s).
        </p>
        {result.passages.map((candidate) => (
          <label key={candidate.source_id} className="pdf-candidate">
            <span className="pdf-candidate-heading">
              <input type="checkbox" checked={selected.includes(candidate.source_id)}
                onChange={() => toggle(candidate.source_id)} />
              <strong>{candidate.locator}</strong>
              <span>Matched terms: {candidate.matched_terms.join(", ")}</span>
            </span>
            <span className="pdf-candidate-excerpt">{candidate.passage}</span>
          </label>
        ))}
        <p className="review-caveat">{result.caveat}</p>
        {result.passages.length > 0 && (
          <button type="button" className="secondary-btn" onClick={useSelected}
            disabled={selected.length === 0}>
            <Check size={15} /> Use selected excerpts in assessment
          </button>
        )}
      </div>}
    </section>
  );
}
