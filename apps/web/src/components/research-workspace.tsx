"use client";

import {
  ArrowDownRight,
  ArrowRight,
  BookMarked,
  BookOpenText,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  ClipboardCheck,
  ExternalLink,
  FileSearch,
  Fingerprint,
  FlaskConical,
  GitBranch,
  Info,
  Layers3,
  LoaderCircle,
  LockKeyhole,
  PanelTop,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { EvidenceReview } from "@/components/evidence-review";

import {
  getPublicationRange,
  getResponseError,
  getShortAuthors,
  validateCitation,
  validateSearch,
} from "@/lib/academic";
import type { AcademicWork, CitationCheck } from "@/lib/academic";

type SearchState = "idle" | "loading" | "success" | "error";
type VerifyState = "idle" | "loading" | "success" | "error";

function safeExternalUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : undefined;
  } catch {
    return undefined;
  }
}

async function readApiResponse<T>(response: Response): Promise<T> {
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data && typeof data === "object" && "detail" in data
      && typeof data.detail === "string" ? data.detail : undefined;
    throw new Error(getResponseError(response.status, detail));
  }
  return data as T;
}

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark"><Layers3 size={22} strokeWidth={1.75} /></span>
        <span><div className="brand-title">EvidenceOS</div><div className="brand-subtitle">Research intelligence</div></span>
      </div>
      <nav aria-label="Workspace navigation">
        <p className="side-label">Workspace</p>
        <div className="side-group">
          <a className="side-link" href="#overview"><PanelTop size={17} /> Overview</a>
          <a className="side-link active" aria-current="page" href="#research-search"><BookOpenText size={17} /> Academic Research</a>
          <a className="side-link" href="#citation-verification"><ShieldCheck size={17} /> DOI Verification</a>
          <a className="side-link" href="#evidence-review"><FileSearch size={17} /> Evidence Review</a>
        </div>
        <div className="side-separator" />
        <p className="side-label">Coming later</p>
        <div className="side-group">
          <div className="side-link dim"><BookMarked size={17} /> Legal Research <span className="soon">SOON</span></div>
          <div className="side-link dim"><GitBranch size={17} /> Evidence Graph <span className="soon">SOON</span></div>
          <div className="side-link dim"><FlaskConical size={17} /> Research Gaps <span className="soon">SOON</span></div>
        </div>
      </nav>
      <div className="sidebar-foot">
        <div className="sidebar-status"><span className="online-dot" /> Research workspace</div>
        <div>Academic module · v0.2</div>
        <div style={{ marginTop: 10, fontSize: 11, lineHeight: 1.5 }}>Source-backed metadata. Claim verification is not yet available.</div>
      </div>
    </aside>
  );
}

function WorkCard({ work, onVerify, onReview }: { work: AcademicWork; onVerify: (work: AcademicWork) => void; onReview: (work: AcademicWork) => void }) {
  const safeUrl = safeExternalUrl(work.source_url);
  return (
    <article className="work-card">
      <div className="work-head"><span className="work-type">Research paper</span><span className="work-year">{work.publication_year ?? "Year unknown"}</span></div>
      <h3 className="work-title">{work.title}</h3>
      <p className="work-authors">{getShortAuthors(work.authors)}</p>
      <div className="work-bottom">
        <p className="work-doi">{work.doi ? `DOI: ${work.doi}` : "DOI not available"}</p>
        <div className="work-actions">
          <button className="link-btn" type="button" onClick={() => onReview(work)}><FileSearch size={13} /> Analyze passage</button>
          {work.doi && <button className="link-btn" type="button" onClick={() => onVerify(work)}><Fingerprint size={13} /> Verify DOI</button>}
          {safeUrl && <a className="link-btn" href={safeUrl} target="_blank" rel="noreferrer noopener" aria-label={`Open source for ${work.title}`}><ExternalLink size={13} /> Source</a>}
        </div>
      </div>
    </article>
  );
}

function VerificationResult({ check }: { check: CitationCheck }) {
  const status = check.status;
  const verified = status === "verified";
  const mismatch = status === "title_mismatch";
  const title = verified ? "Bibliographic metadata verified" : mismatch ? "Title mismatch found" : "DOI not found in Crossref";
  const description = verified
    ? "Crossref has a record for this DOI, and its title matches the expected title if supplied. This does not verify scientific claims."
    : mismatch
      ? "Crossref returned this DOI, but the title does not match the expected title. Check the details below."
      : "Crossref has no record for this DOI. Another DOI registration agency may still have it.";
  const url = check.metadata ? safeExternalUrl(check.metadata.source_url) : undefined;
  return (
    <div className={`result-box ${verified ? "" : mismatch ? "warning" : "neutral"}`} role="status">
      <div className="result-heading">{verified ? <CheckCircle2 size={16} /> : <CircleAlert size={16} />}{title}</div>
      <p className="result-description">{description}</p>
      {check.metadata && (
        <div style={{ marginTop: 13, fontSize: 12, color: "#355662", lineHeight: 1.65 }}>
          <strong>{check.metadata.title}</strong>
          <div>{check.metadata.publication_year ?? "Year not available"}</div>
          {url && <a href={url} target="_blank" rel="noreferrer noopener" style={{ display: "inline-flex", alignItems: "center", gap: 5, marginTop: 4, color: "#147f78" }}>View DOI record <ExternalLink size={12} /></a>}
        </div>
      )}
    </div>
  );
}

export function ResearchWorkspace() {
  const [reviewWork, setReviewWork] = useState<AcademicWork | null>(null);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(10);
  const [works, setWorks] = useState<AcademicWork[]>([]);
  const [searchState, setSearchState] = useState<SearchState>("idle");
  const [searchError, setSearchError] = useState<string | null>(null);
  const [previousQuery, setPreviousQuery] = useState("");
  const [doi, setDoi] = useState("");
  const [expectedTitle, setExpectedTitle] = useState("");
  const [check, setCheck] = useState<CitationCheck | null>(null);
  const [verifyState, setVerifyState] = useState<VerifyState>("idle");
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const searchController = useRef<AbortController | null>(null);
  const verifyController = useRef<AbortController | null>(null);

  async function searchWorks(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const issue = validateSearch(query, limit);
    if (issue) { setSearchError(issue); setSearchState("error"); return; }
    searchController.current?.abort();
    const controller = new AbortController();
    searchController.current = controller;
    setSearchState("loading");
    setSearchError(null);
    setWorks([]);
    try {
      const params = new URLSearchParams({ query: query.trim(), limit: String(limit) });
      const response = await fetch(`/api/academic/works?${params.toString()}`, { signal: controller.signal, cache: "no-store" });
      const results = await readApiResponse<AcademicWork[]>(response);
      if (controller.signal.aborted) return;
      if (!Array.isArray(results)) throw new Error("Unexpected response from research service.");
      setWorks(results);
      setPreviousQuery(query.trim());
      setSearchState("success");
    } catch (error) {
      if (controller.signal.aborted) return;
      setSearchError(error instanceof Error ? error.message : "Search failed.");
      setSearchState("error");
    }
  }

  async function verifyCitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const issue = validateCitation(doi, expectedTitle);
    if (issue) { setVerifyError(issue); setVerifyState("error"); return; }
    verifyController.current?.abort();
    const controller = new AbortController();
    verifyController.current = controller;
    setVerifyState("loading");
    setVerifyError(null);
    setCheck(null);
    try {
      const response = await fetch("/api/academic/citations/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doi: doi.trim(), expected_title: expectedTitle.trim() || null }),
        signal: controller.signal,
      });
      const result = await readApiResponse<CitationCheck>(response);
      if (controller.signal.aborted) return;
      setCheck(result);
      setVerifyState("success");
    } catch (error) {
      if (controller.signal.aborted) return;
      setVerifyError(error instanceof Error ? error.message : "Verification failed.");
      setVerifyState("error");
    }
  }

  function chooseForReview(work: AcademicWork) {
    setReviewWork(work);
    document.getElementById("evidence-review")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function chooseForVerification(work: AcademicWork) {
    verifyController.current?.abort();
    setDoi(work.doi || "");
    setExpectedTitle(work.title);
    setCheck(null);
    setVerifyError(null);
    setVerifyState("idle");
    document.getElementById("citation-verification")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  const doiCount = works.filter((work) => Boolean(work.doi)).length;
  return (
    <div className="layout-shell">
      <Sidebar />
      <div className="main-panel">
        <header className="headerbar"><div className="breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>Academic Research</strong></div><div className="header-right"><span>Evidence-first discovery</span><div className="avatar" aria-label="EvidenceOS">E</div></div></header>
        <main className="page-container" id="overview">
          <p className="eyebrow">EvidenceOS / Research intelligence</p>
          <h1 className="hero-title">Discover research.<br /><span>Verify the evidence.</span></h1>
          <p className="hero-desc">Search real academic records from OpenAlex and validate DOI metadata against Crossref — all in one transparent research workspace.</p>
          <div className="mode-row"><span className="mode-chip"><BookOpenText size={14} /> Academic Mode <Check size={13} /></span><span className="mode-chip disabled"><LockKeyhole size={13} /> Legal Mode · Coming soon</span></div>
          <section className="card search-panel" id="research-search" aria-labelledby="search-title">
            <h2 className="panel-title" id="search-title">Explore academic literature</h2>
            <p className="panel-subtitle">Results are retrieved live from OpenAlex. No fabricated sample citations.</p>
            <form onSubmit={searchWorks}>
              <div className="search-row">
                <div className="input-wrap"><Search size={17} className="input-icon" aria-hidden="true" /><input className="field search-field" aria-label="Research topic" value={query} maxLength={200} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. artificial intelligence and adolescents" required minLength={3} /></div>
                <select className="field search-limit" aria-label="Number of search results" value={limit} onChange={(e) => setLimit(Number(e.target.value))}><option value={5}>5 results</option><option value={10}>10 results</option><option value={20}>20 results</option><option value={25}>25 results</option></select>
                <button type="submit" className="primary-btn" disabled={searchState === "loading"}>{searchState === "loading" ? <LoaderCircle size={16} className="spinner" /> : <Search size={16} />}{searchState === "loading" ? "Searching…" : "Search papers"}<ArrowRight size={15} /></button>
              </div>
            </form>
            <p className="hint-line"><Info size={12} /> Search is live and requires an OpenAlex API key in your local backend settings.</p>
            {searchError && <div role="alert" className="alert"><CircleAlert size={16} style={{ flexShrink: 0 }} />{searchError}</div>}
          </section>
          <div className="dashboard-grid">
            <section aria-labelledby="results-heading">
              <div className="section-heading"><div><h2 id="results-heading">Research results</h2><p>{searchState === "success" ? `Showing records for “${previousQuery}”` : "Live academic records with source links"}</p></div><span className="count-pill">{searchState === "success" ? `${works.length} results` : "OpenAlex"}</span></div>
              {searchState === "success" && <div className="stats-row"><div className="stat-card"><div className="stat-label">Sources found</div><div className="stat-value">{works.length}</div><div className="stat-note">Current search</div></div><div className="stat-card"><div className="stat-label">With DOI</div><div className="stat-value">{doiCount}</div><div className="stat-note">Metadata identifiers</div></div><div className="stat-card"><div className="stat-label">Publication years</div><div className="stat-value">{getPublicationRange(works)}</div><div className="stat-note">Among returned results</div></div></div>}
              <div className="card" aria-live="polite">
                {searchState === "loading" ? <div className="empty-state"><div className="empty-icon"><LoaderCircle className="spinner" size={25} /></div><strong>Searching academic records…</strong><p>Requesting sources from OpenAlex.</p></div>
                  : searchState === "success" && works.length > 0 ? works.map((work) => <WorkCard key={work.source_id} work={work} onVerify={chooseForVerification} onReview={chooseForReview} />)
                  : <div className="empty-state"><div className="empty-icon"><FileSearch size={25} strokeWidth={1.7} /></div><strong>{searchState === "success" ? "No matching records" : "Your research starts here"}</strong><p>{searchState === "success" ? "Try another term or broader topic." : "Enter a research topic above to discover real papers, author lists, publication years, and DOIs."}</p></div>}
              </div>
            </section>
            <aside aria-label="Citation verification and research notes">
              <section className="card panel-pad" id="citation-verification" aria-labelledby="verification-title">
                <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#19857d", marginBottom: 12 }}><ClipboardCheck size={20} /><span style={{ fontSize: 10, fontWeight: 750, letterSpacing: 1.1, textTransform: "uppercase" }}>Citation intelligence</span></div>
                <h2 className="small-title" id="verification-title">Verify a DOI</h2>
                <p className="small-sub">Cross-check a DOI and optionally match the article title against Crossref metadata.</p>
                <form onSubmit={verifyCitation}>
                  <label htmlFor="doi" className="field-label">Digital Object Identifier</label>
                  <input className="field" id="doi" placeholder="10.1016/j.jadohealth.2020..." value={doi} maxLength={300} onChange={(e) => { setDoi(e.target.value); setCheck(null); }} required />
                  <label htmlFor="expected-title" className="field-label">Expected title <span style={{ fontWeight: 400, color: "#9cabb1" }}>(optional)</span></label>
                  <input className="field" id="expected-title" placeholder="Article title to compare" value={expectedTitle} maxLength={500} onChange={(e) => { setExpectedTitle(e.target.value); setCheck(null); }} />
                  <button className="primary-btn" type="submit" disabled={verifyState === "loading"} style={{ width: "100%", marginTop: 19 }}>{verifyState === "loading" ? <LoaderCircle size={16} className="spinner" /> : <ShieldCheck size={16} />}{verifyState === "loading" ? "Checking DOI…" : "Verify citation"}<ArrowRight size={15} /></button>
                </form>
                {verifyError && <div role="alert" className="alert"><CircleAlert size={16} style={{ flexShrink: 0 }} />{verifyError}</div>}
                {verifyState === "success" && check && <VerificationResult check={check} />}
                <p className="hint-line" style={{ lineHeight: 1.65, alignItems: "flex-start" }}><LockKeyhole size={12} style={{ flexShrink: 0, marginTop: 3 }} />Metadata verification does not establish that a publication supports a scientific claim.</p>
              </section>
              <div className="info-panel"><div className="info-heading"><Sparkles size={16} /> An evidence-first workflow</div><p>Every paper links to its source. DOI matches are checked with Crossref; deeper claim verification and legal research are planned for future releases.</p></div>
              <div style={{ display: "flex", gap: 7, alignItems: "center", color: "#92a3aa", fontSize: 11, padding: "23px 6px" }}><ArrowDownRight size={14} /> Built for transparent academic discovery</div>
            </aside>
          </div>
          <EvidenceReview works={works} selectedWork={reviewWork} />
        </main>
      </div>
    </div>
  );
}
