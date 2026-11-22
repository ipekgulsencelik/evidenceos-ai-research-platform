# Research Methodology Intelligence — source-limited review

This is a **local-development preview** that helps researchers audit the
methodological reporting of one saved scientific PDF analysis.

## How it works

In **Scientific Literature Intelligence**, choose an existing academic
research project. Open **Research Library → Research Methodology Intelligence**,
select one saved analysis, explicitly authorize external AI processing, and
click **Review study methodology with AI**.

The feature evaluates seven categories:

1. Study design
2. Sampling and participants
3. Instruments
4. Validity and reliability / psychometrics
5. Statistical methods
6. Effect and result reporting
7. Reported limitations

Each category is either:

- **Reported in excerpt**: model believes a detail is present in cited excerpts.
  This is *not* independent fact verification or a study-quality score.
- **Needs review**: the model found an attributed excerpt but identifies a
  methodological question that requires the full paper.
- **Not assessable**: no valid, source-linked model observation was accepted.
  This **does not imply** the full publication lacks the information.

Every non-empty review item references a saved **exact quotation and PDF page**
from the original analysis. Source IDs are checked server-side against
the stored record and allowed facet. Invented, mismatched, duplicate and
unsupported source IDs are discarded, not displayed.

## Privacy and consent

- Independent **explicit checkbox** before every method assessment.
- Sends to Groq at most five saved, preselected excerpts: methods, sample,
  instruments, findings and limitations, with page locators and facet labels.
- Does **not** send full PDFs, raw full-page text, reviewer corrections,
  researcher note histories, project or entry IDs.
- The backend checks project and entry ownership before processing.
- No Groq call is made if the saved record has no grounded quotations.
- Results are computed **on demand** and are not saved as verified claims.

The existing PDF analysis may itself have selected only a few short windows.
This feature **cannot** assess the full methods section, internal/external
validity, study risk of bias, reliability or validity of an instrument merely
from its name, causal inference, or statistical robustness.

## Evidence and methodological limits

The model is prompted **not** to invent Cronbach alpha, omega, test-retest
reliability, statistical tests, p-values, effect sizes, confidence intervals,
sample power, or study design if not explicit in the provided quotation.

Even a matched source ID does **not** guarantee the model's narrative is
factually supported by that quote. Always expand the source quote and verify
in the original paper; for an actual thesis or review, use validated
risk-of-bias tools and appropriate reporting guidelines, not this tool as
a replacement. The system deliberately does not issue quality scores or
statements that a full paper omitted an assessment.

## Architecture

- Domain: methodology aspect, status, sources, observations and report.
- Port: MethodologyAnalyst protocol; AI provider is replaceable.
- Application: project-scoped record lookup, consent gate, facet-specific
  quote matching, fail-closed reference validation and deterministic
  not-assessable fallbacks.
- Infrastructure: Groq JSON response adapter with bounded output.
- Presentation: POST
  `/api/v1/projects/{project_id}/literature/{entry_id}/methodology-review`
  with JSON `{"consent_to_share_quotes": true}`.
- Web: project-bound proxy, runtime response validation, seven evidence
  cards and source quotes.

No database migration is needed; saved literature records are reused.
This module requires no extra environment secrets beyond the existing
`EVIDENCEOS_GROQ_API_KEY`.

## Start locally (after merge)

From the local repository:

    git switch main
    git pull origin main
    docker compose up --build -d
    docker compose ps

Open http://localhost:3001. Select your academic project, then one of the
saved test PDFs (not both). Check the Groq consent box and run the method
review. Some categories may be unassessable; this is expected.

Never use `docker compose down -v` unless intending to delete saved
PostgreSQL data. Do not expose the service publicly; there are no users,
authentication, permission roles, or clinical/research governance controls.
Do not upload identifiable participant records, confidential documents or
sources you lack permission to process.

The two EvidenceOS sample PDFs are **fictional software fixtures** and may
not be cited as scientific research.
