# Research Workspace & Literature Management — initial release

## What persists in PostgreSQL

- Academic research projects (title, domain, identifier, created time).
- A versioned-by-snapshot, server-generated AI literature analysis after the
  researcher uploads an authorized, selectable-text PDF and consents to Groq.
- Structured extraction with exact selected quotations, original PDF page
  locators, six study fields, model identifier, rejected-quote explanations,
  document SHA-256 and extraction caveats.
- Reviewer changes as append-only audit revisions (field, correction, note,
  reviewed flag and timestamp). Prior revisions are never overwritten.

PDF binaries and entire extracted full text are **not** persisted. Selected
quotes, AI interpretations and researcher notes **are** persisted. This matters
for confidentiality, copyright and scientific governance.

## Local launch

From the repository root:

    git switch main
    git pull origin main
    docker compose up --build -d
    docker compose ps

The migrate service applies Alembic revision 0002 to your existing PostgreSQL
volume before the API starts. Never run docker compose down -v unless you
intend to erase the PostgreSQL database volume. Keep the existing .env secrets.

Open http://localhost:3001 and scroll to Scientific Literature Intelligence.

1. Create an academic research project and leave it selected.
2. Choose an authorized PDF, confirm the Groq consent and click
   Analyze document with AI. The backend extracts and verifies its own
   source excerpts and saves the resulting snapshot. User-supplied
   unverifiable structured profiles cannot be written as verified records.
3. Expand Edit researcher review for a study field, add a correction or
   note, then explicitly click Save review revision.
4. Use View saved review history to inspect older versions. Notes are
   never silently autosaved, and revisions do not modify AI evidence.
5. Reload the page and reselect the project to verify records and latest
   reviewer notes return from PostgreSQL.
6. Export the matrix to CSV to maintain a second copy.

Temporary session mode still works without persistence. Analyses made before
this release are not retroactively saved.

The panel displays up to five distinct PDFs among the 25 newest analysis
snapshots. Reanalyzing a PDF creates a new immutable snapshot, each with its
own audit history. Older snapshots remain accessible through the API; a
complete paginated document library is a future development.

## HTTP API

- GET /api/v1/projects — list recent projects.
- POST /api/v1/projects — create an academic or legal project (existing API).
- POST /api/v1/projects/{project_id}/literature/analyze-pdf — multipart
  file and share_excerpts_with_ai=true; returns 201 with saved ID,
  project ID, creation time, and extracted profile.
- GET /api/v1/projects/{project_id}/literature — list saved analyses.
- GET /api/v1/projects/{project_id}/literature/{entry_id} — retrieve one.
- POST /api/v1/projects/{project_id}/literature/{entry_id}/reviews —
  append a review revision.
- GET /api/v1/projects/{project_id}/literature/{entry_id}/reviews —
  retrieve latest 100 revisions in descending order.

Project identifiers are checked in each query, and cross-project entry
access returns 404. Non-academic projects cannot hold literature entries.

## Architecture and limits

The existing Unit of Work now exposes a LiteratureRepository domain port;
SQLAlchemy implements it in the infrastructure layer. Alembic revision 0002
adds literature_entries and literature_review_revisions with foreign keys
and indexes. The domain and application layers remain independent of
FastAPI, SQLAlchemy and Groq.

This is a localhost-only developer milestone, NOT a production-ready
or private multiuser system. There are currently no accounts, authentication,
access control, rate limiting, malware scanning, PDF parser isolation,
encryption-key governance or research retention policies. Do not expose
the service publicly or upload patient records, personal information,
confidential legal files or material without processing rights.
The Groq provider receives selected PDF excerpts after explicit consent.
