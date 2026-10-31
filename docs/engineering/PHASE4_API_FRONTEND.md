# Phase 4: API contract and independent frontend

ResumeBot preserves Django as the backend and adds a versioned REST interface.
The future React/TypeScript/Vite frontend is a separate deployable unit under
`frontend/`, with its own lockfile, build and CI. It will **not** be compiled
into Django, and its static files will not be delivered through WhiteNoise.

## Boundaries

- Backend: Django, DRF, drf-spectacular/OpenAPI, authorization policy,
  AI governance, candidate/guest data and PostgreSQL.
- Frontend: React and TypeScript, UI state, layout and API client only.
- Admin and original HTML pages remain available during incremental migration.
- The frontend may be hosted on a separate static-site service or served by
  Nginx/Caddy from a shared VPS without a dedicated Node server process.
- Deployment may expose separate origins, e.g. `app.example.test` and
  `api.example.test`. Configure strict CORS origin allowlists, trusted CSRF
  origins and Secure/SameSite cookie policy only when JWT integration lands.

## API contract policy

- All new APIs use `/api/v1/`, explicit serializers and object authorization
  enforced through database querysets or shared service policies.
- The public read contract exposes only approved and published candidate
  information, and only explicitly verified/public facts. Never serialize
  `phone`, private owner email, source documents, source references, guest
  origin hashes or internal usage/event metadata.
- Authenticated owner read endpoints will initially use existing Django
  session authentication for migration/testing. JWT and separate-origin CORS
  are **not introduced** in the initial API PR.
- Existing HTML chat is retained until a new DRF chat route can reuse the
  original service with equivalent Turnstile, sessions, idempotency, evidence
  authorization, quotas and budget reservation.
- Swagger UI is a schema explorer, not an invitation to bypass permissions.
  The schema defines field allowlists; unauthenticated requests remain limited
  to public resources.
- OpenAPI is the source for TypeScript client types. Version-breaking changes
  require a versioned contract and regression tests.

## Incremental implementation

1. DRF, public read-only candidate endpoints, owner read endpoints, schema
   and privacy tests (issue #29).
2. JWT with short bearer-token lifetime, HttpOnly refresh rotation/logout,
   CSRF on cookie-authenticated state changes, explicit CORS and negative tests
   (issue #30).
3. Visual identity and mobile/desktop prototypes, reviewed before React
   implementation (issue #31).
4. Independent React application, typed contract client, Vitest/Playwright
   and separate deployment (issue #32).

This architecture avoids a new service for each API function and avoids
unnecessary Redis/Celery infrastructure for the low-traffic portfolio.
