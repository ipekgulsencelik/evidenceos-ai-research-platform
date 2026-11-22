# Research Quality & Bias Intelligence — human reporting triage

## Purpose and scientific boundaries

This **local-only development milestone** adds a generic, seven-item study
reporting checklist with retained, page-located PDF quotations and an
**independent, append-only human judgment history**.

It does NOT automatically assign study quality, risk-of-bias classifications,
causal inferences, publication validity or certainty of evidence. A matched
quote merely indicates an excerpt is available, not that an item is adequately
reported. An absent excerpt does NOT mean an item is missing from the full paper.

This general checklist is NOT STROBE, ROBINS-I, RoB 2, JBI or another validated
study-design-specific instrument and MUST NOT be cited as a formal risk-of-bias
appraisal. Reviewers should select and complete the appropriate external
instrument for an actual systematic review or thesis.

## Checklist and what is saved

Seven generic prompts cover study design, participant sampling, measurement,
validity/reliability evidence, statistical method and assumptions, effects and
uncertainty, and limitations. For each:

- Available matching quotations and PDF page locators are displayed from the
  existing, unchanged saved literature profile.
- The initial reporting assessment and concern assessment are both **Not
  assessed** regardless of quotation availability.
- A researcher may make a manual **full-text reporting judgment**:
  reported, unclear, not reported, not applicable or not assessed.
- Separately, they may indicate **Potential concern**,
  **No concern identified in this review** or **Not assessed**. These are
  *unvalidated researcher annotations*, NOT official risk-of-bias categories.
- Before selecting a non-default judgment, the researcher must check
  **I checked the original full PDF for this judgment**. This is self-attested
  and not independently verified.
- A researcher may save an exploratory note while leaving both judgments
  Not assessed and original-PDF box unchecked.
- Saving always creates a new timestamped, immutable revision, instead of
  replacing a prior judgment. History shows up to 100 newest revisions.
- After page refresh, choosing the same project and saved analysis restores
  the latest judgments and notes from PostgreSQL.

No AI provider is called for this checklist. It reuses stored excerpts.
The original evidence profile and previous AI methodology output are not
changed by a researcher judgment. No automatic confidence percentage,
publication appraisal score or "study passes/fails" status exists.

## Architecture

- Domain: immutable quality indicators and reviewer revision entities.
- Application: deterministic source coverage plus strict project-scoped
  reviewer workflow and full-text confirmation requirement.
- Port: `QualityReviewRepository` appended to existing Unit of Work.
- Infrastructure: SQLAlchemy adapter plus additive Alembic **0004** revision
  `quality_review_revisions` with foreign keys and database check constraints.
- Presentation:
  - `GET /api/v1/projects/{project_id}/literature/{entry_id}/quality-checklist`
  - `POST /api/v1/projects/{project_id}/literature/{entry_id}/quality-reviews`
  - `GET /api/v1/projects/{project_id}/literature/{entry_id}/quality-reviews`
- Web: strict Next.js request/response boundaries and human review forms
  within Research Library.

All reads and writes verify the saved entry belongs to the specified academic
project. This is **not authentication**; no user-level roles, reviewer identity,
tamper-proof event signing, third-party audit service or access policy exists.

## Local update

From the same repository directory as compose.yaml:

    git switch main
    git pull origin main
    docker compose up --build -d
    docker compose ps

The migrate service runs Alembic 0004 against the existing PostgreSQL volume.
Keep the current `.env`. **Never run `docker compose down -v`** unless you
intend to destroy saved data.

Open http://localhost:3001, select the existing research project and then
Research Library → Research Quality & Bias Intelligence. Choose one stored
analysis and inspect its seven prompt cards. An actual full-text researcher
judgment requires a check against an authorized original PDF. You can test
notes and Not assessed status without checking the fictional PDF. Check
View saved review history, refresh the browser and select the same project
and analysis to verify PostgreSQL persistence.

The two synthetic EvidenceOS PDF fixtures are **fictional**. Their fabricated
participants, results and methods may not be used as academic evidence.

## Security limitations

Localhost-only trusted development. There are no accounts, passwords,
authorization policies, reviewer attribution, sensitive-document governance
or hardened deployment. Source snippets, titles, researcher notes and manual
judgments are saved in PostgreSQL; the original PDF binary is not persisted.
Avoid identifiable, confidential, proprietary, patient or unauthorized text.
