# EvidenceOS Research Library + Evidence Coverage Candidates

This iteration extends the existing **local academic workspace**. It is a
research organization and source-coverage audit tool, **not** an autonomous
discoverer of original scientific research gaps.

## Research Library

Choose an existing academic project in Scientific Literature Intelligence.
Research Library displays up to the newest 100 saved analysis snapshots,
including snapshots of the same PDF made on different occasions. You can:

- Search the document title, filter by reading status and exact tag.
- Set an independent *To read*, *Reading*, or *Reviewed* status for each snapshot.
- Add up to eight tags of 1–32 letters, numbers, spaces, underscores, or hyphens.
- Explicitly click **Save metadata** to persist your changes.
- Select distinct saved studies for an evidence-coverage comparison.

The backend exposes GET /api/v1/projects/{project_id}/library with
query/status/tag/limit filters and PUT
/api/v1/projects/{project_id}/library/{entry_id}. Metadata is stored in the
new literature_library_metadata table, created by additive Alembic revision
0003. Existing AI findings, source quotes and reviewer history remain
unchanged.

The first-release library is explicitly bounded to the **newest 100 snapshots**
per project; search only considers that bounded set. A paginated server-side
full-text corpus and attachments/folders are not part of this release.

## Research Gap Detection — what it actually does

Select **two to ten different saved PDFs**. Click **Compare selected analyses**.

EvidenceOS deterministically compares the **six fields** already extracted
from those PDF analyses (aim, method, sample, instruments, findings,
limitations). Each field missing a matching source quote in one or more
selected studies generates an **extraction coverage candidate**, with:

- number of studies with a quoted, extracted field;
- studies where the field was *not identified*;
- studies where the source quote was *rejected*;
- title, original PDF page locator, exact quote and original AI
  interpretation of the studies where source quotes did match;
- clear instructions for manual full-paper verification.

No new model call is made by the comparison. Values are not invented and
the output does not compare study statistical significance, infer causality,
declare scientific novelty, or conclude that a field is absent in an entire
paper or broader literature. A missing field can mean keyword snippet
selection, PDF extraction, or model extraction failed.

**This is NOT proof of a genuine research gap.** Genuine gap identification
requires a reproducible literature search, domain knowledge, study quality
appraisal, inclusion/exclusion criteria, and manual source review.

## Privacy and deployment

- PDF binaries remain unpersisted. The saved literature profiles, selected
  quotes, tags, reading state and reviewer notes are kept in PostgreSQL.
- Gap comparisons read saved analyses and do **not** send text to Groq.
  The existing PDF analyze flow still sends selected excerpts to Groq
  **only with explicit consent**.
- The app has no authentication, per-user ownership, RBAC, malware
  scanning, rate limits or production data governance. It must remain
  bound to localhost for trusted development and must not contain
  identifiable clinical records or unauthorized confidential content.
- Project scope is checked for metadata updates and comparisons. IDs
  of analyses from other projects are rejected.
- No background research or automatic monitoring is performed.

## Run locally after merge

Keep your existing .env secrets and PostgreSQL Docker volume.

    git switch main
    git pull origin main
    docker compose up --build -d
    docker compose ps

Never use docker compose down -v unless you intend to delete saved project data.
The migrate service applies Alembic revision 0003 before the API starts.
Open http://localhost:3001 and choose the research project.

To test the comparison, upload a *second distinct* permitted text-based PDF
into the same project. A single PDF or two snapshots of the same PDF
cannot establish a meaningful comparison. The existing fictional sample
paper is for software tests only, not thesis evidence.

## Clean Architecture and tests

- Domain: ReadingStatus, LibraryMetadata, CoverageCandidate and source references.
- Ports: LibraryRepository, UnitOfWork composition.
- Application: metadata validation/project isolation and deterministic
  source-coverage comparison.
- Infrastructure: SQLAlchemy metadata adapter, Alembic 0003.
- API: Pydantic contracts, scoped FastAPI routes, bounded selection.
- Web: typed Next.js proxy and interactive search/filter/tag/compare panel.

Tests exercise tag validation, cross-project isolation, missing/rejected
fields, source quote provenance, SQLite roundtrip, live PostgreSQL
migration roundtrip, TypeScript response guards and comparison UI build.
