"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";

import {
  isAssignableRole, isMemberKey, isOidcIdentity, isProjectMember,
  type AssignableRole, type ProjectMember, type VerifiedIdentity,
} from "@/lib/memberships";
import { isResearchProject, type ResearchProject } from "@/lib/workspace";

async function jsonResponse<T>(response: Response): Promise<T> {
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body && typeof body === "object" && "detail" in body &&
      typeof body.detail === "string" ? body.detail : undefined;
    throw new Error(detail || "The research service rejected this request.");
  }
  return body as T;
}

const panel: React.CSSProperties = {
  background: "#fff", border: "1px solid #dae7e8", borderRadius: 12,
  padding: 24, marginTop: 18,
};

const field: React.CSSProperties = {
  width: "100%", padding: "10px 12px", border: "1px solid #adbfca",
  borderRadius: 7, boxSizing: "border-box",
};

const action: React.CSSProperties = {
  borderRadius: 7, border: "1px solid #2c686a", padding: "9px 14px",
  color: "#fff", background: "#205d62", cursor: "pointer",
};

export function ProjectMembershipManager() {
  const [projects, setProjects] = useState<ResearchProject[]>([]);
  const [identity, setIdentity] = useState<VerifiedIdentity | null>(null);
  const [selected, setSelected] = useState<ResearchProject | null>(null);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [memberKey, setMemberKey] = useState("");
  const [role, setRole] = useState<AssignableRole>("viewer");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [accessDenied, setAccessDenied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load(): Promise<void> {
      try {
        const [meResponse, projectsResponse] = await Promise.all([
          fetch("/api/identity", { cache: "no-store" }),
          fetch("/api/projects", { cache: "no-store" }),
        ]);
        const [me, listed] = await Promise.all([
          jsonResponse<VerifiedIdentity>(meResponse),
          jsonResponse<ResearchProject[]>(projectsResponse),
        ]);
        if (!me || !isMemberKey(me.principal_key) ||
            !Array.isArray(listed) || !listed.every(isResearchProject)) {
          throw new Error("Unexpected identity or project response.");
        }
        if (!cancelled) { setIdentity(me); setProjects(listed); }
      } catch (cause) {
        if (!cancelled) setNotice(cause instanceof Error ? cause.message : "Unable to load projects.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  async function readMembers(project: ResearchProject): Promise<void> {
    setSelected(project);
    setMembers([]);
    setNotice(null);
    setAccessDenied(false);
    setBusy(true);
    try {
      const response = await fetch(
        "/api/projects/" + project.id + "/memberships", { cache: "no-store" },
      );
      if (response.status === 404) {
        setAccessDenied(true);
        return;
      }
      const entries = await jsonResponse<unknown>(response);
      if (!Array.isArray(entries) || !entries.every(isProjectMember)) {
        throw new Error("Unexpected project membership data.");
      }
      setMembers(entries);
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : "Cannot load project members.");
    } finally {
      setBusy(false);
    }
  }

  async function saveMember(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selected || !isOidcIdentity(identity) || !isMemberKey(memberKey) ||
        !isAssignableRole(role) || memberKey === identity.principal_key) {
      setNotice("Provide a verified 64-character member key and a non-owner role.");
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const response = await fetch(
        "/api/projects/" + selected.id + "/memberships/" + memberKey,
        { method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ role }) },
      );
      await jsonResponse<unknown>(response);
      setMemberKey("");
      await readMembers(selected);
      setNotice("Membership saved.");
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : "Cannot update membership.");
    } finally {
      setBusy(false);
    }
  }

  async function revokeMember(principalKey: string): Promise<void> {
    if (!selected || !isOidcIdentity(identity) || !isMemberKey(principalKey)) return;
    if (!window.confirm("Remove this member's access to the project?")) return;
    setBusy(true);
    setNotice(null);
    try {
      const response = await fetch(
        "/api/projects/" + selected.id + "/memberships/" + principalKey,
        { method: "DELETE" },
      );
      if (!response.ok) await jsonResponse<unknown>(response);
      await readMembers(selected);
      setNotice("Membership revoked.");
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : "Cannot revoke membership.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", maxWidth: 950,
      padding: "40px 24px", margin: "0 auto", color: "#16374b", lineHeight: 1.55 }}>
      <Link href="/" style={{ color: "#17666a" }}>Back to research workspace</Link>
      <h1 style={{ marginBottom: 6 }}>Project access management</h1>
      <p>Project membership access is enforced by the API. Only project owners can manage
        memberships when signed in with OIDC.</p>

      <section style={panel} aria-labelledby="identity-title">
        <h2 id="identity-title">
          {isOidcIdentity(identity) ? "Your verified OIDC identity key" : "Authentication mode"}
        </h2>
        {isOidcIdentity(identity) ? (
          <>
            <p>Share this key privately with a project owner so they can grant access.
              It is derived from your verified OIDC identity, not your email address.</p>
            <div style={{ overflowWrap: "anywhere", fontFamily: "monospace", fontSize: 13 }}>
            <code>{identity.principal_key}</code>
            <div style={{ marginTop: 12 }}>
              <button style={action} type="button" onClick={() => {
                void navigator.clipboard.writeText(identity.principal_key).then(
                  () => setNotice("Identity key copied."),
                  () => setNotice("Copy this key manually."),
                );
              }}>Copy identity key</button>
            </div>
          </div>
          </>
        ) : identity ? (
          <p role="status">Local or service-operator mode is active ({identity.kind}).
            This administrative identity is not a verified OIDC user account. A local
            research project may have no owner membership record; multi-user member
            management requires separately configured OIDC sign-in.</p>
        ) : <p>{loading ? "Checking authentication mode…" : "Identity unavailable."}</p>}
      </section>

      <section style={panel} aria-labelledby="projects-title">
        <h2 id="projects-title">Your research projects</h2>
        {loading ? <p>Loading…</p>
          : projects.length === 0 ? <p>No accessible projects yet.</p>
          : (
            <ul style={{ paddingLeft: 20 }}>
              {projects.map((project) => (
                <li key={project.id} style={{ padding: "8px 0" }}>
                  <strong>{project.title}</strong>{" "}
                  <button type="button" style={{ ...action, marginLeft: 10 }}
                    disabled={busy} onClick={() => { void readMembers(project); }}>
                    Manage members
                  </button>
                </li>
              ))}
            </ul>
          )}
      </section>

      {selected && (
        <section style={panel} aria-labelledby="members-title">
          <h2 id="members-title">Members — {selected.title}</h2>
          {accessDenied ? <p role="alert">
            Only a project owner may administer members. Your project remains accessible
            according to your existing role.
          </p> : (
            <>
              <p>Verify the recipient's identity key through a trusted channel
                before granting them access. Ownership transfer is intentionally unavailable.</p>
              {!busy && members.length === 0 && (
                <p role="status">No project memberships are registered.
                  {identity && !isOidcIdentity(identity)
                    ? " This is expected for projects created in local operator mode."
                    : " Check that this project has an assigned OIDC owner."}
                </p>
              )}
              <ul style={{ paddingLeft: 20 }}>
                {members.map((member) => (
                  <li key={member.principal_key} style={{ margin: "12px 0", overflowWrap: "anywhere" }}>
                    <code style={{ fontSize: 12 }}>{member.principal_key}</code>
                    <strong style={{ marginLeft: 10 }}>{member.role}</strong>
                    {member.role !== "owner" && isOidcIdentity(identity) && (
                      <button style={{ ...action, marginLeft: 10, background: "#884034" }}
                        type="button" disabled={busy} onClick={() => {
                          void revokeMember(member.principal_key);
                        }}>Remove access</button>
                    )}
                  </li>
                ))}
              </ul>
              {isOidcIdentity(identity) ? (
              <form onSubmit={(event) => { void saveMember(event); }}
                style={{ display: "grid", gap: 12, maxWidth: 650, marginTop: 20 }}>
                <label>Verified member key
                  <input style={field} value={memberKey} maxLength={64}
                    onChange={(event) => setMemberKey(event.target.value.trim())}
                    placeholder="64-character identity key" spellCheck={false}
                    autoComplete="off" required />
                </label>
                <label>Role
                  <select style={field} value={role} onChange={(event) => {
                    const next = event.target.value;
                    if (isAssignableRole(next)) setRole(next);
                  }}>
                    <option value="viewer">Viewer — read</option>
                    <option value="reviewer">Reviewer — read and review</option>
                    <option value="editor">Editor — read, write and review</option>
                  </select>
                </label>
                <button style={action} type="submit"
                  disabled={busy || !isMemberKey(memberKey) || memberKey === identity?.principal_key}>
                  Save membership
                </button>
              </form>
              ) : (
                <p role="status">Member invitations and role changes are unavailable in
                  this local operator view. Configure an OIDC identity provider and
                  dedicated user accounts to manage access for multiple users.</p>
              )}
            </>
          )}
        </section>
      )}
      {notice && <p role="status" style={{ marginTop: 16 }}>{notice}</p>}
    </main>
  );
}
