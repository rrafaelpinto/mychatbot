# Phase 4: API contract and independent frontend

The approved architecture preserves Django as a modular backend while
deploying the React/TypeScript/Vite frontend as a separately built static
application. Both live in one Git repository, with independent build steps,
environment configuration and deployment targets. React assets are not
compiled into Django or served through WhiteNoise.

## Implemented boundaries

- **Django:** Django REST Framework, drf-spectacular/OpenAPI,
  PostgreSQL, candidate authorization, owner-only review, fact publication,
  JWT/CSRF authentication, guest sessions and AI usage policies.
- **React:** typed HTTP client generated from OpenAPI, public profiles,
  Candidate Agent chat, owner workspace, authentication lifecycle and
  responsive layouts. No provider keys or privileged decisions live in React.
- **Legacy interfaces:** Django Admin and original HTML views remain
  available for administration and fallback usage.
- **Deployment:** an opt-in Render Blueprint defines independent Django and
  React services. Production DNS, TLS, persistent database and browser
  acceptance still require manual provisioning.

## Trust and implementation principles

- All API endpoints are versioned under `/api/v1/`; resource-specific
  serializers expose only approved fields.
- The public API returns only active, published profiles and separately
  verified, public facts; source documents, private contacts and internal AI
  usage records remain unavailable.
- Owner-only operations enforce object authorization and review transition
  policies on the backend, independent of frontend visibility.
- Browser access uses short-lived JWT bearer tokens, a rotating Secure
  HttpOnly refresh cookie and CSRF protection. CORS origins are explicit,
  never wildcarded for credentialed requests.
- Anonymous chat uses a separate server-side session, Turnstile verification,
  quota/budget policies and idempotency. It never receives a user JWT.
- The Candidate Agent answers as the candidate in first person using only
  verified public facts, with structured evidence IDs revalidated by Django.
- OpenAPI-generated TypeScript types are committed and checked for drift
  in CI. Regression tests cover negative authorization and cost-control paths.

## Delivered work

1. DRF, public/owner read endpoints, OpenAPI schema and privacy tests
   (issue #29).
2. JWT token lifecycle, CSRF and CORS hardening, owner review and
   authenticated chat (issue #30).
3. Responsive design direction and visual prototypes (issue #31).
4. Independent React app, typed API client, owner and public experiences,
   guest chat, Vitest/Playwright and safe deployment preparation (issue #32).

## Release verification still outstanding

A live release requires a persistent backed-up PostgreSQL instance, verified
HTTPS site/subdomains, independent service deployment, login/refresh cookie
checks in a real browser, and a controlled Turnstile/guest session
acceptance test before enabling paid AI access. See
[Production deployment](DEPLOYMENT.md).

This design avoids unnecessary distributed application services, Redis/Celery
workers and paid embedding infrastructure for occasional recruiter traffic.
