# ResumeBot Phase 0 Architectural Assessment

Assessment date: 2026-09-01

Scope: the repository at the start of the structured modernization. This is an assessment and baseline only; it does not implement ResumeBot 2.0.

# 1. Executive Summary

ResumeBot is a small Django monolith with two application entities, server-rendered Bootstrap templates, PostgreSQL configuration, synchronous resume parsing, and synchronous OpenAI calls through LangChain. Its size makes incremental modernization practical. The difficult part is not code volume: the current data model and request boundaries combine identity, publication, resume truth, chat authorization, and paid AI execution in ways that are unsafe for a multi-user product.

Useful behavior should be retained: Django authentication, email activation, candidate ownership through a `OneToOneField`, PostgreSQL, simple administrative access, and the existing server-rendered UI. A rewrite, React introduction, RAG stack, agent framework, Redis, or LangGraph would add risk before the required policy boundaries exist.

The most urgent findings are:

- a database password and Django secret were committed; Phase 0 removed the literal current values, but the database credential must be rotated and Git history must be treated as compromised;
- `public_profile` only controls directory listing. Any authenticated user with a slug can chat with a private or inactive candidate and see the candidate email; `activate` is not consulted anywhere;
- every verified Django user has unmetered access to paid chat and resume-formatting calls; there are no rate, quota, token, cost, budget, or idempotency controls;
- a question triggers one independent model call per 2,000-character resume chunk and concatenates the answers, multiplying cost and producing contradictory or repetitive output;
- the LLM can overwrite the only stored resume text, so generated formatting can become indistinguishable from source data;
- upload validation is extension-only, processing is synchronous, extracted PII is printed, and failed parsing can leave a file in a media location not covered by the README's suggested Nginx rule;
- the AJAX chat inserts untrusted user and model strings as HTML, creating an XSS surface;
- the declared environment is not reproducible: `django_extensions` is configured but absent from requirements, no Python version is declared, and the pinned snapshot failed under uv's Python 3.14 default but worked under Python 3.12.

Modernization difficulty is **moderate** if performed as a sequence of policy, test, and data-boundary changes within Django. It becomes high if product features are built before authorization, verified-fact, and cost-control foundations.

# 2. Current Architecture

The deployed shape implied by the repository is a synchronous three-tier Django application:

```text
Browser (Bootstrap 4 + jQuery, server-rendered HTML)
        |
        | session cookie + CSRF-protected POST
        v
Django URL routes -> function views -> forms/models
        |                         |        |
        |                         |        +-> PostgreSQL
        |                         +-> local filesystem media
        |
        +-> LangChain LLMChain -> OpenAI gpt-4o-mini

Operational edge described only in README:
Nginx -> Gunicorn -> Django
```

There is one custom app, `chatbot`. There is no DRF API, React application, background worker, task queue, cache, vector store, provider abstraction, usage ledger, or observability integration. Django templates implement candidate management, discovery, chat, and staff interaction review. Django's built-in `User` plus `django-registration` provide accounts and activation email.

`chatbot.prompts` creates two process-global `LLMChain` objects at module import. Requests invoke those chains synchronously from views. PostgreSQL is configured directly in `settings.py`/`local_settings.py`; uploads use Django's default local `FileSystemStorage`.

# 3. Repository Map

| Path | Current responsibility |
| --- | --- |
| `manage.py` | Standard Django command entry point. |
| `mychatbot/settings.py` | Shared settings, PostgreSQL defaults, SMTP, static/media paths, installed apps, and import of local overrides. |
| `mychatbot/local_settings.py` | Tracked host/database overrides. Before Phase 0 it contained a literal database password and forced debug on. |
| `mychatbot/urls.py` | Admin, registration/auth routes, application routes, and development media/static serving. |
| `mychatbot/utils.py` | PDF/DOCX text extraction and deletion of successfully processed source files. |
| `mychatbot/test_settings.py` | Phase 0-only hermetic SQLite settings for characterization tests; avoids requiring a developer PostgreSQL database. |
| `chatbot/models.py` | `Candidate` and `Interaction`. |
| `chatbot/forms.py` | Candidate profile form and filename-extension validation for resumes. |
| `chatbot/views.py` | All product request orchestration, persistence, access checks, file processing, and model calls. |
| `chatbot/prompts.py` | Two prompts and global OpenAI-backed LangChain chains. |
| `chatbot/urls.py` | About, candidate management/list, profile, chat, format, and staff interaction routes. |
| `chatbot/admin.py` | Basic candidate and interaction administration. |
| `chatbot/templates/` | Bootstrap/jQuery server-rendered UI and registration/auth templates. |
| `mychatbot/static/` | Local CSS and image assets. Bootstrap and jQuery are CDN-loaded. |
| `chatbot/migrations/0001_initial.py` | The complete custom schema; there is only one migration. |
| `chatbot/fixtures/initial_data.json` | One Django candidate fixture containing resume/profile data. |
| `chatbot/fixtures/*_CV.json` | Two structured CV JSON documents that are not Django fixture-shaped and appear unused at runtime. They contain professional/PII data and need an explicit consent/retention decision. |
| `chatbot/tests.py` | Six Phase 0 characterization tests; it was empty at assessment start. |
| `requirements.txt` | Fully pinned mixture of direct and transitive runtime dependencies. |
| `README.md` | Basic setup plus manual Gunicorn/Nginx notes. It is not a complete or reproducible deployment specification. |

No Docker files, CI workflows, `pyproject.toml`, lock file, Python version file, lint/format/type configuration, pre-commit configuration, checked-in service definitions, or architecture/security documentation existed.

# 4. Current Request Flows

## Candidate registration and update

```text
anonymous POST /accounts/register/
  -> django-registration activation backend
  -> inactive Django User + activation email
  -> activation link within 3 days
  -> active User may log in

authenticated GET/POST /candidate/
  -> @login_required
  -> Candidate.objects.get(user=request.user), or new instance
  -> CandidateRegistrationForm
  -> candidate.user = request.user
  -> optional resume processing
  -> Candidate.save()
```

Editing is correctly scoped to the logged-in user's candidate. The candidate can independently set name, candidate email, phone, LinkedIn, image, resume file, and `public_profile`. `Candidate.email` is separate from the activated `User.email`, can be changed without verification, and is rendered in chat. `activate` is neither in the form nor enforced. A user without a candidate gets a new candidate; the nullable user relationship also permits admin/fixture candidates without an owner.

Slug creation occurs only when the slug is empty: `slugify(name)`. It does not update after a name change, has no collision-resolution strategy, and a duplicate or empty-normalized slug reaches the unique database constraint. The broad view exception returns raw exception text to the user.

## Resume upload

```text
multipart POST /candidate/
  -> extension check: pdf or docx
  -> FileSystemStorage.save(original filename under MEDIA_ROOT)
  -> local absolute path
  -> PyMuPDF or python-docx synchronous extraction
  -> extracted full text printed to stdout
  -> temporary source deleted on successful extraction
  -> Candidate.resume overwritten with one TextField value
```

The file is not retained as a source document and no provenance, checksum, type inspection, size bound, malware scan, processing status, or extraction review exists. On parser error, deletion is skipped and the view displays the exception. The README protects `/media/upload/`, but the code saves at the default media root, so that rule does not match these temporary files. Candidate images are retained under `candidate_images/` and exposed through their media URL.

## Candidate discovery

```text
authenticated GET /candidates/
  -> Candidate.objects.filter(public_profile=True)
  -> name-ordered list
  -> link to /chat/<slug>/
```

Discovery requires a full account and does not filter `activate`. There is no `/u/<slug>` public profile. The about page is anonymous and hard-codes one candidate chat link.

## Candidate chat

```text
authenticated GET/POST /chat/<slug>/
  -> Candidate lookup by slug (no public_profile/activate policy)
  -> current user's Interaction rows for candidate
  -> on POST, read unbounded question
  -> split full Candidate.resume into 2,000-character chunks, no overlap
  -> one synchronous gpt-4o-mini call for every chunk
  -> concatenate independent answers without separator/synthesis
  -> store one Interaction question/combined response
  -> JSON response
```

Authentication and CSRF are present. Candidate visibility, approval, agent entitlement, input scope, moderation, rate, quota, global budget, and provider availability checks are absent. A provider failure after earlier chunk calls loses those costs and stores no interaction. Double submission has no idempotency protection.

## Interaction persistence and access

Each `Interaction` stores one user/candidate/question/response/timestamp tuple. A chat page shows only the logged-in user's rows for that candidate, which provides a useful current isolation property. Staff users can group and inspect every user/candidate pair. A candidate cannot review other users' interactions with their agent. There is no conversation/session, message role, status, provider metadata, token/cost record, evidence link, retention policy, deletion workflow, or consent/audit event.

# 5. Current Data Model

```text
Django User 1 ---- 0..1 Candidate
     |                    |
     |                    |
     +---- * Interaction *+
```

## Candidate

`Candidate` owns display identity, contact data, the entire extracted resume, slug, image, a directory flag, and an unused activation flag. This mixes account ownership, professional profile, source knowledge, public projection, and moderation state.

Limitations:

- candidate ownership is nullable, weakening the future invariant that tenant data has an owner;
- the user email and candidate email have no synchronization or verification relationship;
- `resume` is a mutable text blob with no raw source, structure, verification state, version, evidence, or privacy classification;
- `public_profile=True` by default and is candidate-controlled;
- `activate=True` by default but has no behavioral effect;
- publication and platform approval are not modeled;
- one generated formatting response can replace the only candidate knowledge copy;
- one deterministic slug attempt does not handle duplicates, Unicode collisions, reserved paths, or rename policy.

## Interaction

`Interaction` is an exchange, not a conversation. It cannot represent system events, multi-message context, streaming, retries, failures, tool calls, evidence, moderation, or usage. Foreign keys and chat filtering correctly associate a row with a recruiter user and candidate, but there is no explicit tenant policy layer and no candidate-facing access model.

# 6. Current AI Architecture

The provider is OpenAI through `langchain-openai`; both chains select `gpt-4o-mini`. The code uses `PromptTemplate`, the deprecated `LLMChain` class, and deprecated `.run()` calls. The test run emits the LangChain deprecation warning. Chains are initialized once at Python module import, once per application process/worker, which couples URL/view import to provider configuration and makes tests/startup less isolated.

There are two prompts:

1. `extraction_prompt` is actually a Markdown formatter. It asks the model to preserve all information, but it has no structured schema, validation, evidence, or factual-diff check. `/format_resume/` invokes it through a state-changing GET and overwrites `Candidate.resume`.
2. `resumebot` instructs first-person, honest answers and supplies a fallback phrase. Resume and question are interpolated into the same prompt with labels but no robust instruction/data boundary.

For chat, the entire current resume is considered on every question. Character splitting occurs at 2,000 characters with no overlap. For `N` chunks, the system performs `N` independent provider calls. Each chunk is asked to answer the entire question; outputs are concatenated directly. There is no retrieval, ranking, reranking, synthesis call, deduplication, evidence capture, factual validator, or conversation context.

Reliability and cost consequences:

- cost and latency grow linearly with resume length;
- every chunk can generate a complete answer, causing repetition and contradictions;
- relevant facts divided across chunk boundaries cannot be jointly reasoned about;
- chunks lacking evidence can correctly say “no information” and that refusal is appended to answers from relevant chunks;
- default model output limits, temperature, timeout, retry, and provider options are not explicitly controlled;
- no token or cost metadata is captured;
- partial provider success is billed but discarded when a later call fails;
- repeated clicks/retries are indistinguishable from new operations;
- prompt injection in either the resume or question can compete with application instructions;
- model output is treated as truth when the formatting endpoint overwrites resume text.

RAG is not warranted in Phase 0 or as the first Phase 1 change. The immediate need is a verified-data boundary and a single controlled AI gateway. Retrieval should follow structured facts, document provenance, authorization, and evaluations.

# 7. Authentication and Authorization

Current authentication uses Django sessions and password authentication. `django-registration`'s activation backend provides activation email and a three-day activation window. CSRF middleware is enabled, and the AJAX POST includes a token.

Actual endpoint rules:

| Surface | Rule |
| --- | --- |
| About | Anonymous. |
| Registration/login/password reset | Django/django-registration rules. |
| Candidate create/edit/profile | Any authenticated user; object lookup uses `request.user`. |
| Candidate directory | Any authenticated user; `public_profile=True` only. |
| Chat GET/POST | Any authenticated user; any candidate slug; flags ignored. |
| Resume formatting | Any authenticated candidate owner; flags ignored; state change and paid call via GET. |
| Interaction listing/detail | Any `is_staff` user. |
| Django admin | Normal Django staff/model permission behavior. |

Good current boundaries are owner-scoped candidate editing, user-scoped chat history, staff-only global interaction screens, session authentication, CSRF middleware, and password validators.

Missing boundaries are candidate lifecycle approval, publication approval, `activate` enforcement, private-profile access control, recruiter-specific verified identity/grants, operation authorization, candidate access to authorized interaction analytics, quota/budget policy, and reusable object-level policy functions. Frontend visibility is not relied upon for existing owner scoping, which is correct.

# 8. Problems and Technical Debt

Severity reflects the target multi-user product and plausible exposure, not just code style.

## CRITICAL

### Committed secrets

- **Problem:** a literal PostgreSQL password was tracked in `mychatbot/local_settings.py`, and a Django signing key was tracked in `mychatbot/settings.py`.
- **Impact:** anyone with repository/history access can attempt database access and forge data protected by the Django secret if the values were deployed. Removing current literals does not remove history.
- **Evidence/location:** Git-tracked settings files; Phase 0 replaced literals with `POSTGRES_PASSWORD` and `DJANGO_SECRET_KEY` environment reads.
- **Recommended direction:** rotate both deployed credentials immediately, invalidate relevant sessions/tokens, audit access, use environment/secret-store injection, and coordinate any history rewrite separately. Never put real values in `.env.example`.

No other issue was classified critical in the current authenticated portfolio deployment. Several high issues become critical before anonymous/public scale.

## HIGH

### Private/inactive candidate access is not enforced

- **Problem:** chat resolves `Candidate` by slug alone; `public_profile` controls only listing and `activate` is unused. Candidate email is rendered on the chat page.
- **Impact:** direct-object access exposes supposedly private profile/contact data and paid agent access to any authenticated user who obtains or guesses a slug. Suspended candidates cannot be disabled.
- **Evidence/location:** `chatbot/views.py` candidate list and chat queries; `chatbot/models.py` flag help text; Phase 0 test `test_direct_chat_currently_allows_non_public_inactive_candidate`.
- **Recommended direction:** define one server-side visibility/operation policy, distinguish public publication from AI entitlement, enforce it in every queryset/service, and test deny paths including “no provider call.”

### Unbounded paid AI surface

- **Problem:** every activated Django user can call chat and format operations without rate, quota, budget, input size, or idempotency checks.
- **Impact:** a single user, automation, long resume, or repeated request can exhaust project budget and degrade service.
- **Evidence/location:** `chatbot/views.py` calls provider chains directly; no usage/limit configuration or model exists.
- **Recommended direction:** route all paid operations through a central policy/gateway that authenticates, authorizes, validates scope, rate-limits, reserves quota/budget, calls the provider, and records final usage.

### Chunk fan-out and unsafe resume overwrite

- **Problem:** chat calls the LLM once per character chunk; formatting makes a paid call through GET and replaces the only resume field with model output.
- **Impact:** excessive cost, duplicate/contradictory answers, accidental calls, loss/corruption of verified source data, and hallucinations becoming durable candidate facts.
- **Evidence/location:** `chatbot/views.py:27-34` and `chatbot/views.py:101-110` at assessment time.
- **Recommended direction:** stop model writes to source data, require POST and explicit operation policy, preserve immutable source documents and approved facts, and use one bounded answer operation until retrieval is justified.

### Upload boundary is unsafe

- **Problem:** extension-only validation, original filename storage in media root, synchronous parsing, PII logging, no size/content/malware controls, and incomplete cleanup on failure.
- **Impact:** parser/resource-exhaustion attacks, private document exposure, log disclosure, request-worker exhaustion, and orphan files.
- **Evidence/location:** `chatbot/forms.py`, `chatbot/views.py:45-64`, `mychatbot/utils.py`; README blocks a different `/media/upload/` path.
- **Recommended direction:** private storage, generated keys, allowlisted MIME/signature validation, explicit size/page limits, safe cleanup in `finally`, sanitized errors, no content logs, and a persisted document/processing state. Add asynchronous processing only when workload evidence requires it.

### Untrusted HTML insertion in chat

- **Problem:** jQuery `.append()` builds HTML with the raw question and raw model JSON response.
- **Impact:** malicious model output or input can execute script in the authenticated origin; model output is untrusted even when prompted to behave.
- **Evidence/location:** `chatbot/templates/chat.html` AJAX handlers.
- **Recommended direction:** create DOM text nodes/use `.text()`, apply context-appropriate escaping, validate JSON response shape, add browser regression coverage, and later adopt a CSP.

## MEDIUM

### Identity/lifecycle concepts are conflated

- **Problem:** `User.is_active`, `Candidate.activate`, `public_profile`, ownership, and candidate-controlled publication lack defined relationships.
- **Impact:** approval, suspension, email verification, publication, and paid AI access cannot be reasoned about consistently.
- **Evidence/location:** models, form, views, and registration configuration.
- **Recommended direction:** model email verification, platform approval, publication, and AI entitlement as separate dimensions; derive effective access through policy.

### Resume data has no verification or provenance

- **Problem:** one mutable text field is both extracted input and agent knowledge.
- **Impact:** no factual review, privacy classification, evidence mapping, versioning, or reliable tailored-resume validation.
- **Evidence/location:** `Candidate.resume` and both prompts.
- **Recommended direction:** raw document -> extraction candidate facts -> candidate approval -> verified facts -> public projection/retrieval.

### Error handling and observability are inadequate

- **Problem:** broad exception text reaches users, provider errors become 500s, PII/counts are printed, AJAX has no failure behavior, and no structured logs/tracing exist.
- **Impact:** information leakage, poor supportability, uncertain paid-call outcomes, and bad UX.
- **Evidence/location:** candidate management exception, `print()` calls, direct chain calls, chat JavaScript.
- **Recommended direction:** typed service errors, sanitized user messages, structured PII-safe logs, request/operation identifiers, timeout/failure statuses, and graceful AI disablement.

### Dependency contract does not reproduce startup

- **Problem:** `django_extensions` is installed in settings but missing from `requirements.txt`; no Python constraint exists. Dependencies are a manually pinned transitive snapshot.
- **Impact:** `pip install -r requirements.txt` cannot start normal settings; platform compatibility is implicit. uv selected Python 3.14 and failed building `tiktoken==0.7.0`; Python 3.12 succeeded.
- **Evidence/location:** settings, requirements, Phase 0 commands.
- **Recommended direction:** declare Python 3.12 initially, identify direct dependencies, move to `pyproject.toml` + committed `uv.lock`, and keep an exported requirements file temporarily only if deployment needs it.

### Slug and candidate identity integrity are weak

- **Problem:** nullable owner, independently editable/unverified candidate email, simple slug generation, and no collision/reserved-name handling.
- **Impact:** orphan profiles, misleading contact identity, failed saves, and unstable public routing policy.
- **Evidence/location:** candidate model/form/save.
- **Recommended direction:** inventory existing null owners, define legacy/system ownership, verify public contacts separately, and introduce an explicit stable slug allocation policy before `/u/` launch.

### Interaction representation is too coarse

- **Problem:** each row combines question and response with no conversation, operation status, evidence, usage, or retention state.
- **Impact:** future context, audits, retries, evaluations, and candidate analytics cannot be represented accurately.
- **Evidence/location:** `Interaction` model and staff views.
- **Recommended direction:** evolve incrementally toward Conversation + Message while keeping legacy rows readable; keep UsageEvent separate from conversational content.

### CDN assets lack an explicit browser security policy

- **Problem:** Bootstrap/jQuery load from third-party CDNs without SRI and no CSP is configured.
- **Impact:** supply-chain compromise or overly permissive inline-script requirements affect authenticated pages.
- **Evidence/location:** `base.html` and inline chat script.
- **Recommended direction:** pin/self-host or add integrity/crossorigin attributes, move inline code to static files, then deploy a measured CSP.

## LOW

- README setup uses conflicting virtual-environment paths, documents port 8001 while `runserver` defaults to 8000, and contains environment-specific manual operations.
- `django.contrib.sites` is not installed although `SITE_ID` is set; domain/protocol/email configuration is fragmented.
- Logging uses `print`, and interaction grouping performs a count only for stdout.
- `target="_blank"` links lack `rel="noopener noreferrer"`.
- The admin exposes basic data but has no moderation/usage-oriented filters or actions.
- The about page and metadata are hard-coded to the original personal portfolio identity.

# 9. Security Assessment

## Authentication

Session authentication, password validators, activation email, login requirements, and CSRF middleware are reasonable foundations. However, email verification is represented indirectly by account activation and does not cover the separately editable candidate contact email. Password reset depends on incomplete SMTP/default sender configuration. There is no MFA for staff, recruiter-specific verification, session policy documentation, or brute-force/rate controls.

## Authorization and isolation

Candidate editing and ordinary chat-history reads use the current user correctly. Staff-wide interaction access is explicit. The main authorization flaw is candidate resource selection by slug without publication/activation policy. Object-level decisions are embedded in individual views instead of a reusable policy/query layer. Future DRF/frontend work must not duplicate these rules client-side.

Required invariant tests include Candidate A cannot read/change Candidate B, Recruiter A cannot see Recruiter B's conversation, unpublished/suspended candidates cannot be discovered or queried without an explicit preview grant, and a denied paid operation makes zero provider calls.

## Public/private data and PII

The chat view reveals candidate email and optional LinkedIn to every authenticated user, including for private/inactive profiles. Resume and interaction content are high-value PII stored without retention, deletion, consent, export, or field-level public/private policy. CV fixtures in Git contain real-looking professional data and should be reviewed for consent and necessity. Logs currently receive full extracted resume text. Backups, encryption, production access, and retention are undocumented.

## Uploads

Resume and image uploads need explicit limits and private storage. Extension validation is not content validation. Complex PDF/DOCX inputs are untrusted parser data and potential decompression/parser/resource attacks. Processing in a web worker increases denial-of-service impact. A temporary resume file can remain if parsing fails, and the documented Nginx protection does not match its actual path.

## Secrets and configuration

The committed secrets are the only Phase 0 issue requiring a direct security change. Literal values were removed from the working tree and debug now defaults off in local settings. Rotation and historical remediation remain owner/operations actions. Production should fail closed when required secrets are absent; the current development fallback for `DJANGO_SECRET_KEY` is intentionally not a production solution.

Django deployment hardening is otherwise absent: HTTPS redirect/HSTS, secure session/CSRF cookies, proxy SSL header, CSP, trusted origins, secure secret validation, and production checks are not encoded. The Nginx/systemd examples are documentation, not versioned verified configuration.

## Prompt injection and data exfiltration

Resume documents and recruiter questions are placed directly into a prompt. A document/JD can instruct the model to ignore constraints, and there is no separation of verified private facts from public facts. The present prompt's prose is not a security boundary. Future design must select only authorized evidence before prompt construction, label external material as data, restrict tools, validate structured outputs, and post-check claims against evidence. Private data that never enters the model context cannot be exfiltrated by prompt injection.

## Abuse and AI endpoints

Full Django registration/activation adds friction, but after activation the AI surface is unlimited. There is no off-topic/abuse classifier, deterministic scope gate, input length bound, rate limit, quota, budget, or global kill switch. The formatting GET is susceptible to accidental/replayed calls, and chat lacks idempotency. Scope classification should live in the AI application/policy layer before retrieval/provider invocation, with deterministic rejection for clear policy cases and a bounded classifier only where ambiguity warrants cost.

# 10. AI Cost Risk Assessment

Current paid operations are:

| Operation | Trigger | Call pattern | Main risk |
| --- | --- | --- | --- |
| Candidate chat | authenticated POST | `ceil(character-split resume / 2000)` calls, subject to splitter behavior | linear fan-out, unlimited repeats/users, no accounting |
| Resume formatting | authenticated candidate GET | one call with full resume | accidental/replayed GET, source overwrite, no accounting |

There is no usage record for success or failure, input/output tokens, model, candidate, operation, latency, estimated cost, or request identity. Provider retries may add cost without application visibility. A later chunk failure can bill earlier calls without storing an interaction. There is no graceful mode in which profiles remain available while AI is disabled.

The target pipeline should be implemented once and reused:

```text
request + operation id
  -> authenticated/verified identity
  -> candidate/resource authorization
  -> operation and domain-scope validation
  -> rate limit
  -> per-identity/per-candidate/per-operation quota reservation
  -> project daily/monthly budget reservation
  -> provider adapter call with timeout and bounded tokens
  -> record actual tokens/cost/status
  -> reconcile reservation
  -> grounded output validation and response
```

Checks should occur before paid calls. Reservation prevents concurrent requests from all passing the same remaining budget. The final project circuit breaker must be a server-side configuration/policy check and return a typed “AI temporarily unavailable” result while profile pages remain functional. Exact quotas and prices must be configuration, not code constants. Rate limiting and durable budget accounting solve different problems and both are needed. Redis is not justified yet; PostgreSQL transactions/advisory or row locks can provide an initial durable budget ledger at this scale.

# 11. Developer Tooling Assessment

## Current state

- Dependency installation is `pip install -r requirements.txt` into a manually created venv.
- All 59 packages are exact-pinned, but direct and transitive dependencies are mixed and there are no hashes or resolver metadata.
- `django_extensions` is required by settings but absent from the requirements file, so a clean normal startup fails.
- No Python version/constraint is declared. The assessor's active Python was 3.12.8, while uv defaulted to 3.14 and failed because pinned `tiktoken` needed an unavailable Rust build; explicit Python 3.12 succeeded.
- The active global environment had Django 5.2.5 and almost none of the project dependencies, demonstrating venv ambiguity.
- Runtime and development dependencies are not separated. `pytest`, `pytest-django`, uv, and Ruff are not project dependencies/configuration.
- Tests use Django's unittest runner. The suite was empty; Phase 0 added six `TestCase` characterization tests and a SQLite test settings module.
- No lint, format, import sorting, static type, security scanner, pre-commit, coverage, or CI configuration exists.
- Deployment is manual and environment-specific in README; no checked-in systemd/Nginx/Docker/PAAS configuration validates parity.
- `pip check` on the unrelated active global environment reported a requests-version conflict, further evidence that global tooling is not a valid project baseline.

## Phase 0 test and check baseline

- Framework: Django's built-in unittest runner and `django.test.TestCase`.
- Starting suite: zero meaningful tests (`chatbot/tests.py` contained only the generated placeholder).
- Standard command result: `python manage.py test --verbosity 2` failed before discovery with `ModuleNotFoundError: django_extensions`.
- Isolated declared-dependency result: `uv run --python 3.12 --with-requirements requirements.txt python manage.py test --settings=mychatbot.test_settings --verbosity 2` passed all 6 characterization tests in 0.043 seconds.
- Covered behavior: candidate-management login, owner-scoped update, directory visibility, current private/inactive direct-chat behavior, recruiter chat-history isolation, and successful interaction persistence with a mocked provider.
- Deployment check: Django reported five hardening warnings for HSTS, HTTPS redirect, production secret strength, secure session cookie, and secure CSRF cookie. The LangChain deprecation warning also appears at application import.
- Important untested behavior remaining: registration email delivery/activation edge cases, staff permission granularity, upload validation/parser failures/cleanup, slug collisions, format endpoint method/cost, provider failures/retries, chunk fan-out, XSS behavior, concurrency/idempotency, PostgreSQL-specific behavior, and production deployment.

## Recommended target

Adopt **uv + `pyproject.toml` + Ruff + pytest/pytest-django**, incrementally in Phase 1.

Benefits:

- explicit project metadata and `requires-python`;
- direct runtime dependencies separated from a development group;
- deterministic cross-developer/CI resolution in committed `uv.lock`;
- one fast lint/format/import tool instead of overlapping Black/isort/flake8 stacks;
- concise fixtures/markers and Django test ergonomics while retaining existing `TestCase` tests;
- identical local and CI commands.

Compatibility risks:

- current pins are from a 2024 ecosystem snapshot and should not all be upgraded in one unexplained change;
- Django, django-registration, LangChain/OpenAI, PyMuPDF, Pillow, psycopg, and Python-version compatibility need focused verification;
- `psycopg2` and old `tiktoken` builds vary by platform/Python version;
- switching runner/config can hide differences if database settings and test discovery are changed simultaneously;
- deployment may still consume `requirements.txt`.

Recommended migration sequence:

1. Declare `requires-python = ">=3.12,<3.13"` initially, matching the verified baseline; widen only after CI evidence.
2. Identify actual direct runtime dependencies and add the missing configured dependency or remove it if confirmed unused (`django_extensions` appears unused and should likely be removed).
3. Create `pyproject.toml` without opportunistic major upgrades. Add a `dev` dependency group for pytest, pytest-django, Ruff, and only justified test tools.
4. Generate and commit `uv.lock`; run migrations/checks/tests under uv on PostgreSQL-compatible CI plus fast SQLite tests where appropriate.
5. Configure Ruff lint and format with a small rule set; apply formatting in a separate mechanical change to preserve reviewability.
6. Configure pytest and migrate tests gradually; Django's runner may coexist briefly.
7. Keep `requirements.txt` temporarily as a generated `uv export` artifact only if current deployment requires it. Document that it is generated and prevent hand editing.
8. Upgrade dependency families in separate, tested changes; run a vulnerability audit after the dependency source of truth is stable.

Recommended grouping:

- runtime: Django, django-registration, crispy integration, PostgreSQL driver, Gunicorn, Pillow, PDF/DOCX parsers, minimal OpenAI/LangChain packages actually used;
- development: pytest, pytest-django, Ruff, coverage if a reporting requirement exists, and a security audit tool when CI policy is defined;
- avoid retaining transitive packages as direct declarations unless application code imports or policy requires them.

Recommended CI commands after migration:

```text
uv sync --locked --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check --deploy --settings=<production-check-settings>
```

Use PostgreSQL for integration/model-policy tests that depend on PostgreSQL semantics. Fast isolated tests may use SQLite only when that difference is irrelevant.

# 12. Gap Analysis Against ResumeBot 2.0

| Vision capability/invariant | Current state | Gap |
| --- | --- | --- |
| Multi-user candidate platform | User-to-candidate ownership exists | No lifecycle, approval, isolation policy, or `/u/` public projection |
| Verified candidate facts are truth | One mutable resume text blob | No raw source, extraction review, structured facts, verification, versioning, or evidence |
| Candidate application | Basic authenticated edit/profile | No settings, document management, review workflow, privacy controls, preview entitlement, or analytics |
| Anonymous public profile | None; directory/chat require login | Need separate read-only public projection and publication policy |
| Verified lightweight recruiter AI access | Full Django account activation | Need expiring verified recruiter identity/grant scoped to AI operations |
| Platform administration | Django admin + staff interaction pages | No approval/publication/moderation/suspension/usage/cost controls |
| Cost governance | None | Need usage ledger, rate/quota/budget policy and circuit breaker |
| Domain-limited Candidate Agent | Prompt instruction only | Need pre-provider scope policy, tool restrictions, refusal behavior, evaluations |
| Prompt-injection resistance | Untrusted text interpolated directly | Need authorized retrieval, instruction/data separation, output grounding, privacy minimization |
| RAG/provenance | Full resume chunk fan-out | Need structured verified knowledge and evidence before retrieval/vector work |
| Tailored resume workflow | None | Correctly deferred until evidence, JD parsing, matching, planning, and validation exist |
| React/TypeScript | Server templates/jQuery | React may follow stable API/domain boundaries; not a prerequisite for security |
| Production AI observability | Print statements | Need typed operations, structured logs, usage/cost/failure/evidence records |
| Reproducible DX/CI | Manual pip snapshot, no CI | Need explicit Python, pyproject, uv lock, Ruff, pytest, and CI parity |

# 13. Proposed Target Architecture

Retain a modular Django monolith and PostgreSQL. Establish domain/application boundaries before extracting services or adding frontend frameworks.

```text
Candidate web app       Public /u/<slug>       Admin surface
(templates now,         (read-only public      (approval, moderation,
 React later)            projection)            usage/cost)
          \                    |                    /
           +--------- Django application --------+
                      | policies/services |
         identity ----+ profiles ----------+ conversations
         documents ---+ verified facts ----+ AI operations
                      |                    |
                 PostgreSQL           private object storage
                      |
             usage/quota/budget ledger
                      |
        authorized evidence + scoped operation
                      |
              provider adapter (OpenAI first)
```

Recommended rules:

- views/API serializers translate HTTP; they do not call providers or encode all policy;
- services orchestrate use cases; policy objects/querysets authorize server-side;
- provider adapters accept a typed, already-authorized operation and return structured usage metadata;
- verified facts and public projections are distinct from documents and model output;
- expensive operations create a durable operation/usage record and reserve budget before provider calls;
- public profile rendering remains available when the AI circuit breaker is open;
- DRF should be introduced when a React surface has a concrete endpoint need, not as a parallel rewrite;
- background processing and Redis/Celery should be introduced only after document workload/reliability requirements justify them;
- pgvector/RAG follows a retrieval evaluation proving structured/database queries alone are insufficient;
- LangGraph follows a real stateful, resumable multi-step workflow, likely tailored-resume generation, not basic chat.

# 14. Proposed Domain Model

## MUST HAVE SOON

These concepts are foundational, but should be introduced in small migrations rather than one speculative schema dump.

- **User**: authentication identity. Add explicit `email_verified_at` or a clearly documented equivalent rather than indefinitely overloading `is_active`.
- **CandidateProfile**: one owned professional profile with stable slug and approval/suspension state. Separate candidate contact fields from login identity.
- **PublicProfile**: candidate-authorized projection/publication state and field visibility. It may initially be a policy/configuration attached one-to-one rather than a duplicate data store.
- **CandidateDocument**: private source file metadata, type, checksum, size, processing state, uploader, timestamps, and retention/deletion state.
- **Structured professional facts**: start with the product's used facts (Experience, Education, Skill, Project) and add other types only when a workflow needs them. Every fact needs verification status and owner.
- **Evidence/SourceReference**: link a fact or generated claim to a document/page/chunk or manually entered source. Evidence is internal unless explicitly exposed.
- **Conversation and Message**: separate participant/candidate scope from ordered messages; retain legacy Interaction migration compatibility.
- **AIOperation/UsageEvent**: identity, candidate, operation, model/provider, reservation, input/output tokens, estimated/actual cost, timestamp, status, error category, and idempotency key. Keep financial/audit data out of message text.
- **RecruiterIdentity/AccessGrant**: verified email identity and an expiring, scoped permission to AI interaction. Avoid forcing a full candidate-style account for a one-time recruiter.
- **JobDescription** only when JD analysis enters implementation; store it as untrusted private input with owner, status, and retention policy.

Verification should be explicit per fact: extracted/unreviewed -> verified/corrected or rejected. Model-generated prose is never promoted automatically. Manual candidate entries may be marked candidate-attested with provenance distinct from document-verified evidence.

## POSSIBLE LATER

- GeneratedResume, ResumeVersion, ResumeEvidence, requirement/match/plan entities;
- Achievement, Certification, Language, ProfessionalPreference as explicit tables when UI/workflows use them;
- embedding/chunk records and pgvector indexes after a retrieval corpus/evaluation exists;
- tool-call and trace spans beyond the durable AI operation record;
- organization/recruiter-team tenancy, billing/subscription, and delegated candidate editors;
- background job model/task queue when synchronous processing no longer meets measured limits;
- generalized policy/entitlement products only if multiple plans or commercial requirements emerge.

Avoid a generic entity-attribute-value “fact” table that sacrifices constraints, and avoid creating every possible resume section before the first verification workflow.

# 15. Candidate and Recruiter Access Model

Do not store one lifecycle enum that conflates independent concerns. Recommended dimensions:

```text
User identity: registered -> email verified (or disabled)
Candidate approval: pending -> approved | rejected | suspended
Publication: draft -> pending review -> published | unpublished
AI entitlement: derived from verified identity + approval + suspension + quota/budget
```

“ACTIVE” should be an effective state derived from verified identity, approval, non-suspension, and any platform rules, not a second boolean with unclear meaning. Existing `activate` data must be inventoried and mapped explicitly before migration.

Candidates should gain inexpensive profile/document-form functionality after email verification. Expensive extraction, preview, generation, and public-agent operations require platform approval plus operation policy. Candidate-controlled “public” is a request/authorization input, not unilateral publication if moderation is required.

Anonymous recruiters may view the published public projection at `/u/<slug>`. Clicking AI interaction should start a lightweight email code/magic-link flow. A successful verification creates an expiring recruiter identity/access grant, ideally scoped to the candidate and operation class. The grant does not expose private fields and is still subject to per-recruiter, per-candidate, per-operation, and global limits.

Suspension must deny publication and paid operations before provider calls while preserving staff audit access and, where policy permits, candidate access to export/correct data. Authorization decisions should return reason codes suitable for audit and graceful UI without exposing sensitive status details to arbitrary visitors.

# 16. AI Safety and Trust Model

The central trust chain should be:

```text
private raw document/manual entry
  -> untrusted extraction proposal
  -> candidate review/correction
  -> verified/attested structured facts + evidence
  -> public/privacy authorization filter
  -> scoped retrieval
  -> grounded generation
  -> claim/evidence validation
  -> answer + internal provenance
```

Enforcement principles:

- application code, not an LLM, decides identity, authorization, visibility, quotas, budget, and tool permissions;
- prompts receive the minimum authorized facts, never the whole private profile by convenience;
- system instructions and tool schemas remain separate from delimited external documents/questions/JDs;
- retrieved text remains untrusted data even when stored internally;
- generated factual claims must be attributable to verified facts/evidence; unsupported requirements are explicitly reported as gaps;
- the model may select/rewrite/summarize but cannot mutate verified facts;
- high-risk structured operations use schema validation and deterministic post-checks;
- off-topic and abusive requests are rejected before expensive work when deterministic rules suffice; a bounded classifier may handle ambiguous domain scope;
- no general-purpose tools are exposed to the Candidate Agent;
- private contact, availability, preferences, and documents have field/evidence-level visibility rules;
- evaluations cover groundedness, refusal, privacy leakage, prompt injection, cross-candidate isolation, unsupported JD requirements, and cost/call counts.

Provenance should be stored internally even if the conversational answer stays natural. It supports audits, debugging, truthful tailored resumes, and regression evaluation.

# 17. Migration Strategy

Use a strangler-style evolution inside the Django monolith:

1. Secure and reproduce the current baseline: rotate secrets, explicit environment, executable tests, dependency/tooling source of truth, and CI.
2. Centralize current authorization/visibility queries and paid-operation entry points without changing URLs or templates unnecessarily.
3. Introduce explicit lifecycle/publication policy and deny unsafe access. Backfill from current booleans only after inspecting production data.
4. Create private document metadata/storage and preserve new source uploads. Continue reading legacy `Candidate.resume` while new extraction/review paths are built.
5. Add structured fact/evidence models incrementally and a candidate review workflow. Do not auto-promote existing model-formatted text to verified facts.
6. Add AI operation/usage records, reservations, quotas, budget, timeouts, and graceful disablement around the existing provider.
7. Replace chunk fan-out with a bounded grounded answer service. Initially this can query structured facts and legacy text deterministically; add semantic retrieval only after evaluation.
8. Introduce `/u/<slug>` as a distinct public projection; keep legacy chat routes redirected/compatible where safe.
9. Add DRF endpoints and React feature slices only when the candidate/public UX needs them; migrate page by page.
10. Migrate legacy Interactions into Conversation/Message or provide an adapter/read path, preserving audit history.
11. Implement JD/tailored resume stages after verified facts/evidence and cost policy are production-proven.

For schema changes, use expand/backfill/verify/switch/contract. Migrations should be reversible where practical, avoid long locks, preserve legacy reads during transition, and include row-count/data-quality checks. Never delete legacy resume/interaction data until backup, consent/retention, and migration verification are settled.

Tooling modernization should be a focused early Phase 1 task because the current clean install cannot start, but credential rotation and immediate access/cost safety are not postponed for formatting work.

# 18. AI-Assisted Development Architecture

Use five responsibility-based development roles for complex work. They need not run on every small task, and they are not product agents.

## Planner / Architect

- **Responsibility:** repository context, domain boundaries, invariants, migration sequence, acceptance criteria, ADR-worthy decisions, and cross-surface coordination.
- **Boundary:** proposes and validates direction; does not become the sole implementer or approve its own assumptions without evidence.
- **Use when:** work crosses domains, introduces data models/policies, or has meaningful alternatives.
- **Must not:** design speculative systems, introduce technology for portfolio value, or treat plans as runtime truth.

## Backend Engineer

- **Responsibility:** Django/DRF, models/migrations, policies/services, PostgreSQL, APIs, document/AI integrations, and backward-compatible data evolution.
- **Boundary:** enforces server-side business rules and provider boundaries; coordinates public contracts with frontend and tests.
- **Use when:** implementing a backend use case or migration.
- **Must not:** put authorization only in templates/serializers, call paid providers before policy, or invent future abstractions without a use case.

## Frontend Engineer

- **Responsibility:** accessible/responsive candidate, public, admin, and chat UX; TypeScript/React only when introduced; API integration and safe rendering.
- **Boundary:** presents server-authorized state and handles loading/error/disabled AI modes.
- **Use when:** changing user-facing interaction or establishing a concrete React slice.
- **Must not:** become the source of authorization, trust raw model HTML, or start a wholesale frontend rewrite.

## Quality Engineer

- **Responsibility:** characterization, unit/integration/API tests, migration tests, invariant regression, future AI evals, and review of test effectiveness.
- **Boundary:** tests behavior and risk, including provider call counts/absence, without mirroring implementation.
- **Use when:** before/alongside behavior changes and for release/regression review.
- **Must not:** chase superficial coverage percentages or mock away the security/cost boundary being tested.

## Security & Reliability Engineer

- **Responsibility:** identity, object authorization, multi-user isolation, uploads/PII/secrets, prompt injection, abuse, quotas/budgets, failure modes, auditability, and operational hardening.
- **Boundary:** threat-models and validates controls across backend/frontend/AI; implementation remains with the responsible engineer where appropriate.
- **Use when:** any public/private, paid AI, upload, deployment, or cross-tenant path changes.
- **Must not:** defer controls to prompts, demand infrastructure without a concrete threat/reliability need, or expand scope into unrelated compliance theater.

For small bounded changes, one engineer can use the relevant skills and review checklist. Use multiple roles when their decision boundaries materially differ, not to maximize agent count.

# 19. Recommended Skills

A small curated initial set:

| Skill | Purpose / users | Value and origin |
| --- | --- | --- |
| Repository assessment and incremental planning | Planner; all engineers before broad work | Custom lightweight procedure based on repository evidence, flow tracing, risk ranking, and acceptance criteria. Prevents rewrite-first behavior. |
| Django authorization and multi-tenant review | Backend + Security + Quality | Custom checklist grounded in Django's authorization/queryset practices and OWASP IDOR guidance. Tests ownership, visibility, staff scope, deny paths, and zero provider calls. |
| Django test and invariant design | Quality + Backend | Based on established Django/pytest practices; customize only project fixtures/invariants. Emphasizes behavior, database boundaries, migrations, and provider fakes. |
| LLM threat, grounding, and cost review | Security + Backend + Quality | Custom ResumeBot checklist informed by OWASP LLM threat categories and provider usage semantics. Covers untrusted data, evidence, scope, tokens, retries, quotas, budget, and eval cases. |
| Dependency/tooling modernization | Backend/Quality/Planner | Procedure based on official uv, Python packaging, Ruff, and pytest guidance. Separates direct dependencies, lock verification, platform testing, and mechanical formatting. |
| ADR and engineering documentation | Planner + decision owner | Use a small established ADR template adapted to Context/Decision/Alternatives/Consequences/Trade-offs. Only invoke for accepted consequential decisions. |
| Regression/release review | Quality + Security | Custom final checklist covering tests, migrations, docs, secrets, permissions, paid-call ordering, dependency lock, and rollback. |

Do not install external skills during Phase 0. Review any external skill's prompts, scripts, permissions, network behavior, and assumptions before adoption. CI validation is a step within tooling/release skills, not a separate agent. Documentation updates are a reusable procedure, not a full-time agent.

# 20. Public vs Private Repository Strategy

Public, versioned engineering artifacts should include concise product/architecture documentation, setup/deployment contracts, tests, migrations, security/threat summaries appropriate for disclosure, ADRs for accepted decisions, `AGENTS.md` project conventions, `pyproject.toml`, `uv.lock`, generated compatibility requirements if needed, and CI.

Private AI-working artifacts belong under `.local/`, which Phase 0 added to `.gitignore`. Create subdirectories (`learning/`, `linkedin/`, `prompts/`, `sessions/`, `research/`, `scratch/`) only when used. None may be a runtime dependency or the sole copy of a project decision.

An `AGENTS.md` should be created in Phase 1 after tooling, test, security, and change-scope conventions are accepted. It should be short, actionable, and public: commands, boundaries, invariants, directory guidance, and definition of done. It should not contain transcripts or model-specific scratch prompts.

Introduce `docs/adr/` when the first decision is accepted. Likely early candidates are verified facts as source of truth, access/cost policy before providers, and the tooling source of truth. Do not pre-create empty/speculative ADRs.

Private learning notes and LinkedIn drafts should be rare and evidence-based. Public docs capture the durable engineering decision; `.local/learning` captures personal reflection; `.local/linkedin` may derive a first-person draft only from work that actually occurred. Existing committed CV fixtures should be reviewed separately because private professional data is not an engineering artifact merely because it is JSON.

# 21. Proposed Phase 1

The sequence begins with outstanding credential action, then makes changes reproducible, then enforces access and paid-operation boundaries. Each task should be a separately reviewable change. Phase 1 must not silently expand into RAG, React, or tailored-resume implementation.

## Task 1: Complete production secret and configuration remediation

**PURPOSE**

Rotate compromised values and make production fail safely instead of relying on tracked host settings.

**FILES / AREAS LIKELY AFFECTED**

`mychatbot/settings.py`, `mychatbot/local_settings.py` or replacement environment-specific settings, README/development docs, deployment secret configuration; operational database/session/email configuration.

**EXPECTED BEHAVIOR**

Local development has documented non-secret defaults. Production requires injected secrets, defaults to debug off, and starts only with valid required configuration. Deployed database/Django credentials are rotated and relevant sessions/tokens invalidated.

**TESTS REQUIRED**

Settings tests for missing production secrets, `manage.py check --deploy`, startup smoke check with production-shaped environment, and confirmation that secret scanning finds no real values in the current tree.

**SECURITY CONSIDERATIONS**

Coordinate rotation to avoid outage; do not print secret values; treat Git history and old clones as compromised; decide whether history rewriting is operationally worthwhile after rotation.

**ACCEPTANCE CRITERIA**

- deployed DB and Django secrets are rotated;
- no production secret exists in tracked files/current diff;
- debug defaults off and production missing-secret behavior is fail-closed;
- environment variables and rotation/runbook are documented without values.

**LEARNING OBJECTIVES**

Secret lifecycle, configuration boundaries, incident containment versus Git history rewriting, deployment-safe rotation, and Django production hardening.

## Task 2: Establish reproducible Python tooling and CI-ready commands

**PURPOSE**

Make clean setup, tests, lint, and dependency resolution deterministic before broader refactoring.

**FILES / AREAS LIKELY AFFECTED**

New `pyproject.toml`, `uv.lock`, optional `.python-version`, generated/temporary `requirements.txt`, README/development docs, test settings, minimal Ruff/pytest configuration.

**EXPECTED BEHAVIOR**

Python 3.12 is explicit; `uv sync --locked --group dev` installs a working environment; unused `django_extensions` is removed or correctly declared; pytest discovers the characterization suite; Ruff has one agreed lint/format configuration. Application behavior does not change.

**TESTS REQUIRED**

Clean-environment sync, Django checks, six existing tests, import/startup smoke test, lock reproducibility, and a Linux/PostgreSQL CI install check.

**SECURITY CONSIDERATIONS**

Review direct dependencies and vulnerability posture; do not combine the source-of-truth migration with uncontrolled major upgrades; ensure exported requirements cannot drift.

**ACCEPTANCE CRITERIA**

- explicit `requires-python` and runtime/dev groups;
- committed `uv.lock`;
- documented local commands work from clean checkout;
- Ruff check/format-check and pytest pass;
- any retained requirements file is generated and documented.

**LEARNING OBJECTIVES**

Python packaging metadata, direct versus transitive dependencies, cross-platform locks, reproducible environments, tool consolidation, and reviewable mechanical changes.

## Task 3: Expand security-focused characterization and policy tests

**PURPOSE**

Turn the most important current and target access/cost invariants into executable constraints before changing behavior.

**FILES / AREAS LIKELY AFFECTED**

`chatbot/tests.py` split into focused test modules/fixtures as justified; provider fakes; test factories only if repetition warrants them.

**EXPECTED BEHAVIOR**

Tests describe owner edit isolation, recruiter history isolation, anonymous/login behavior, public/private/inactive access, staff access, format method semantics, upload cleanup, XSS-safe rendering, and provider call counts/absence. Tests for current unsafe behavior are deliberately updated in the same change that fixes it.

**TESTS REQUIRED**

This task is tests; include positive and negative cases and database/provider boundaries. At least one invariant must assert an unauthorized or over-budget request invokes no provider fake.

**SECURITY CONSIDERATIONS**

Avoid fixtures with real PII/API keys. Do not mock away authorization. Ensure error messages do not reveal candidate existence where policy requires concealment.

**ACCEPTANCE CRITERIA**

- critical owner/isolation/paid-call invariants are named and pass;
- provider fake records exact call count;
- current intentional behavior versus desired changed behavior is clear;
- tests are fast and hermetic, with PostgreSQL coverage marked where needed.

**LEARNING OBJECTIVES**

Characterization versus specification tests, invariant-driven testing, negative authorization tests, test doubles at paid external boundaries, and security regression design.

## Task 4: Define and enforce candidate lifecycle/publication policy

**PURPOSE**

Remove ambiguous boolean behavior and ensure private, unpublished, or suspended candidates cannot be discovered or queried without an explicit authorized preview.

**FILES / AREAS LIKELY AFFECTED**

Candidate model and migration, policy/query service, candidate/chat/directory/admin views/templates, data backfill command or migration, tests, one accepted ADR if owner confirms the lifecycle dimensions.

**EXPECTED BEHAVIOR**

Email verification, candidate approval/suspension, and publication are separate. Directory/public querysets include only publishable profiles. Chat checks candidate and operation policy. Candidate owner preview is explicit. Existing data is mapped safely; `activate` is removed only after verified migration.

**TESTS REQUIRED**

State transition matrix; owner, recruiter, anonymous, staff cases; direct slug access; suspended/unpublished deny behavior; migration/backfill tests; “denied means no provider call.”

**SECURITY CONSIDERATIONS**

Default-deny unknown states; prevent candidate self-approval; avoid existence leaks; audit staff transitions; preserve access needed for candidate correction/export.

**ACCEPTANCE CRITERIA**

- one documented server-side policy controls discovery, public display, preview, and AI eligibility inputs;
- private/unpublished/suspended direct access is denied as specified;
- platform approval cannot be changed through candidate form;
- legacy rows are accounted for and reversible rollback is documented.

**LEARNING OBJECTIVES**

State modeling versus boolean flags, policy centralization, object authorization, safe data migrations, derived state, and multi-user isolation.

## Task 5: Harden chat/UI and state-changing HTTP semantics

**PURPOSE**

Remove immediate browser/request vulnerabilities while retaining the server-rendered product.

**FILES / AREAS LIKELY AFFECTED**

Chat/profile templates and JavaScript/static files, chat and format views/forms/URLs, security settings, tests.

**EXPECTED BEHAVIOR**

Questions and model responses render as text, not executable HTML. Paid/state-changing actions require POST + CSRF, have input length bounds, disable duplicate submissions, and show sanitized timeout/unavailable errors. External links are safe.

**TESTS REQUIRED**

Malicious HTML/model-response rendering, CSRF/method rejection, question bounds, duplicate/idempotency behavior where implemented, graceful AJAX failures, and normal chat regression.

**SECURITY CONSIDERATIONS**

Treat model output as attacker-controlled; use context-correct escaping rather than blacklists; introduce CSP only after removing incompatible inline patterns and measuring deployment impact.

**ACCEPTANCE CRITERIA**

- no chat path inserts untrusted strings with HTML interpretation;
- GET cannot invoke formatting/provider state changes;
- input bounds and safe error contract are enforced server-side;
- normal interaction remains accessible and responsive.

**LEARNING OBJECTIVES**

DOM XSS contexts, CSRF versus HTTP method safety, untrusted LLM output, idempotency, graceful external-service UX, and defense in depth.

## Task 6: Establish private document and verified-source boundaries

**PURPOSE**

Preserve source truth and safely process future uploads without immediately building full extraction/RAG.

**FILES / AREAS LIKELY AFFECTED**

New minimal `CandidateDocument` model/migration, storage configuration/service, form validators, parser service, candidate upload/review UI, tests, retention documentation.

**EXPECTED BEHAVIOR**

New resumes are stored privately with generated identifiers and metadata; allowed content is size/type validated; extraction is a proposal/status, not an overwrite of verified facts; cleanup and sanitized failure states are deterministic; no resume contents are logged. Legacy `Candidate.resume` remains readable during migration.

**TESTS REQUIRED**

Ownership/access, size and signature/type rejection, parser failure cleanup, filename/path handling, no public media URL, status transitions, legacy compatibility, and representative PDF/DOCX fixtures without real PII.

**SECURITY CONSIDERATIONS**

Parser/decompression limits, malware/storage policy, private object authorization, log redaction, retention/deletion, and asynchronous processing decision based on measured workload.

**ACCEPTANCE CRITERIA**

- uploaded documents are not publicly addressable by storage URL;
- source file and extraction proposal are distinguishable;
- parser failures do not expose paths/content or leave unmanaged files;
- existing resume data is preserved and migration plan is explicit.

**LEARNING OBJECTIVES**

Untrusted file boundaries, secure storage, provenance, stateful processing, privacy/retention, expand-and-migrate design, and why extraction output is not truth.

## Task 7: Introduce a controlled AI operation gateway and usage ledger

**PURPOSE**

Put every paid call behind one enforceable policy and make cost/failure observable before adding new AI features.

**FILES / AREAS LIKELY AFFECTED**

AI application service/provider adapter, `AIOperation` or `UsageEvent` model/migration, policy/quota/budget configuration, chat/format call sites, admin views, tests.

**EXPECTED BEHAVIOR**

Call sites submit typed operations. The gateway checks verified identity, candidate policy, scope, rate/quota, and project budget before invoking OpenAI. It sets timeouts/token bounds, records success/failure and usage, supports idempotency, and fails gracefully when AI is disabled. Profiles remain available.

**TESTS REQUIRED**

Authorized success, every denial stage with zero provider calls, concurrent budget reservation, idempotent replay, provider timeout/failure, usage reconciliation, global circuit breaker, and PII-safe audit fields.

**SECURITY CONSIDERATIONS**

Transactions/concurrency around budget, configuration tamper boundaries, model/operation allowlists, sanitized provider errors, least-data prompts, and no quota trust in frontend headers.

**ACCEPTANCE CRITERIA**

- no view calls a paid provider directly;
- usage stores identity, candidate, operation, model, tokens/cost estimate, time, and status;
- configurable limits and global daily/monthly breaker deny before calls;
- disabled/exhausted AI has a stable non-500 response and non-AI pages work.

**LEARNING OBJECTIVES**

Provider abstraction at a real boundary, cost as domain state, reservations/concurrency, rate versus quota versus budget, observability, failure accounting, and production AI circuit breakers.

## Task 8: Align CI and deployment validation

**PURPOSE**

Make the baseline and security invariants mandatory on every change and verify production-shaped configuration.

**FILES / AREAS LIKELY AFFECTED**

CI workflow, development/deployment docs, optional PostgreSQL service configuration, health/startup checks, generated dependency exports.

**EXPECTED BEHAVIOR**

CI uses locked dependencies and explicit Python, runs Ruff, pytest, migration drift, and deployment checks; PostgreSQL integration cases run against PostgreSQL. Deployment consumes the same resolved dependencies and has a rollback/checklist.

**TESTS REQUIRED**

The pipeline commands themselves, clean checkout, PostgreSQL migration/smoke test, production settings validation with placeholder secrets, and artifact/export drift check.

**SECURITY CONSIDERATIONS**

Least-privilege CI tokens, no production secrets or PII in CI, pinned actions, dependency provenance, safe logs, and protected required checks.

**ACCEPTANCE CRITERIA**

- clean CI passes only through `uv sync --locked`;
- lint, format, tests, migration drift, and deployment checks are required;
- local docs use the same commands;
- failure output contains no secret/PII and deployment rollback is documented.

**LEARNING OBJECTIVES**

CI/CD parity, reproducible builds, database service testing, supply-chain controls, deployment checks, rollback thinking, and turning architecture invariants into delivery gates.

# 22. Open Questions / Decisions

Only the following require owner/operational input; the rest have recommendations above.

## 1. Are the exposed credentials current anywhere, and who can rotate them?

**Recommended option:** assume both committed values were used, rotate the PostgreSQL password and Django secret now, invalidate sessions/activation/reset tokens affected by the Django rotation, and audit logs. Decide on Git history rewriting only after rotation because rewriting does not revoke secrets and disrupts clones.

**Alternative/trade-off:** if deployment evidence proves a value was never used, rotation has less operational urgency, but the proof and secret handling still need documentation.

## 2. How should existing `activate`, `public_profile`, null-owner candidates, and production rows map to the new lifecycle?

**Recommended option:** inspect a sanitized production data inventory, default ambiguous rows to non-public/pending, explicitly assign or mark legacy/system ownership, and require admin review before publication/AI enablement.

**Alternative/trade-off:** treating current true flags as approved preserves access but may publish or fund profiles that were never reviewed. Blanket pending is safer but can temporarily hide intended profiles.

## 3. Which candidate contact fields are public by default?

**Recommended option:** public profile defaults to no direct email/phone; show candidate-approved professional links and offer a controlled contact path. Each contact field has an explicit visibility setting, and candidate login email is never implicitly public.

**Alternative/trade-off:** publishing a candidate contact email is simpler for a portfolio, but creates scraping/spam/privacy risk and couples verified login identity to public contact.

## 4. May the three committed CV datasets remain public?

**Recommended option:** confirm informed consent and fixture purpose for every person; replace real PII with synthetic test data if public retention is not necessary. Keep real documents in private storage, never Git.

**Alternative/trade-off:** consented portfolio data may remain, but Git permanence, forks, and inability to honor deletion cleanly should be accepted explicitly.

## 5. What is the initial operational approval model?

**Recommended option:** manual Django-admin approval/publication for the portfolio phase, with audited state changes. It is understandable, cheap, and does not justify a custom admin workflow yet.

**Alternative/trade-off:** automatic approval improves onboarding but exposes paid AI and moderation risk; a custom review surface improves UX but is premature before policy stabilizes.

## 6. Is Python 3.12 acceptable as the initial supported runtime?

**Recommended option:** declare Python 3.12 only for the first tooling migration because Phase 0 verified the exact requirements there and observed a Python 3.14 build failure. Add newer versions only after dependency upgrades and CI evidence.

**Alternative/trade-off:** supporting multiple versions immediately broadens portability but increases compatibility and CI work before the baseline is stable.
