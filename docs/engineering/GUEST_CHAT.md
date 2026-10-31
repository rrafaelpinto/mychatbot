# Anonymous Candidate Agent

Guest chat is disabled by default. Registered-user access remains unchanged.

## Deployment configuration

Configure the following environment variables before enabling anonymous chat:

- `GUEST_CHAT_ENABLED=true`
- `GUEST_TURNSTILE_SITE_KEY`: the public Cloudflare Turnstile widget key
- `GUEST_TURNSTILE_SECRET_KEY`: the private Siteverify secret
- `GUEST_IP_HASH_SECRET`: independent, randomly generated high-entropy secret
- `GUEST_TRUSTED_PROXY_IPS`: explicit addresses of reverse proxies that
  overwrite X-Forwarded-For before forwarding requests

Use the Turnstile **Managed** widget, restrict its hostnames, and create
separate widgets per environment. Do not use public test credentials in
production. Missing keys with guest chat enabled cause Django startup to
fail. The backend validates each initial token using Siteverify, including
the returned hostname and action; a used or expired token cannot be reused.
Subsequent requests use a server-signed Django session cookie and a
database-backed guest identity.

Only configure trusted proxies under your administrative control. Never put
untrusted client addresses in `GUEST_TRUSTED_PROXY_IPS`. If the app is behind
a reverse proxy but none is configured, clients share the proxy's address
and will hit origin quotas together. The default ignores forwarded headers.

## Initial limits

- 10 admitted requests per guest session, valid for 24 hours
- 4 new guest sessions per origin every 24 hours
- 2 admitted requests per origin per rolling minute
- 20 admitted requests per origin per rolling 24 hours
- 50 admitted guest requests globally per rolling 24 hours
- At most one active provider request per session, with a bounded lease
- Existing candidate-level quotas and monetary reservations remain mandatory

Limits count *admitted attempts*, including provider failures. A new browser
cookie does not reset origin/global limits. IP hashes are HMAC-derived, not raw
IP addresses. Shared IPs can be rate limited together. Bot verification and
limits reduce abuse but do not eliminate distributed attacks.

Project budgets must be set explicitly in production. A suggested initial
cap is `AI_DAILY_BUDGET_USD=0.20` and `AI_MONTHLY_BUDGET_USD=2.50`.
Set a model/pricing configuration with valid reservation assumptions and
monitor actual usage before increasing caps.

## Retention

Guest sessions expire after 24 hours, while conversation text and hashed
origin records are retained for up to seven days. Execute:

```sh
uv run python manage.py cleanup_guest_sessions
```

Schedule the cleanup command daily using the host scheduler. AI usage
records persist for financial audit without conversation text. Deleting
a guest session clears its foreign key from usage records.

Keep the entire feature disabled until the trusted proxy setup, monitoring,
backup policy, test challenge, and budget values are validated in production.

See [Cloudflare Siteverify](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/).
