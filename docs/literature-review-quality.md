# EvidenceOS — Scientific Literature Review Quality & Matrix UX

This update improves the AI-assisted scientific literature review module without
changing its core safety boundary: generated interpretations must never be presented
as scientifically verified facts.

## Verbatim source checks

The application compares model-proposed quotations to original snippets extracted
from the uploaded PDF. It rejects:
- duplicated model fields;
- missing quoted evidence or interpretation;
- excessive or empty quotations / interpretations;
- quotations absent from all selected snippets;
- quotations present on more than one page if the model supplied no correct source ID.

If a quoted string appears verbatim on **exactly one PDF page** among selected
snippets, the application may repair an incorrect model snippet ID. This emits
locator_repaired=true; the displayed locator is from PDF parsing, not guessed by
the model. Multiple windows on the same page count as one page. A quote missing
from selected snippets is never accepted by semantic similarity alone.

The model prompt has stricter instructions to supply complete, verbatim source
sentences, especially for limitations. The system does not guarantee all six
research fields can be recovered, nor does matching a quote validate the model's
interpretation. Missing fields remain missing.

## Reading the improved matrix

The previous six narrow research-content columns have been replaced by one
row per PDF and research field. The view supports:
- keyword search across study titles, AI values, quotes and researcher notes;
- filtering by research field and extraction status;
- exact source quote expansion and page references;
- a specific reason for each rejected field;
- separate human corrections, review notes and a reviewer checkbox.

Edits **never overwrite** the original AI statement, exact quotation, status,
or page locator. Human notes are labeled unverified; checking the review box
records an action, not independent scientific validation. Removing a PDF removes
its local annotations.

CSV export always includes all documents, regardless of current filters. AI
fields, verification status, rejection reason, locator repair, researcher
correction/notes and manual check status have separate columns. Untrusted cells
are escaped to prevent spreadsheet formula execution.

## Important limitations

Profiles and human notes exist in the browser session only; they are not
persisted in PostgreSQL. Save the CSV before reloading if needed.
The app is for local development; it does not yet have login, multi-user
isolation, secure document processing or formal audit trails.

Uploaded PDFs are processed locally with pypdf; selected source snippets go
to Groq only when explicitly consented. No PDF binary is sent to Groq.
This is a literature extraction aid, not a validated systematic-review engine.
Verify scale names, sample sizes, findings, and limitation statements in the
actual publication before incorporating them into a thesis.

## Use

From the repository root:

    git switch main
    git pull origin main
    docker compose up --build -d
    docker compose ps

Open http://localhost:3001, select a searchable PDF in Scientific Literature
Intelligence, provide explicit consent, and analyze. Use the new status/facet
filters, then open Edit researcher review for corrections and notes. Export CSV.

## Verification

Backend tests cover quote/source mismatch, unknown or misassigned source IDs,
ambiguous page matches, duplicate fields and incomplete evidence. Frontend
tests cover filter behavior and CSV annotation separation/formula escaping.
GitHub CI checks Ruff, mypy, pytest, TypeScript, web tests and Docker.
