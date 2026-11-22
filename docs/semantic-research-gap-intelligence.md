# Semantic Research Gap Intelligence — first, consent-gated milestone

## Purpose

Compare **population/sample**, **study design/method**, **measurement scales**
and **reported findings** across two to ten different saved scientific PDFs
within one academic research project.

The first-release feature uses the already saved *verbatim, PDF-page-linked
quotations* from Scientific Literature Intelligence. It requests preliminary
AI classifications and research questions, rather than making scientific
claims on its own.

### Two different comparison modes

1. **Research Gap Detection — evidence coverage:** existing, deterministic,
   local comparison of whether fields have matched quotations. No Groq call.
2. **Semantic Research Gap Intelligence:** optional external Groq request to
   propose tentative similarities, differences and things to verify manually,
   based ONLY on available source quotations.

## Consent and data transmitted

After selecting **two to ten distinct PDF analyses** and checking the NEW,
separate Groq consent box, press **Compare scientific content with AI**.

Only the selected project’s *document titles*, *page locators*, *dimension
labels* and *verbatim selected quotations* are sent to Groq. The PDF binary,
complete PDF text, local reviewer notes and project/record UUIDs are **not
sent** by this feature. At most one quote per dimension per selected document
is sent: 4 dimensions × 10 documents = 40 quotations.

No outbound call occurs without consent, without an adequately matched pair
of source excerpts, or if the records are not in the same academic project.
The UI resets the explicit consent when changing the selection or project.

The model response can contain at most one candidate per dimension. Every
source identifier is resolved **on the server** against known excerpts;
invented references, incorrectly matched facets or references originating
from only one document are discarded. Original quotations and their PDF
page references come exclusively from saved records, not the model.

The output records a model ID, skipped candidate count, insufficient
dimensions, tentative conclusion class, research question, and expandable
source quotations. The response is **not persisted**, and contains no
machine-validated scientific conclusions. Researchers must check each quote
in the original full publication before using the comparison.

## Interpretation limits

- "Possible difference" is not a validated statistical difference.
- "Possible alignment" does not establish equivalence.
- "Insufficient context" means the saved excerpts do not justify a comparison.
- **No comparison proves a novel or generalizable research gap**; broader,
  systematic searches and quality appraisal are necessary.
- Two publications discussing different populations, interventions, scales
  or outcome variables may not be meaningfully comparable.
- Quotes in the database were verified against *selected PDF excerpts*;
  their surrounding context and the underlying scientific claims must still
  be read by a qualified researcher.
- Hallucinations in a model's proposed **summary** or research question
  remain possible even if the returned source ID is valid.

## Run

Keep your existing Groq key in `.env` and the current PostgreSQL volume:

    git switch main
    git pull origin main
    docker compose up --build -d
    docker compose ps

Open http://localhost:3001, select your academic project, choose two
**different** saved PDF analyses inside Research Library, then use the new
Semantic Research Gap Intelligence section under the existing coverage
comparison. Check the separate consent box before sending quotes.

For repeatable tests, use the two *fictional* EvidenceOS PDFs you already
uploaded. Their contents are software fixtures, not academic source
material. Live model results may legitimately contain no candidates.

## Architecture / API

- Domain: immutable SemanticExcerpt, ProposedSemanticComparison,
  SemanticComparison and SemanticGapReport.
- Application: consent enforcement, project-scoped selection and source
  grounding. Extends the same project-selection invariants reused by the
  deterministic comparator.
- Infrastructure: asynchronous Groq model adapter with bounded JSON,
  temperature zero, strict enum parsing and no user-driven URL injection.
- Presentation: `POST /api/v1/projects/{project_id}/semantic-gaps`,
  accepting `entry_ids` and `consent_to_share_quotes: true`.
- Web: same-origin proxy, strict response validator, optional consent, and
  source-quote reference cards.

No migration is needed because comparisons are computed on demand. The
existing platform remains **localhost-only** and has no accounts, RBAC,
tenant separation, safe handling of sensitive materials, or production data
governance. Do not publish it or upload confidential, patient-identifiable,
unpublished or otherwise unauthorized materials.

Automated tests cover consent gating, no-model-call paths, forged source ID
rejection, dimension/source mismatch, cross-project isolation, repeated
PDF copies, mocked Groq transport and the API boundary. They do NOT replace
a live, human-reviewed Groq evaluation.
