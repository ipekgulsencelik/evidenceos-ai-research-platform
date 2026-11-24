# HTTPS ingress reference (opt-in, loopback-only)

**This is NOT a public production deployment.** This example adds a
certificate-terminating Nginx boundary to the **existing** development
Compose services, without changing their host port bindings. It is a
starting point for a separately reviewed deployment design, not permission
to expose a development stack to the internet.

## Scope and trust model

- `compose.https-ingress-reference.yaml` is **never** selected by
  `docker compose up`; users must explicitly include it.
- Both exposed host ports are pinned to **127.0.0.1** by design.
  Internal Nginx ports are 8080 (redirect) and 8443 (TLS).
- The only upstream is the private Compose `web:3000`, **not** the FastAPI,
  PostgreSQL, Redis or Keycloak service. The browser still reaches the API
  through the Next.js BFF.
- Unknown HTTP Host values are dropped; unknown TLS hosts return 421.
  Valid HTTP requests redirect to a fixed configured HTTPS hostname,
  never a client-supplied `Host` or `X-Forwarded-Host`.
- The proxy replaces forwarded host, protocol, port and client-IP headers.
  Do not add other untrusted proxies in front without reviewing the
  actual client-IP trust chain.
- TLS 1.2/1.3 only, 10 MiB request body limit, connection and timeout
  limits, per-IP baseline request quotas, and a smaller quota for
  `/auth/login`. These protect against basic mistakes, not distributed
  flooding; real IdP login rate limiting/MFA and upstream WAF remain
  deployment responsibilities.
- HSTS is applied at the TLS edge and duplicates from the web response
  are suppressed. **Do not** duplicate or replace the application's
  nonce-based CSP: that header is forwarded untouched.
- This is a single-replica, in-memory Nginx request-limit example. Do
  not mistake it for a distributed account/organization quota or an
  availability/DoS guarantee.
- `nginx:stable-alpine` is suitable for the reference test only. A real
  release must pin an audited, supported image **digest** and arrange
  scanning, timely updates and an owned patch process.

## Certificate and origin requirements

The example requires two **operator-provided, untracked files**:

```text
deploy/ingress/certs/fullchain.pem
deploy/ingress/certs/privkey.pem
```

The directory is Git-ignored. Never commit TLS private keys or paste them
into GitHub issues or logs. The certificate must match the exact
`EVIDENCEOS_INGRESS_HOST` hostname and be issued by a trusted authority
for any browser or production use. DNS, external certificate issuance and
rotation are **not** automated by this repository.

The existing isolated OIDC stack uses
`EVIDENCEOS_WEB_ORIGIN=http://127.0.0.1:3101` and deliberately
permits HTTP development cookies. **Do not place this HTTPS reference
in front of that OIDC stack without redesigning its origin and IdP
registration.** In an actual TLS deployment:

1. Set `EVIDENCEOS_APP_ENV=production` on the appropriate application
   containers, after satisfying all production-only API configuration
   checks (including shared `rediss://` rate limits).
2. Set `EVIDENCEOS_WEB_ORIGIN=https://<exact-hostname>`.
3. Configure the identity provider's exact HTTPS callback and
   post-logout URLs; validate secure, HttpOnly session cookies and CSRF.
4. Keep backend, PostgreSQL, Redis and identity-provider administration
   private; restrict egress, service identities and secret access.
5. Verify the actual TLS chain, revocation and certificate rotation.
   Do not use `curl -k` as a release acceptance test.

**Do not copy the development Compose directly into public production.**
It still exposes localhost API/web ports and does not supply a managed
production database, external secret manager, load balancer/WAF, backups
or incident operations.

## Syntax/preflight only (safe, no public listener)

With `compose.yaml` and `.env` present, use a **non-production**
placeholder name to check the combined configuration:

```powershell
$env:EVIDENCEOS_INGRESS_HOST = "research.example.invalid"
docker compose -f compose.yaml -f compose.https-ingress-reference.yaml config --quiet
Remove-Item Env:EVIDENCEOS_INGRESS_HOST
```

This validates Compose interpolation only. To check actual Nginx
parsing without publishing a service, CI runs a disposable container,
a one-day throwaway certificate and `nginx -t` with network disabled:

```bash
python -m unittest discover -s scripts -p 'test_https_ingress_reference.py' -v
```

On Windows, the Docker syntax portion is skipped by the test script;
it executes on GitHub's Ubuntu CI runner. A correct `nginx -t` result
does **not** prove trusted TLS, real-browser OIDC login, or transport
security in a deployed environment.

## Deployment-specific go/no-go still required

Before exposing the service, record the selected hosting environment,
public hostname, certificate issuer/renewal, DNS and reverse-proxy
ownership, network isolation, proxy trust chain, DDoS/WAF policies,
MFA/offboarding, persistent services, secure secrets, disaster recovery,
monitoring, rollback strategy and independently reviewed security tests.
Then run actual HTTPS browser E2E against a **separate, disposable**
deployment. See [production readiness](production-readiness.md).

**The reference remains loopback-only and disabled by default.**
