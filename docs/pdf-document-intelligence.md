# PDF Document Intelligence — Phase 2.1

This increment adds local extraction of selectable PDF text and deterministic
retrieval of page-grounded candidate passages to populate the existing EvidenceOS
AI Evidence Review form. It is a human-in-the-loop tool, not a full research-paper
understanding system.

## Workflow

1. In Evidence Review, write a claim (10–500 characters).
2. Select a PDF you are authorized to process (max 8 MiB, 30 pages).
3. Click Find passages. The browser sends the PDF to the local Next.js server,
   which forwards it to the local FastAPI backend.
4. The backend parses the PDF with pypdf, extracting selectable text with page
   numbers. Uploaded PDFs and extracted passages are not persisted by EvidenceOS.
5. A deterministic lexical ranking algorithm compares claim terms with exact
   overlapping text windows. Up to three unchanged candidates are returned,
   each identified by an original page number.
6. Review candidate excerpts against the original document and choose
   Use selected excerpts in assessment.
7. Only Assess claim sends the claim and selected excerpts to Groq. This gives
   preliminary LLM judgments, which always require human review.

An empty result means keyword overlap did not find a match; it does not prove
the document lacks evidence. The lexical score is not AI confidence or claim support.

## Limitations

- Scanned/image-only PDFs are unsupported (no OCR in this increment).
- Password-protected, damaged, oversized and textless PDFs return clear errors.
- PDF extraction may lose formatting, ligatures and column order. Page locators
  refer to 1-indexed PDF pages, not printed journal page labels.
- Filename and page numbers are not DOI or bibliographic verification.
- No file is transmitted to Groq on upload, but selected excerpts are sent
  externally if the user chooses Assess claim.
- This local-only development version has no authentication, rate limiting,
  malware scanning, parser sandbox, multi-user isolation or production-ready
  retention and privacy controls. Never expose its upload endpoint publicly.
- Do not upload patient records, confidential legal documents, sensitive
  identifiable material or text for which you lack processing rights.

## Local run

In the project root PowerShell:

    git switch main
    git pull origin main
    docker compose up --build -d
    docker compose ps

Open http://localhost:3001 and use PDF import in AI-assisted claim assessment.

## API

    POST /api/v1/documents/retrieve-passages
    multipart/form-data: file (PDF), claim (text 10-500 chars)

    200: title, sha256, page_count, text_page_count,
         passages [{source_id, title, locator, passage, matched_terms, lexical_score}], caveat
    413: size/complexity limits exceeded
    422: invalid, encrypted, scanned/textless PDF or invalid claim

No original document text or uploaded binary is stored as part of retrieval.

## Architecture

- domain/entities/document.py: immutable typed document and result objects
- domain/ports/document.py: extraction protocol
- infrastructure/providers/pypdf_document.py: local bounded PDF adapter
- application/use_cases/document.py: deterministic retrieval engine
- presentation/api/routes/document.py: HTTP upload, async offload
- Next.js same-origin route: bounded upload forwarding
- Next.js component: human review and explicit selection

Before a production release, isolate the parser under CPU/memory/time limits,
add malware scanning, identity/RBAC, rate limits, privacy controls, retention,
audit trails and robust evaluation across realistic PDF layouts.
