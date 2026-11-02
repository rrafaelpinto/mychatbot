# Email-code onboarding and manual candidate approval

Status: Accepted

## Decision

Use email one-time codes for candidate and recruiter registration and subsequent React sign-in. Keep short-lived access JWTs and rotating HttpOnly refresh cookies. Create candidate profiles only after email verification, then require superuser approval before any candidate application access. Recruiters need email verification without manual approval. A normal account has one role; superuser authority is independent and grants both application areas and exclusive access to Django Admin.

Keep candidate approval, profile publication, fact verification/publication and AI entitlement independent. Reuse existing file validation, private storage, extraction and paid-operation policies.

## Alternatives

Password registration and password recovery add credentials and flows that are unnecessary for this email-based product. Automatic candidate approval would remove the explicit operator decision required for public onboarding. Django Admin as a candidate workspace would expose administrative navigation and fail to provide a coherent React journey.

## Consequences

Transactional email delivery is a prerequisite for normal sign-in. Expiring codes require bounded attempts, resend protection, single-use consumption and transactional concurrency controls. Pending and suspended accounts must be denied on the server, including pre-existing tokens and legacy routes. Existing users require a normalized, unique email and verification before application access. Superusers retain separate administrative authentication and remain subject to paid-operation and upload constraints.
