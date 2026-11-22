# Owner-managed project memberships

EvidenceOS manages project access with issuer-scoped pseudonymous keys derived
only from cryptographically verified OIDC identities. A user **cannot**
identify or authorize another user by sending an email address or arbitrary
`sub` claim to the API.

## User workflow

1. Sign in through the organization's configured OIDC identity provider.
2. Open **Projects & members** in the research workspace sidebar.
3. Copy **Your verified identity key** from `/api/identity`, and share it with
   the project owner through a trusted, independently verified channel.
4. The owner opens **Manage members** for their project, enters the exact key
   and assigns **viewer**, **reviewer** or **editor**. The owner can later
   change or remove those non-owner memberships.
5. To revoke a member, use **Remove access** and confirm. The API transaction
   removes the membership; all subsequent project actions are denied on their
   next authorization check.

This release does **not** implement email invitations, automatic directory
lookups, SCIM synchronization, ownership transfer or legacy project claiming.
The owner's responsibility is to verify that the shared pseudonymous key
belongs to the intended account; raw keys alone do not prove a person's name.

## API endpoints

All routes require authentication. Project-scoped membership routes require
`MANAGE_MEMBERS` in both the project permission dependency and the application
use case. For OIDC principals, this is equivalent to the **owner** role.

| Method | Route | Permission |
| --- | --- | --- |
| GET | `/api/v1/identity` | Authenticated user |
| GET | `/api/v1/projects/{project_id}/memberships` | Owner |
| PUT | `/api/v1/projects/{project_id}/memberships/{principal_key}` | Owner |
| DELETE | `/api/v1/projects/{project_id}/memberships/{principal_key}` | Owner |

PUT body: `{"role":"viewer"}`, `{"role":"reviewer"}` or
`{"role":"editor"}`. The target key must be exactly 64 lowercase hex
characters. Unknown fields and invalid role values receive HTTP 422.
Attempting to change a project's owner returns HTTP 409.
Unauthorized projects and membership listings return HTTP 404 without
enumerating other users' data.

### Security invariants

- The owner row cannot be demoted, removed or modified through the user-facing
  member administration API. New owners cannot be granted through this path.
  Explicit ownership transfer requires a separate audited workflow.
- Membership revocation is enforced by the API's existing per-request RBAC
  authorization. It is not tied to token expiry or browser session termination.
- Changes and denied owner-only operations emit pseudonymous access-decision
  audit records. Logs contain no JWT bearer tokens, passwords or provider
  credentials. Audit history remains application-level, not tamper-proof.
- There is a maximum of 100 memberships returned per project. Larger
  administrative directories need a paginated extension before production
  adoption.
- In the localhost single-operator modes, the existing operator principal
  retains administrative access. Multi-user deployment requires trusted OIDC
  with a tested provider, HTTPS, and the Redis session allowlist.

## Validation

Unit/API tests cover cross-user project isolation, owner-only membership GET
and mutations, blocked owner reassignment, malformed keys/roles, correct
identity mapping, the final revoke state and audit events. A PostgreSQL
integration test exercises persistence and revocation with the real repository.

The CI checks in this repository do not perform an end-to-end sign-in against
a live organization IdP. No IdP test account, client secret or real bearer
token is stored in the repository. Provider-specific end-to-end testing,
ownership migration and security review are separate launch requirements.
