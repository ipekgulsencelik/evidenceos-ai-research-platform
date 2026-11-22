# Project authorization and access-decision audit — foundation

## Security status

This milestone defines **domain-level RBAC**, persistence and HTTP authorization
gates in preparation for externally verified OIDC identities.

**It does not provide an OIDC login flow, an identity provider, multi-user sessions
or a production-ready multi-tenant system.** The existing `local` and
`service_token` authentication modes retain **single-operator** privileges,
including access to all projects. Do not expose the current system to the
public internet or use patient-identifiable or confidential research data.

## Explicit project permissions

| Role | Read | Save/edit | Submit human review | Manage members / view access audit |
| --- | --- | --- | --- | --- |
| Owner | yes | yes | yes | yes |
| Editor | yes | yes | yes | no |
| Reviewer | yes | no | yes | no |
| Viewer | yes | no | no | no |

The shared domain policy, rather than HTTP code, defines allowed actions.
The FastAPI composition root attaches a project-permission dependency to
all existing research routers. Stateless academic search and other operations
with **no** `project_id` remain protected by existing authentication but
are not project-scoped.

In a future OIDC mode, `Principal` must be created **only** after the ID
provider's access token has been cryptographically verified. Client-supplied
`X-User` or `X-Role` headers must never become the identity source.

Denied project access returns 404 to avoid disclosing projects to other
users. Project listings use a **membership-filtered SQL query**, rather than
loading a global list and filtering after the database query.

## PostgreSQL migration 0005

- `project_memberships`: composite `(project_id, principal_key)` key,
  project FK, role check constraint and a principal lookup index.
- `access_decision_events`: append-only application repository, pseudonymous
  actor key, optional project ID, action, permission outcome, request ID and time.
  The project field deliberately lacks a cascade FK so deleted projects do not
  silently erase past access decisions.

The actor key is a deterministic SHA-256 representation of the issuer and
subject; it is pseudonymous, **not anonymized**. Never log access tokens,
subject strings, request bodies or confidential document content.

The log records **permission decisions**, not actual operation completion.
Successful project creation and role assignment are logged in the same
transaction as their database changes. Project write authorization decisions
are recorded before the requested operation; a later failed operation does
not change the authorization outcome.

The privileged `GET /api/v1/projects/{project_id}/access-audit` endpoint
shows up to 100 recent decisions. Only owners (or single-operator mode) may
read it. These records are **not** a tamper-proof or complete forensic audit
trail; database administrators can still change or delete data.

## Existing projects and rollout

**Do not automatically assign ownership of legacy projects to the first
person who signs in.** Migration 0005 adds no default memberships. In
future multi-user mode, existing unclaimed projects must be explicitly
assigned to known identities using a controlled, authenticated administrator
migration. Until then, they remain inaccessible to nonoperator identities.

Local mode remains backward compatible and no project binaries are moved.
The existing `.env` and PostgreSQL volume must be retained. Run

```powershell
git switch main
git pull origin main
docker compose up --build -d
docker compose ps
```

Never run `docker compose down -v` unless deliberately deleting the data.

## Next phase, not part of this PR

1. OIDC issuer/JWKS access-token verification, issuer/audience/expiry checks,
   key rotation and an enforced public-client PKCE login flow.
2. Browser-to-API session handling with secure HttpOnly cookies, CSRF
   protection, refresh/token rotation and TLS at a trusted origin.
3. Trustworthy membership administration with owner-scoped invitation,
   grant/revoke flows, and explicit migration for legacy projects.
4. Audit read-access and retention policies, actor attribution from verified
   identities, event integrity protection and security tests.

Do **not** claim enterprise readiness or launch a multi-user service on
the basis of this RBAC foundation alone.
