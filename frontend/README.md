# ResumeBot standalone frontend

React, TypeScript and Vite application served independently from Django. The
public experience follows the recruiter-first UI layout and semantic tokens
in `src/styles.css`. Use the repository's `ui-ux-review` skill and
[`UI_UX_WORKFLOW.md`](../docs/engineering/UI_UX_WORKFLOW.md) for interface changes.

## Local development

Requires Node.js 22 or later and a running Django API on port 8000.

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
npm run build
npm test
npm run test:e2e
```

The production build runs `scripts/check-build-env.mjs` when
`RESUMEBOT_BUILD_TARGET=production` and requires an HTTPS
`VITE_API_BASE_URL` without an embedded path or secrets. The optional
[Render Blueprint](../render.yaml) configures two separately deployed
services with manual release and no automatic database creation. See the
[production runbook](../docs/engineering/DEPLOYMENT.md#independent-react-and-django-deployment-on-render)
and run `npm run test:deploy` for offline build checks.

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
quotas/budgets. Anonymous chat uses a separate CSRF-protected Django session
endpoint with server-verified Cloudflare Turnstile, origin-based admission,
usage limits and safe evidence revalidation. The original Django HTML chat
remains available as a fallback; neither guest JWTs nor privileged API tokens
are issued for guest requests.

Guest access defaults to disabled in production. Enable `GUEST_CHAT_ENABLED`
only after configuring the existing Turnstile keys, origin hash secret,
trusted proxies and session cleanup schedule documented in the backend
deployment runbook. Register the **React hostname** in the Turnstile widget's
approved hostnames, and include the exact React origin in both
`API_CORS_ALLOWED_ORIGINS` and `DJANGO_CSRF_TRUSTED_ORIGINS`.
Siteverify validates the challenge action and the registered frontend
hostname. Prefer HTTPS same-site subdomains: Django session and CSRF cookies
must actually reach the API, with `credentials: include`. Cross-site
installations require an explicit cookie/SameSite and browser privacy review;
they are not assumed supported by default.

Only public profile data is rendered to unauthenticated visitors. The UI treats
all API text as plain text, without HTML injection. Public API errors,
withdrawn evidence and model availability are backend-owned policies.

Generate the TypeScript contract directly from Django's schema (no live backend needed):

```sh
mkdir -p .local
uv run python manage.py spectacular --format openapi-json --file .local/openapi.json --settings=mychatbot.test_settings
npm --prefix frontend run api:types
```

The generated `src/api/schema.generated.d.ts` file is committed, and the
`OpenAPI Type Contract` CI job fails if it drifts from DRF. Application types
in `src/api/types.ts` consume those schema declarations rather than
duplicating API contracts.

## Product and release state

The public profile, discovery, JWT-authenticated chat, protected guest chat,
owner profile editor, and fact review/visibility controls are API-backed.
The Candidate Agent is instructed to answer recruiter questions in the
candidate's first person, citing verified public facts.

The repository provides an independent static-site Blueprint and read-only
release checks. Actual DNS/TLS provisioning, browser cookie verification,
persistent production database, and real Turnstile-hostname acceptance
remain operational tasks under issue #32. No external AI calls occur in CI.
This is **not** a production launch.
