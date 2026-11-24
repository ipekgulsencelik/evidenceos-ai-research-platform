# Browser response security headers — nonce CSP and HSTS

EvidenceOS's Next.js `proxy.ts` now attaches security headers to **all**
application responses, including OIDC redirects and authentication errors.

## Enforced policy

- Every request gets a new cryptographically random CSP nonce. Proxy forwards
  `Content-Security-Policy` and `x-nonce` in internal request headers, so
  Next.js can nonce its inline App Router bootstrap scripts. Untrusted
  inbound values are overwritten.
- `script-src 'self' 'nonce-...' 'strict-dynamic'` prohibits untrusted
  inline scripts and executable injection. Local Next.js development alone
  enables `'unsafe-eval'` for development tooling.
- `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `object-src 'none'`,
  `base-uri 'none'`, and `form-action 'self'` restrict embedding, object
  execution, base URLs, and form destinations.
- `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`
  and restricted `Permissions-Policy` apply in every environment.
- `Strict-Transport-Security: max-age=31536000` is sent **only** when
  `EVIDENCEOS_APP_ENV=production`. Do not use production mode on the
  isolated HTTP staging origin. TLS termination and HTTP-to-HTTPS redirect
  remain the responsibility of the trusted fronting ingress/proxy.
  Deliberately omit `includeSubDomains` and `preload`.

## Compatibility and limits

- **Style CSP is transitional**: components currently use inline React style
  properties, so `style-src 'unsafe-inline'` remains necessary. Do not
  confuse this with permitting `'unsafe-inline'` scripts. Refactor inline
  styles into classes before considering a stricter style policy.
- API calls, Keycloak logout and the fixed server-side OIDC redirect URL
  are unchanged. The public login and signed-out landing routes also
  receive nonces; no credentials or tokens are placed in CSP.
- Static assets are excluded from proxy by the existing Next.js matcher.
  The HTML/document response is protected. A fronting reverse proxy/CDN
  should also set any desired asset response headers.
- Nonce CSP requires **dynamic HTML rendering**. Review Next.js dynamic
  route behavior before enabling full-page CDN caching or static export.
  Do not cache document responses across requests with different nonces.
- Next.js framework/client hydration should be validated using the genuine
  disposable Keycloak browser E2E after deployment. CI unit tests and
  build checks alone do not establish that the rendered UI works under CSP.
- This is one defense-in-depth layer, not a production security audit,
  replacement for input validation, or an API request rate limiter.

## Verification

From `apps/web`:

```powershell
npm ci
npm run check
npm run build
```

To verify the actual browser, follow
[`isolated-local-oidc-staging.md`](isolated-local-oidc-staging.md)
and rebuild the disposable staging web container, then run:

```powershell
python scripts/run_local_oidc_e2e.py
```

Inspect the app's `Content-Security-Policy` header and browser console
for violations; test sign-in, sign-out, and in-app navigation. Do **not**
publish the service solely based on passing these tests.
