/** Client input validation; FastAPI makes all security/role decisions. */
export type MemberRole = "owner" | "editor" | "reviewer" | "viewer";
export type AssignableRole = Exclude<MemberRole, "owner">;

export interface VerifiedIdentity {
  principal_key: string;
  kind: string;
}

export interface ProjectMember {
  principal_key: string;
  role: MemberRole;
  created_at: string;
}

export function isMemberKey(key: unknown): key is string {
  return typeof key === "string" && /^[0-9a-f]{64}$/.test(key);
}

export function isAssignableRole(role: unknown): role is AssignableRole {
  return role === "editor" || role === "reviewer" || role === "viewer";
}

export function isProjectMember(data: unknown): data is ProjectMember {
  if (!data || typeof data !== "object" || Array.isArray(data)) return false;
  const value = data as Partial<ProjectMember>;
  return isMemberKey(value.principal_key) &&
    (value.role === "owner" || isAssignableRole(value.role)) &&
    typeof value.created_at === "string";
}
