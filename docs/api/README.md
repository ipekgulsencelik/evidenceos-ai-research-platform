# API v1 foundation

- `GET /api/v1/health/live` returns `200` when the process is alive.
- `GET /api/v1/health/ready` issues `SELECT 1`; returns `200` on success or `503` if database unavailable.
- `POST /api/v1/projects` accepts `{ "title": "...", "domain": "academic" | "legal" }`; returns `201`.
- `GET /api/v1/projects/{uuid}` returns `200` or `404`.

Every response dispatched through middleware receives `X-Request-ID`.
Request ID is server generated; incoming untrusted request IDs are ignored.

No authentication is implemented in this foundation: bind published port to
localhost only and never use this release with sensitive real-user data.
