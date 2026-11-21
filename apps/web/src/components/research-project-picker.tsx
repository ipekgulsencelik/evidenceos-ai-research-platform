"use client";

import { useEffect, useState, type FormEvent } from "react";
import { FolderOpen, Plus } from "lucide-react";

import {
  isResearchProject, validateProjectTitle,
} from "@/lib/workspace";
import type { ResearchProject } from "@/lib/workspace";

interface Props {
  projectId: string;
  onSelect: (projectId: string) => void;
}

function apiError(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "detail" in payload
      && typeof payload.detail === "string") return payload.detail;
  return fallback;
}

export function ResearchProjectPicker({ projectId, onSelect }: Props) {
  const [projects, setProjects] = useState<ResearchProject[]>([]);
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/projects", { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        const value: unknown = await response.json().catch(() => null);
        if (!response.ok) throw new Error(apiError(value, "Unable to load projects."));
        if (!Array.isArray(value) || !value.every(isResearchProject)) {
          throw new Error("Unexpected project list response.");
        }
        if (!controller.signal.aborted) {
          setProjects(value.filter((project) => project.domain === "academic"));
        }
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Unable to load projects.");
        }
      });
    return () => controller.abort();
  }, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const issue = validateProjectTitle(title);
    if (issue) { setError(issue); return; }
    setCreating(true);
    setError(null);
    try {
      const response = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim(), domain: "academic" }),
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(apiError(payload, "Project creation failed."));
      if (!isResearchProject(payload)) throw new Error("Unexpected project response.");
      setProjects((previous) => [payload, ...previous]);
      setTitle("");
      onSelect(payload.id);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Project creation failed.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <section className="literature-project-picker" aria-label="Persistent research project">
      <div className="review-heading">
        <div>
          <h4 className="panel-title">Research workspace</h4>
          <p className="panel-subtitle">
            Choose a PostgreSQL project to save AI analysis, notes and review history.
            Session-only mode keeps nothing after refresh.
          </p>
        </div>
        <FolderOpen size={20} aria-hidden="true" />
      </div>
      <label htmlFor="literature-project-select" className="field-label">
        Destination project
      </label>
      <select className="field" id="literature-project-select"
        value={projectId} onChange={(event) => onSelect(event.target.value)}>
        <option value="">Temporary session — do not save</option>
        {projects.map((project) => (
          <option key={project.id} value={project.id}>{project.title}</option>
        ))}
      </select>
      <form className="literature-create-project" onSubmit={create}>
        <label className="field-label" htmlFor="new-project-title">
          Create academic research project
        </label>
        <div className="literature-create-row">
          <input id="new-project-title" className="field" type="text"
            placeholder="e.g. Adolescents and AI literature review"
            maxLength={160} minLength={3} value={title}
            onChange={(event) => setTitle(event.target.value)} />
          <button type="submit" className="secondary-btn" disabled={creating}>
            <Plus size={15} /> {creating ? "Creating…" : "Create project"}
          </button>
        </div>
      </form>
      <p className="review-caveat">
        Local development only. Projects have no accounts or access controls yet.
        Do not expose this service publicly or store sensitive/unpublished documents.
        Source excerpts, structured analyses and review notes are stored; PDF files are not.
      </p>
      {error && <p className="alert" role="alert">{error}</p>}
    </section>
  );
}
