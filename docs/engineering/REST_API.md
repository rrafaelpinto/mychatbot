# ResumeBot REST API (v1)

The backend exposes a deliberately small Django REST Framework API for the
independently deployable React client. It also serves the existing Django
Templates and Django Admin until the new frontend is ready.

## OpenAPI and Swagger

- `GET /api/schema/`: OpenAPI 3 schema
- `GET /api/schema/?format=json`: JSON OpenAPI specification
- `GET /api/docs/`: interactive Swagger UI

OpenAPI is the source for generating future TypeScript client types.
These endpoints provide documentation, not authorization privileges.

## Initial read-only endpoints

| Method | Endpoint | Access |
| --- | --- | --- |
| GET | `/api/v1/candidates/` | Public; active and published profiles only |
| GET | `/api/v1/candidates/{slug}/` | Public; public profile and approved facts |
| GET | `/api/v1/me/` | Authenticated account only |
| GET | `/api/v1/me/profile/` | Authenticated owner only |
| GET | `/api/v1/me/facts/` | Authenticated owner only |

List endpoints use page-number pagination (20 items/page).
The public serializer returns profile fields selected for public visibility
and fact `id`, `fact_type`, `content` only when both verified and public.
It never returns private phone, unapproved facts or source provenance.
Owner serializers expose only current-account profile/fact review fields;
they do not expose private raw source documents or upload paths.

**This PR intentionally does not create a second chat implementation.**
The existing Django chat view still enforces identity/session/Turnstile,
AI quota/budget reservation, idempotency and evidence authorization.
The DRF chat endpoint will arrive alongside JWT and secure CORS rules in
issue #30, reusing the original service boundary and regression tests.

## Authentication and deployment

Initial protected read endpoints support Django's existing session
authentication with CSRF enforcement. No JWTs, new cookies, CORS wildcard,
public write operations or client authentication changes are introduced
here. Admin authentication remains unchanged.

The separately deployed React frontend is planned in issue #32.
JWT bearer access tokens, rotating HttpOnly refresh cookies and
cross-origin safeguards must be implemented and tested before wiring
owner authenticated screens. Anonymous chat remains a different
security model and must not receive a user JWT.

Run locally:

```sh
uv run python manage.py check
uv run python manage.py spectacular --file .local/openapi.yaml --validate
uv run pytest chatbot/tests/test_rest_api.py
```

`./.local/` is ignored by Git, so generated schemas stay out of the repo.
In CI, requests to the schema and public/private endpoints are checked
against explicit visibility/authorization invariants.
