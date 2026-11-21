# EvidenceOS Academic Research Web

A responsive Next.js / TypeScript / Tailwind CSS workspace backed by the existing FastAPI academic APIs.

## Features

- Live OpenAlex academic search (`query`, `limit`), author/year/DOI/source details.
- Crossref DOI metadata verification with optional expected title.
- Result-level **Verify DOI** shortcut that prefills the verification form.
- Explicit loading, empty, offline, provider failure, and validation states.
- No fake results, no credentials sent to the browser, and no scientific claim verification assertions.
- Browser calls use same-origin Next.js API route handlers that forward requests to the existing FastAPI service. `BACKEND_API_URL` is server-side only.
- Responsive and accessible labels, status updates, and keyboard navigation.

## Docker (recommended)

From repository root with `.env` in place:

```powershell
docker compose up --build -d
```

Web: http://localhost:3001  
FastAPI Swagger: http://localhost:8001/docs

Set `EVIDENCEOS_WEB_HOST_PORT` in root `.env` to override 3001 if it is occupied. `BACKEND_API_URL=http://api:8000` is set internally in `compose.yaml`.

## Local Node.js development

Requires Node.js >= 20.9.0, a running backend, and npm access:

```powershell
cd apps/web
npm ci
$env:BACKEND_API_URL="http://127.0.0.1:8001"
npm run dev
```

Then open http://localhost:3000. Run `npm run check` and `npm run build` for quality checks.

## Security and limitations

Local development only: no identity, authorization, tenancy, or rate limiting. Do **not** expose this app directly on the public internet. The Next.js proxy validates parameters, forwards only fixed route paths, and never receives OpenAlex credentials. The backend reads the OpenAlex API key from root `.env`; secrets should never be committed to GitHub. This app only checks bibliographic records, **not** whether an article's conclusions support a scientific claim.

The npm lockfile is committed; CI and Docker use `npm ci` for reproducible installs.
