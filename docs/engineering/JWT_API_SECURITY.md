# JWT and API trust boundaries

The independent React frontend authenticates to Django REST Framework using
short-lived JWT bearer access tokens and a rotating refresh token. The Django
Admin and original Django-template pages **retain session authentication**.
The guest Candidate Agent also retains its existing browser session, Turnstile
and server-side quota; no JWT is issued to anonymous visitors.

## API endpoints

| Method | Endpoint | Credential |
| --- | --- | --- |
| GET | `/api/v1/auth/csrf/` | Public; establishes a CSRF cookie |
| POST | `/api/v1/auth/token/` | Credentials + CSRF |
| POST | `/api/v1/auth/refresh/` | Refresh cookie + CSRF |
| POST | `/api/v1/auth/logout/` | Refresh cookie + CSRF |
| GET/PATCH | `/api/v1/me/profile/` | Authenticated owner |
| POST | `/api/v1/me/facts/{id}/review/` | JWT owner only |
| GET/POST | `/api/v1/candidates/{slug}/chat/` | JWT authenticated user only |

Other read-only API endpoints and /api/schema/ remain in place. Swagger UI is
available at /api/docs/. The production agent still uses full-context
retrieval with the same cost controls.

## Browser flow

1. The frontend requests `GET /api/v1/auth/csrf/` with
   `credentials: "include"`, and retains the returned `csrf_token` in memory.
2. POST login credentials, send `X-CSRFToken` and
   `credentials: "include"`. Only an access token appears in the JSON
   response. The refresh JWT is a host-only `HttpOnly` cookie restricted to
   `/api/v1/auth/`, with `Secure` in production and `SameSite=Lax` by default.
3. Hold the access token **in JavaScript memory only**. Send it in the
   `Authorization: Bearer ...` header to protected API endpoints.
4. For refresh and logout, send the CSRF header and cookie; the response
   rotates the refresh token, blacklists the consumed token and returns a
   new short-lived bearer access token. Do not persist JWTs in localStorage,
   sessionStorage or browser-accessible cookies.
5. Logout blacklists the presented refresh token and deletes the cookie.
   An access token that was already issued can remain valid for up to five
   minutes; this design does **not** promise immediate access-token revocation.

All CSRF-using auth endpoints explicitly apply Django CSRF protection even
though DRF APIViews normally exempt dispatch from Django's CSRF middleware.
Rotation is guarded by a PostgreSQL row lock on the outstanding token to
prevent concurrent requests from accepting the same token after blacklist.

## CORS, domains and deployment

For independent deployments, prefer same-site HTTPS subdomains:
`app.example.com` and `api.example.com`. This permits `SameSite=Lax`
without giving the frontend JavaScript access to the host-only API refresh
cookie.

Configure both sets of origins in the **backend**:

```dotenv
API_CORS_ALLOWED_ORIGINS=https://app.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://app.example.com,https://api.example.com
JWT_REFRESH_COOKIE_SAMESITE=Lax
```

CORS is restricted to `/api/` and the legacy `/chat/` path (used for
Turnstile-protected guest chat). Production rejects wildcard or HTTP origins,
and requires every permitted CORS origin to be CSRF trusted. Never enable
`CORS_ALLOW_ALL_ORIGINS`. CSRF and CORS protect different boundaries;
correct CORS headers are not an authorization decision.

When the frontend is on a **different site**, `JWT_REFRESH_COOKIE_SAMESITE=None`
is an explicit production-only option and also sets the CSRF cookie to
SameSite=None. Secure HTTPS, exact CORS origins, explicit CSRF trust,
credentialed requests and privacy-aware browser behavior must all be
verified. Browser third-party-cookie blocking may prevent this arrangement,
so same-site subdomains are preferred.

Set `JWT_SIGNING_KEY` to a dedicated long secret in production if you need
independent signing-key rotation; otherwise JWT signing uses Django
`SECRET_KEY`. Do not commit signing keys or token values.

## Security and limitations

- Authentication failures never reveal whether a username exists. Login is
  throttled at five requests/minute, refresh at twenty requests/minute, and
  CSRF bootstrap at sixty requests/minute. DRF's default cache throttle is
  **not** sufficient distributed brute-force protection across multiple
  workers or servers. Add shared-cache admission or an edge rate limit before
  scaling horizontally.
- Refresh tokens are stored and revoked via SimpleJWT's database blacklist.
  Its OutstandingToken records need periodic cleanup:
  `uv run python manage.py flushexpiredtokens` using a real scheduler.
- Owner profile PATCH accepts only a strictly limited field allowlist.
  Review decisions are version-checked, row-locked and audited; they cannot
  edit another owner's facts or bypass verified-before-public state rules.
- JWT chat is restricted to active, published candidates and authenticated
  users, and uses the existing application service for approval checks,
  quota, idempotency, budget reservation, provider errors, citations and
  conversation history. Guest chat remains on the original browser-session
  endpoint until the independent frontend ports its Turnstile UI.
- The token response is marked `Cache-Control: no-store`; neither refresh
  tokens nor private records are included in the OpenAPI examples.
- XSS against the frontend can steal a live access token from memory.
  Maintain CSP, escape untrusted content and do not render raw HTML answers.
  A short access-token lifetime limits exposure but does not eliminate risk.
- SimpleJWT token issuance adds database-backed blacklist migrations;
  run migrations before traffic. No user-registration or public write API
  is enabled by this phase.
