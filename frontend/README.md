# ResumeBot standalone frontend

React, TypeScript and Vite application served independently from Django. The
design inherits the approved Phase 4 visual prototype and its semantic tokens.

## Local development

Requires Node.js 22 or later and a running Django API on port 8000.

```sh
cd frontend
npm install
cp .env.example .env.local
npm run dev
npm run build
npm test
npm run test:e2e
```

The frontend is served on port 4173. No compiled assets are copied into Django
or served by WhiteNoise. Deploy `dist/` to a static host with HTTPS. Set
`VITE_API_BASE_URL` to the Django API origin at **build time** and configure
`API_CORS_ALLOWED_ORIGINS` and `DJANGO_CSRF_TRUSTED_ORIGINS` on Django with
that exact frontend origin. Prefer same-site subdomains so Secure host-only
HttpOnly refresh cookies work with SameSite=Lax. Never use wildcard credentialed
CORS and never put secrets in Vite environment variables.

The access JWT exists only in JS memory; the backend owns the HttpOnly refresh
cookie. The client bootstraps CSRF and handles refresh and logout. It does not
persist tokens in browser storage. Signed-in chat reuses the DRF API and backend
quotas/budgets; unauthenticated visitors are directed to the existing Django
Turnstile-protected chat, not an unprotected REST substitute.

Only public profile data is rendered to unauthenticated visitors. The UI treats
all API text as plain text, without HTML injection. Public API errors,
withdrawn evidence and model availability are backend-owned policies.

`npm run api:types` generates an OpenAPI snapshot in
`src/api/schema.generated.d.ts` from a running backend. The small typed public
and chat contract currently lives in `src/api/types.ts`; wire generated
types to the application in the next integration slice.

## Scope of this slice

The public profile, discovery and JWT-authenticated chat UI are API-backed.
Owner editing/review UI, schema-generated type consumption, full deployment
acceptance, and the anonymous API guest migration remain follow-up work under
issue #32. This is **not** a production launch.
