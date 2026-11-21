# EvidenceOS — Literature Matrix & AI Evidence Review

This is an early human-in-the-loop research support feature, **not** a scientific
truth checker or legal opinion generator.

## What it does

- An OpenAlex search produces a comparison table of bibliographic metadata:
  title, author list, year, DOI and source. Export CSV with formula-safe escaping.
  This table does NOT extract study results or methods.
- A researcher can supply a claim and 1–3 passages copied from documents they
  are authorized to access, with optional page/section locators.
- An opt-in external Groq model evaluates the passages separately, returning
  preliminary supports, contradicts, or insufficient judgments.
- Every non-insufficient judgment needs a literal quote from the text the user
  supplied. If a quote is missing or not verbatim, the backend downgrades the
  judgment to insufficient. This prevents fabricated **quotes**, but cannot
  guarantee that an exact quote truly supports a scientific claim.
- Human review is always required.

## Local setup (Windows / Docker)

Add to your existing repository-root .env file:

    EVIDENCEOS_GROQ_API_KEY=your-private-key
    EVIDENCEOS_GROQ_MODEL=openai/gpt-oss-20b

Never share the key or commit .env. Then run in the project root:

    git switch main
    git pull origin main
    docker compose up --build -d

Web: http://localhost:3001
Swagger: http://localhost:8001/docs

New endpoint: POST /api/v1/evidence/assess

Example body (illustrative, NOT a real study result):

    {
      "claim": "The example study reported a relationship between sleep and wellbeing.",
      "sources": [{
        "source_id": "example-1",
        "title": "Illustrative source — replace with a real paper",
        "locator": "Results",
        "passage": "In this invented example, researchers observed an association between sleep and wellbeing."
      }]
    }

HTTP errors: 503 (AI key missing), 502 (provider failed), 422 (invalid
claim/source input). No synthetic response fallback.

## Privacy and copyright

- **The claim and text are sent to Groq on submission.** Do not paste
  confidential legal files, identifiable health information, unpublished
  sensitive research, or text you do not have permission to use.
- EvidenceOS does not scrape paywalled papers or claim to have checked the
  original study full text. OpenAlex metadata is not a substitute for the article.
- The local app has no authentication, role separation, rate limiting or
  tenant isolation. Do not expose it publicly.
- Passage content is considered untrusted data; LLM prompt-injection defenses
  are imperfect.
- This feature does not persist supplied excerpts in EvidenceOS.

## Architecture

- domain entities and provider-neutral EvidenceJudge port
- application use case with exact quotation validation
- infrastructure Groq API adapter using an injected HTTP client
- FastAPI endpoint with typed request and response contracts
- Next.js same-origin route and interactive academic research workspace
- offline model-mocked tests and CI quality gates

Future work: rights-aware full-text ingestion, page-grounded extraction, study
methods matrix, specialist reviews and a validated evaluation dataset.
