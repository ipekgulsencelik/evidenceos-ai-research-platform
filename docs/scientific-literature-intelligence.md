# Scientific Literature Intelligence — EvidenceOS

This release adds preliminary six-field scientific paper extraction using
locally parsed PDF text, with a human-reviewable side-by-side comparison matrix.

## Six structured fields

Research aim; study design/method; sample/participants; scales/measures;
main findings; study limitations.

A field is "grounded" only if the model's quote is found verbatim in a
source snippet extracted from the PDF. Page numbers are server-assigned.
Invalid quotations are discarded as rejected_quote. Missing details become
not_identified ("not identified in selected excerpts"), NOT proof of absence
from the full publication. Human verification is mandatory.

## Workflow

1. Choose a selectable-text PDF, max 8 MiB and 30 pages.
2. Explicitly consent to sending bounded source extracts to Groq.
3. Click Analyze document with AI.
4. The existing local pypdf adapter extracts the PDF text.
5. Deterministic English/Turkish keyword selection retrieves at most 12
   source-text windows (~1150 characters each), across all six categories.
6. Groq proposes a short value and literal quotation or null for each field.
7. The backend verifies the quote is a contiguous substring from the
   specific source snippet and attaches the original PDF page locator.
8. Compare up to five PDFs in the browser session, expand exact quotations,
   and export a spreadsheet-formula-safe CSV literature matrix.

The keyword selection is NOT exhaustive full-text extraction; a field missed
by selection is not necessarily absent from the PDF. Quotes matching text do
not ensure that the interpretation is factually or methodologically correct.

## Privacy and boundaries

- Uploaded PDF binaries and extracted profiles are not durably stored by
  EvidenceOS; temporary multipart buffering and browser memory still occur.
- Up to 12 selected text windows, NOT the full PDF, are transmitted to Groq
  only after the user's explicit consent for that upload.
- Never submit patient data, identifying records, unpublished sensitive data,
  confidential legal documents, or content without rights to process it.
- The provider's data-handling terms may apply to submitted excerpts.
- The app does not yet have authenticated accounts, rate limits, malware
  scanning, parser isolation or production privacy governance. Keep localhost.
- Scanned/image PDFs, complex figures, tables and PDF columns may be unreadable
  or mis-ordered. OCR is not implemented. Check originals.

## API

POST /api/v1/literature/analyze-pdf
multipart fields: file (PDF), share_excerpts_with_ai (required true)

200 -> document_title, sha256, page_count, text_page_count, model,
       findings [{facet,status,value,quote,locator}], caveat
413 -> PDF size/extraction limit
422 -> bad PDF, missing consent or invalid input
503 -> missing Groq API key
502 -> Groq provider error / invalid model response

## Local use

Keep your existing repo-root .env with private keys.

    git switch main
    git pull origin main
    docker compose up --build -d
    docker compose ps

Open http://localhost:3001 and scroll to Scientific Literature Intelligence,
below the bibliographic comparison matrix.

## Clean Architecture

- Domain entity: immutable literature facets, status and quote references
- Domain protocol: literature analyst interface
- Application use case: snippet selection and exact-quote verification
- Infrastructure: Groq model adapter with bounded JSON contract
- Presentation: multipart FastAPI route and typed response
- Next.js: consent form, same-origin proxy, multi-document matrix and safe CSV

Future: systematic expert evaluation datasets, full-document provenance,
human corrections, review audit, DOI matching, auth and deployment hardening.
