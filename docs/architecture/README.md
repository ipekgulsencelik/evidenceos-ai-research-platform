# Architecture overview

EvidenceOS uses a modular monolith with concentric dependencies:

`presentation -> application -> domain <- infrastructure`

The application layer knows only domain ports. Dependency wiring is performed
by the API composition root. SQLAlchemy, FastAPI, and provider clients are not
permitted in the domain or application packages.

**Transaction boundary:** each use case opens and commits a Unit of Work.
Rollback on exception is handled by the UoW's context manager.

**Modules planned:** `academic`, `legal`, `evidence`, `citations`, `identity`.
The foundational release implements a project aggregate and supporting persistence.
Other modules are *not* implemented in Phase 1 foundation.

**Known gaps:** authentication/authorization, API rate limiting, full audit events,
secret rotation, migrations against multiple Postgres versions, real source connectors,
and semantic claim verification. Do not expose this app publicly before these are designed.
