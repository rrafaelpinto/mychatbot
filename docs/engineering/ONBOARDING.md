# Public account onboarding

The React application owns candidate and recruiter registration and email-code sign-in. Public registration is controlled by `PUBLIC_REGISTRATION_ENABLED`; existing accounts can still request a sign-in code when registration is disabled.

## Account lifecycle

1. A visitor provides a name, email and one role: candidate or recruiter.
2. A six-digit, single-use code validates email ownership. Codes expire after ten minutes, allow five verification attempts, and cannot be resent within sixty seconds. Only an HMAC digest is stored. Public authentication endpoints enforce CSRF and request throttles.
3. Successful verification creates a user with an unusable password. A candidate also receives a private draft profile with `pending_approval` status. Recruiters can immediately explore public profiles and use authenticated chat under existing policies.
4. Pending candidates see only their status and sign-out controls. API and legacy application requests are blocked server-side except authentication and their own account status.
5. A superuser opens **Candidate profiles** in `/admin/`, filters pending candidates and runs **Approve selected candidate accounts**. Only active users with verified email are approved. Approval does not publish the profile or grant a larger AI allowance.
6. Approved candidates upload PDF/DOCX resumes, review processing results, explicitly request fact extraction, edit and approve suggestions, choose public facts and publish their profile. Editing a fact resets verification and withdraws it from public use.

Registration cannot change an existing account's role. Login uses the same email-code flow. There are no candidate/recruiter password or password-reset screens. The separate Django Admin retains superuser password authentication; the React application does not reuse that session as an email-code login.

## Permissions

| Account | Public content | Recruiter chat | Own candidate workspace | Django Admin |
| --- | --- | --- | --- | --- |
| Anonymous | Published profiles | Existing optional guest policy | No | No |
| Pending/unverified/suspended candidate | Status only while authenticated | No | No | No |
| Approved candidate | Yes | Existing authenticated policy | Yes | No |
| Verified recruiter | Yes | Existing authenticated policy | No | No |
| Active superuser | Yes | Existing authenticated policy | Yes | Yes |

Superuser privileges do not bypass upload validation, feature flags, AI quotas or project budgets. The React workspace always addresses the current user's profile. Cross-user administration belongs in Django Admin. Staff membership alone never grants Admin access.

## API

| Endpoint | Behavior |
| --- | --- |
| `POST /api/v1/auth/code/request/` | Request login code, or registration with `name` and `role` |
| `POST /api/v1/auth/code/verify/` | Consume email/code and issue the existing JWT access/refresh credentials |
| `GET /api/v1/me/` | Account role, access status and safe UI capabilities |
| `GET/POST/PATCH /api/v1/me/profile/` | Read/update own profile; creation supports a superuser's first profile |
| `POST /api/v1/me/profile/publication/` | Explicit profile publication or withdrawal |
| `GET/POST /api/v1/me/documents/` | Paginated metadata and multipart `document` upload |
| `GET /api/v1/me/documents/{id}/` | Own document metadata and processing/extraction states |
| `POST /api/v1/me/documents/{id}/extract/` | Explicit, bounded AI fact extraction |
| `PATCH /api/v1/me/facts/{id}/` | Audited fact edit with optimistic version check |
| `POST /api/v1/me/facts/{id}/review/` | Existing approve/reject/publish/withdraw decisions |

Document content, storage paths and extracted text are never returned by these endpoints. Upload processing remains synchronous for the small deployment; failure preserves the profile and records a failed document. Extraction remains separate, subject to existing policies and idempotent completed-run handling. Replacing a resume creates a new source and never silently replaces existing approved facts.

## Operations and migration

Configure a working SMTP backend, sender and credentials before enabling public registration. Development defaults print codes to the backend console. Configure `FRONTEND_URL` for redirects from retired Django account/profile creation URLs. The React deployment still requires correct CORS/CSRF origins and secure refresh-cookie settings.

The account-access backfill preserves existing candidate approval/publication states and assigns other existing users the recruiter role. It normalizes email addresses and stops if duplicate non-empty emails exist; reconcile those accounts before applying the migration. Existing accounts must verify email on their next code sign-in. Accounts without an email need an administrator to set a unique, reachable email before code sign-in. Newly created superusers can use their email to sign in to React independently of Admin.

Password authentication through the legacy token endpoint is restricted to active superusers. Legacy public password and registration pages redirect to React and reject mutations. The former Django profile creation/upload endpoint rejects POST requests.

Production activation requires SMTP delivery verification, persistent private storage, explicit feature flags and the existing AI budget configuration. No new free allowance, background queue, or exemption from cost controls is introduced.
