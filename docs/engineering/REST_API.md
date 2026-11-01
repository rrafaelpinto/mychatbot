# ResumeBot REST API (v1)

The Django REST Framework backend exposes versioned endpoints consumed by
the independently built React/TypeScript application. Existing Django Admin
and original HTML pages remain available as separate interfaces.

## OpenAPI contract

- `GET /api/schema/`: generated OpenAPI 3 schema
- `GET /api/schema/?format=json`: JSON OpenAPI specification
- `GET /api/docs/`: interactive Swagger UI

The checked-in `frontend/src/api/schema.generated.d.ts` is generated from
Django's OpenAPI schema, rather than maintained as a parallel API definition.
CI detects drift in generated TypeScript types. OpenAPI describes the
interface; authorization is enforced independently by Django.

## Endpoints

| Method | Endpoint | Access |
| --- | --- | --- |
| GET | `/api/v1/candidates/` | Public; active, published profiles |
| GET | `/api/v1/candidates/{slug}/` | Public; approved profile fields and verified, published facts |
| GET | `/api/v1/me/` | Authenticated user |
| GET/PATCH | `/api/v1/me/profile/` | Profile owner |
| GET | `/api/v1/me/facts/` | Profile owner; private review context |
| POST | `/api/v1/me/facts/{id}/review/` | Profile owner; constrained approval/publication transition |
| GET/POST | `/api/v1/candidates/{slug}/chat/` | JWT-authenticated user |
| GET/POST | `/api/v1/candidates/{slug}/guest-chat/` | Public session with separate guest/Turnstile controls |
| GET | `/api/v1/auth/csrf/` | CSRF bootstrap |
| POST | `/api/v1/auth/token/` | Credentials + CSRF |
| POST | `/api/v1/auth/refresh/` | Rotating HttpOnly refresh cookie + CSRF |
| POST | `/api/v1/auth/logout/` | Revokes presented refresh token + CSRF |

Public list endpoints use page-number pagination. Public serializers expose
only explicitly approved fields and facts; owner serializers never expose
another candidate's private documents or review history.

Both chat routes reuse the same Candidate Agent service: authorization,
quota/budget admission, idempotency and evidence revalidation are enforced
on the backend. Responses are instructed to speak in the candidate's
first-person voice and to cite currently approved facts. Anonymous chat
never receives a privileged user JWT.

## Cross-origin security

React keeps a short-lived access token in memory; Django maintains a
rotating, revocable refresh cookie and CSRF defenses. Production requires
explicit credentialed CORS allowlists, matching CSRF trusted origins and
shared-site HTTPS subdomains for default SameSite cookies. In particular,
`Idempotency-Key` must be allowed during cross-origin chat preflights.

Guest access is disabled by default in production. Turnstile hostname/action
verification, session retention, origin quotas and daily/monthly budgets are
independent server-side controls. See [JWT API Security](JWT_API_SECURITY.md)
and [Anonymous Candidate Agent](GUEST_CHAT.md).

## Validate

```sh
uv run python manage.py check
uv run python manage.py spectacular --validate --file .local/openapi.yaml
npm --prefix frontend run api:types
uv run pytest chatbot/tests/test_rest_api.py
```

Run `npm --prefix frontend run api:types` after generating
`/.local/openapi.json` according to [frontend instructions](../../frontend/README.md).
The OpenAPI contract CI workflow checks generated types without a live API
or paid AI calls.
