"use client";

import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { CheckCircle2, CircleAlert, FileText, LoaderCircle } from "lucide-react";
import { LiteratureReviewMatrix } from "@/components/literature-review-matrix";
import { ResearchProjectPicker } from "@/components/research-project-picker";

import {
  isLiteratureProfile, literatureProfileCsv, reviewKey, validateLiteratureUpload,
} from "@/lib/literature";
import type {
  HumanReview, HumanReviews, LiteratureProfile, MatrixRow,
} from "@/lib/literature";
import {
  isReviewRevision, isSavedLiteratureEntry, latestReviews,
} from "@/lib/workspace";
import type { ReviewRevision, SavedLiteratureEntry } from "@/lib/workspace";

const MAX_PROFILES = 5;

function getWorkspaceError(value: unknown, fallback: string): string {
  if (value && typeof value === "object" && "detail" in value &&
    typeof value.detail === "string") return value.detail;
  return fallback;
}


export function ScientificLiteratureIntelligence() {
  const [file, setFile] = useState<File | null>(null);
  const [projectId, setProjectId] = useState("");
  const [recordIds, setRecordIds] = useState<Record<string, string>>({});
  const [histories, setHistories] = useState<Record<string, ReviewRevision[]>>({});
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [loadingSaved, setLoadingSaved] = useState(false);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [savedKey, setSavedKey] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [profiles, setProfiles] = useState<LiteratureProfile[]>([]);
  const [reviews, setReviews] = useState<HumanReviews>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);


  useEffect(() => {
    setProfiles([]);
    setReviews({});
    setRecordIds({});
    setHistories({});
    setWorkspaceError(null);
    setSavedKey(null);
    if (!projectId) {
      setLoadingSaved(false);
      return;
    }

    const controller = new AbortController();
    setLoadingSaved(true);
    async function loadSaved() {
      try {
        const response = await fetch("/api/projects/" + projectId + "/literature", {
          cache: "no-store", signal: controller.signal,
        });
        const data: unknown = await response.json().catch(() => null);
        if (!response.ok) {
          throw new Error(getWorkspaceError(data, "Unable to load saved literature."));
        }
        if (!Array.isArray(data) || !data.every(isSavedLiteratureEntry)) {
          throw new Error("Unexpected saved-literature response.");
        }
        const records: SavedLiteratureEntry[] = [];
        const seen = new Set<string>();
        for (const entry of data) {
          if (seen.has(entry.profile.sha256)) continue;
          seen.add(entry.profile.sha256);
          records.push(entry);
          if (records.length === MAX_PROFILES) break;
        }
        const responseHistory = await Promise.all(records.map(async (entry) => {
          const answer = await fetch(
            "/api/projects/" + projectId + "/literature/" + entry.id + "/reviews",
            { cache: "no-store", signal: controller.signal },
          );
          const value: unknown = await answer.json().catch(() => null);
          if (!answer.ok) throw new Error(getWorkspaceError(value, "Unable to load review history."));
          if (!Array.isArray(value) || !value.every(isReviewRevision)) {
            throw new Error("Unexpected reviewer history response.");
          }
          return { entry, revisions: value as ReviewRevision[] };
        }));
        if (controller.signal.aborted) return;
        setProfiles(records.map((entry) => entry.profile));
        setRecordIds(Object.fromEntries(
          records.map((entry) => [entry.profile.sha256, entry.id]),
        ));
        const restored: HumanReviews = {};
        for (const { entry, revisions } of responseHistory) {
          const previous = latestReviews(revisions);
          for (const facet of entry.profile.findings.map((finding) => finding.facet)) {
            const review = previous[facet];
            if (review) restored[reviewKey(entry.profile.sha256, facet)] = review;
          }
        }
        setReviews(restored);
      } catch (failure) {
        if (!controller.signal.aborted) {
          setWorkspaceError(
            failure instanceof Error ? failure.message : "Unable to load saved literature.",
          );
        }
      } finally {
        if (!controller.signal.aborted) setLoadingSaved(false);
      }
    }
    void loadSaved();
    return () => controller.abort();
  }, [projectId]);

  async function saveReview(row: MatrixRow) {
    const entryId = recordIds[row.profile.sha256];
    if (!projectId || !entryId) {
      setWorkspaceError("This analysis is not saved in the selected project.");
      return;
    }
    const review = reviews[row.key] || { corrected_value: "", note: "", reviewed: false };
    setSavingKey(row.key);
    setSavedKey(null);
    setWorkspaceError(null);
    try {
      const response = await fetch(
        "/api/projects/" + projectId + "/literature/" + entryId + "/reviews",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ facet: row.finding.facet, ...review }),
        },
      );
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(getWorkspaceError(data, "Unable to save review."));
      if (!isReviewRevision(data)) throw new Error("Unexpected saved review response.");
      setSavedKey(row.key);
      setHistories((previous) => (
        previous[row.key] ? { ...previous, [row.key]: [data, ...previous[row.key]] } : previous
      ));
    } catch (failure) {
      setWorkspaceError(failure instanceof Error ? failure.message : "Unable to save review.");
    } finally {
      setSavingKey(null);
    }
  }

  async function loadReviewHistory(row: MatrixRow) {
    const entryId = recordIds[row.profile.sha256];
    if (!projectId || !entryId) return;
    setWorkspaceError(null);
    try {
      const response = await fetch(
        "/api/projects/" + projectId + "/literature/" + entryId + "/reviews",
        { cache: "no-store" },
      );
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(getWorkspaceError(data, "Unable to load revision history."));
      if (!Array.isArray(data) || !data.every(isReviewRevision)) {
        throw new Error("Unexpected review history response.");
      }
      setHistories((previous) => ({
        ...previous,
        [row.key]: data.filter((revision) => revision.facet === row.finding.facet),
      }));
    } catch (failure) {
      setWorkspaceError(
        failure instanceof Error ? failure.message : "Unable to load revision history.",
      );
    }
  }

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
      const path = projectId
        ? "/api/projects/" + projectId + "/literature/analyze-pdf"
        : "/api/literature/analyze-pdf";
      const response = await fetch(path, {
        method: "POST", body: form, cache: "no-store",
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(getWorkspaceError(body, "Literature extraction failed."));
      }
      let profile: LiteratureProfile;
      if (projectId) {
        if (!isSavedLiteratureEntry(body) || body.project_id !== projectId) {
          throw new Error("Unexpected persistent literature response.");
        }
        profile = body.profile;
        setRecordIds((current) => ({ ...current, [profile.sha256]: body.id }));
      } else {
        if (!isLiteratureProfile(body)) {
          throw new Error("Unexpected literature service response.");
        }
        profile = body;
      }
      setProfiles((current) => {
        const other = current.filter((p) => p.sha256 !== profile.sha256);
        return [...other, profile].slice(-MAX_PROFILES);
      });
      // A new analysis invalidates manual annotations for that PDF.
      setReviews((current) => Object.fromEntries(
        Object.entries(current).filter(([key]) => !key.startsWith(profile.sha256 + ":")),
      ));
      setConsent(false);
      setHistories({});
      setSavedKey(null);
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

      <ResearchProjectPicker projectId={projectId} onSelect={setProjectId} />
      {loadingSaved && <p role="status" className="panel-subtitle">
        Loading saved research records from PostgreSQL…
      </p>}
      {workspaceError && <p className="alert" role="alert">{workspaceError}</p>}
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
                ...(previous[key] ?? { corrected_value: "", note: "", reviewed: false }),
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
          persistent={Boolean(projectId)}
          onSaveReview={projectId ? (row) => { void saveReview(row); } : undefined}
          onLoadHistory={projectId ? (row) => { void loadReviewHistory(row); } : undefined}
          history={histories}
          savingKey={savingKey}
          savedKey={savedKey}
        />
      )}

    </section>
  );
}
