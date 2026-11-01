# Production deployment

ResumeBot is a low-traffic Django portfolio demonstration, not a multi-tenant SaaS
launch. This runbook prepares deployment but does **not** provision or deploy
services. The production retrieval strategy stays `full_context`. The live
LLM comparison remains optional and deferred.

## Deployment target

The recommended minimal topology is **one Gunicorn web service + one persistent
managed PostgreSQL database**. Render is a suitable example provider. The
database must support the `vector` extension, because the versioned schema
requires pgvector even though semantic retrieval is disabled in public chat.
Render documents pgvector support for PostgreSQL 13+:
https://render.com/docs/postgresql-extensions.

Do **not** choose an expiring or disposable database for actual candidate facts
and conversations. Account for PostgreSQL backups and restoration, not only the
web service price. Avoid Redis, Celery, background workers and paid embeddings
for this small demonstration.

### Managed web service

Configure a Python 3.12 service linked to the repository. Set the build
command to:

```sh
python -m pip install uv && bash scripts/build.sh
```

Set the start command to:

```sh
bash scripts/start.sh
```

The build script installs only locked runtime dependencies and creates
fingerprinted, compressed static assets using WhiteNoise. The start script
launches a single Gunicorn worker with two threads by default; adjust only
when memory and response latency are measured.

Use a dedicated database, and set the following environment variables through
the host's secret manager (never in Git):

| Variable | Requirement |
| --- | --- |
| `RESUMEBOT_ENV` | `production` |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | Unique long random secret |
| `DJANGO_ALLOWED_HOSTS` | Actual platform/domain hostname |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | HTTPS origin for form POST requests |
| `DATABASE_URL` | Managed PostgreSQL internal connection URL |
| `DJANGO_TRUST_X_FORWARDED_PROTO` | `true` only if the host overwrites incoming proxy headers |
| `PUBLIC_REGISTRATION_ENABLED` | `false` for the portfolio |
| `CANDIDATE_UPLOADS_ENABLED` | `false` without persistent media storage |
| `GUEST_CHAT_ENABLED` | `false` until protection and retention are configured |
| `AI_ENABLED` | `false` until the provider and budgets are set |
| `AI_DAILY_BUDGET_USD`, `AI_MONTHLY_BUDGET_USD` | Positive values required before AI is enabled |

The `.env.example` is a **development example**, not a set of production
defaults. Production mode rejects missing required secrets and hosts. It
enables secure cookies, HTTPS redirects and HSTS. Keep HSTS preload disabled
until all domain/subdomain HTTPS requirements are confirmed.

Before the initial start and before deployments containing migrations, run:

```sh
uv run python manage.py migrate --noinput
uv run python manage.py check --deploy
```

Apply migrations using a controlled deploy/release command or provider shell
with the production environment. **Do not migrate during a build against
a shared production database**. Deploying code without its required migration
can cause the `/healthz/` readiness check to fail. Back up the database
before irreversible schema changes.

## Static files and uploaded media

WhiteNoise serves versioned **static** CSS, JavaScript and bundled images
from the web process. It does **not** serve user-uploaded media.

With `CANDIDATE_UPLOADS_ENABLED=false`, both the profile form and file-storage
writes reject uploads. This is intentional: an ephemeral filesystem would
lose source resumes or avatars after a redeploy. The existing static default
avatar can be used for the demonstration.

If uploads become necessary, configure separate, **durable**
`PUBLIC_MEDIA_ROOT` and `PRIVATE_MEDIA_ROOT` paths and enable
`CANDIDATE_UPLOADS_ENABLED=true` only after verifying persistence across
deploys. Public images then need a dedicated media delivery solution; raw
candidate documents must remain private with **no public URLs**. Do not
attach a shared public media URL to the private document directory. Render's
default filesystem is ephemeral:
https://render.com/docs/deploys.

## Email and account administration

Public signups and password reset requests are closed by default in production.
Provision the initial owner account through a trusted management console:

```sh
uv run python manage.py createsuperuser
```

Before enabling public self-registration or password reset, configure a
verified SMTP sender, outbound email credentials and an abuse policy.
Test an activation/password-reset email using non-sensitive test accounts.
Never use console email backend with real external user accounts.

Candidate profile approval and publication are separate admin decisions.
Import or create only facts deliberately reviewed for public display.
Source documents and extracted text remain private.

## Enabling the public Candidate Agent

1. Verify one active, published candidate profile and facts with
   `verification_status=verified` and `is_public=true`.
2. Set `OPENAI_API_KEY` and validate the configured model/token price.
3. Assign small positive daily and monthly AI budgets and enable
   `AI_ENABLED=true`. Keep semantic indexing and query disabled.
4. Create Cloudflare Turnstile keys bound to the exact host and set
   `GUEST_TURNSTILE_SITE_KEY`, `GUEST_TURNSTILE_SECRET_KEY` and a separate,
   randomly generated `GUEST_IP_HASH_SECRET`.
5. Verify the real reverse proxy address and set
   `GUEST_TRUSTED_PROXY_IPS` **only for proxies that overwrite forwarding
   headers**.
6. Configure a daily scheduler for
   `uv run python manage.py cleanup_guest_sessions`, verify its run history,
   and then set `GUEST_CLEANUP_SCHEDULED=true`.
7. Enable `GUEST_CHAT_ENABLED=true` and make one controlled test request.
   Confirm quota rejection, privacy isolation, budget usage and valid
   evidence citations.

Guest chat fails startup in production if the cleanup-scheduled flag is
absent; the flag only records a human-verified operational prerequisite.
**It does not create a scheduler.** Render Cron Jobs are an option, but
introduce a separate recurring charge:
https://render.com/docs/cronjobs.

## Release verification and rollback

- Check `GET /healthz/`: HTTP 200 only when the database responds; HTTP
  503 on DB failure. Do not expose database errors or credentials.
- Check `/static/` CSS and image responses with `DEBUG=false`.
- Confirm unauthenticated access to the published profile, 404 for closed
  registration, and no upload permissions in a production process.
- Check that private facts, documents and other candidates' conversations
  cannot be accessed across account boundaries.
- Confirm the working Turnstile challenge and the guest usage cap if
  anonymous chat is enabled.
- Check the application logs (Gunicorn stdout/stderr), unsuccessful responses,
  provider timeouts, quota/budget usage, and cleanup task failures.
- Verify database backups and perform a restore rehearsal before retaining
  real user data.
- Keep `AI_ENABLED=false` as the emergency paid-provider kill switch.
  Disabling AI does not remove public profile pages.

For rollback, first disable guest chat and AI if needed. Roll back the web
release to the last healthy artifact. **Do not blindly reverse database
migrations**: forward-compatible schema changes and database backups are
required for safe recovery. Restoring from backup may be necessary for
incompatible migrations.

## Independent React and Django deployment on Render

The optional [Render Blueprint](../../render.yaml) defines a Django web service
and a React static site, each with its own build and release. **It does not
define a database, DNS records, Turnstile widget, account, or scheduler.**
Blueprint synchronization is an explicit action in the Render Dashboard and
can create a **paid** service. Both services have
`autoDeployTrigger: off`; merging a PR does not trigger a live deployment.

The backend uses the smallest paid web compute plan (512 MB). This is
intentional: Render's free web plan does not support a pre-deploy migration
command or shell access, and spins down while idle. Check current Render
prices and service limits before activating the Blueprint:
https://render.com/docs/free and https://render.com/docs/compute-plans.
The frontend is a free static site, subject to Render's included usage.
A managed, **persistent and backed-up** PostgreSQL instance with pgvector is
a separate billed decision. Never attach a 30-day expiring free database to
real profile or conversation data.

### Release procedure

1. Choose a domain you control. Use **two HTTPS subdomains on the same site**,
   for example `app.example.com` for React and `api.example.com` for
   Django. Reserve both and point them at the corresponding Render services
   using Render's verified DNS/CNAME instructions. Do not commit provisional
   domains or pretend to have validated DNS or TLS.
2. Create a persistent PostgreSQL database with pgvector enabled, backups
   configured, and a documented restore procedure. Record its **internal**
   connection URL in Render secrets, not Git or a Vite variable.
3. Review [render.yaml](../../render.yaml) and the costs, then activate the
   Blueprint **manually**. Enter the `sync: false` values in Render:
   `DATABASE_URL` (private), `DJANGO_ALLOWED_HOSTS` (API hostname without
   scheme), `DJANGO_CSRF_TRUSTED_ORIGINS` (both actual HTTPS origins),
   `API_CORS_ALLOWED_ORIGINS` (React HTTPS origin only), and
   `VITE_API_BASE_URL` (Django HTTPS origin). These values are not inferred
   from the Render service name. Render creates independent app/JWT secrets
   but does not expose their plaintext to the frontend.
4. Confirm Render terminates TLS and sets trustworthy
   `X-Forwarded-Proto` before keeping
   `DJANGO_TRUST_X_FORWARDED_PROTO=true`. The Blueprint starts with
   a short HSTS lifetime and does not include subdomains. Review broader HSTS
   settings only after DNS/TLS is stable.
5. Verify the database backup, then **manually deploy the backend first**.
   Its paid-service `preDeployCommand` applies migrations after the build,
   never during the static frontend build. Verify `/healthz/` and
   `/api/v1/candidates/`; create the owner through the trusted management
   console, approve a public profile and verify that private data is not
   exposed. Keep `AI_ENABLED=false` and `GUEST_CHAT_ENABLED=false`.
6. **Manually deploy the frontend.** The production Vite build refuses to
   run unless `VITE_API_BASE_URL` is an explicit HTTPS API origin. Confirm
   it points to the deployed backend, not localhost or an old environment.
   Static files are published from `frontend/dist` independently of
   Django's WhiteNoise.
7. Run the read-only smoke command from a trusted machine:

   ```sh
   python scripts/check_deployment.py \
     --frontend-origin https://app.example.com \
     --api-origin https://api.example.com \
     --candidate published-candidate-slug
   ```

   This checks HTML, database readiness, CSRF bootstrap/cookie flags,
   credentialed CORS, `Idempotency-Key` preflight, public API JSON, and
   optionally a **fresh anonymous** guest session status. It makes no
   state-changing or paid AI requests. The command does not prove that the
   browser will persist cookies or solve Turnstile.
8. Manually verify in a real browser: React profile, CSRF cookie, owner
   login, refresh after an access-token expiry, logout and revoked refresh,
   and no access to private facts across accounts. Inspect browser network
   requests and cookie attributes. Guest chat remains disabled until a
   separate controlled enablement check.

### Guest access activation gate

The default `SameSite=Lax` session/CSRF and HttpOnly refresh cookies work
for **same-site HTTPS subdomains**. Separate `*.onrender.com` hosts must not
be assumed same-site for cross-origin cookies; use your own shared parent
domain before enabling login/guest access in the React app. Keep cookies
host-only and credentialed CORS restricted to the known frontend origin.

Only after validating TLS, the registered Turnstile **frontend hostname**,
trusted proxy IP handling, and a real scheduled guest cleanup job should you
supply `GUEST_TURNSTILE_SITE_KEY`, `GUEST_TURNSTILE_SECRET_KEY`,
`GUEST_IP_HASH_SECRET`, a verified small positive AI budget,
`OPENAI_API_KEY`, and finally enable the AI and guest feature flags.
The `GUEST_CLEANUP_SCHEDULED` flag must reflect a real operating scheduler;
the Blueprint deliberately does **not** create a cron job or set it true.

Perform one explicitly budgeted real Turnstile challenge from the frontend
and confirm subsequent guest requests use the same session, idempotency
prevents repeat charges, withdrawn evidence is not disclosed, and limits
return HTTP 429. Test the negative cases without a provider call where
possible. Check the logs and budget counters after the controlled test,
then decide whether to keep paid AI enabled. Browser-based verification
cannot be completed by CI without real configured domains and credentials.

Avoid any irreversible migration before a database backup. If an actual
release fails, disable paid features, roll back the web/static releases,
and restore or forward-fix the database separately if necessary.

## Deliberately deferred

The paid 30-question real-model evaluation, semantic retrieval rollout,
dedicated object storage, automation of account provisioning, uptime alerts
and production cost measurements are separate follow-up decisions. No claim
of live deployment or production verification is made by CI alone.
