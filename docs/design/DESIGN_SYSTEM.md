# ResumeBot visual identity: proposed design system

**Status:** Proposed for visual review in Phase 4, issue #31. Not yet approved
for the React implementation. This document describes a **standalone
fictional prototype**, not an active product feature or deployed frontend.

## Direction and rationale

**Professional Minimal:** warm neutral canvas, deep ink typography and
restrained evergreen accents. Editorial display typography is paired with
compact, legible UI text. The interface should communicate professional
credibility and candidate ownership before emphasizing the AI assistant.

Restraint is intentional. No abstract robot illustrations, artificial
candidate portraits, unsupported endorsements or claims that every answer
is correct. The product differentiator is **approved professional evidence**,
not the fact that a model generated prose.

The wordmark is lowercase "resumebot." with a check-inside-a-document
monogram. Its current SVG is an inline prototype asset. Refine as an
independent vector asset during React implementation if approved. Avoid
brand trademarks or copyrighted illustration assets.

### Information architecture

1. **Overview:** differentiated value proposition, data ownership
   safeguards, three-step introduction and clear call to explore a profile.
2. **Public profile:** profile summary first; explicit verified/public
   professional facts; restrained secondary information and permissioned
   contact surface. Never imply unsupported resume metrics.
3. **Candidate Agent:** evidence-led sample conversation, expandable
   supporting facts, suggested prompts, visible limits and clear failures.
   The React application will use actual API contracts only after approval.

The prototype is composed of static HTML, CSS and plain JavaScript to
enable review without creating a second application or changing existing
Django/DRF endpoints. Its fictional candidate **Alex Morgan** is not
a real candidate or an actual ResumeBot record.

## Token system

All colors and spacing are declared in
[`prototypes/visual/styles.css`](../../prototypes/visual/styles.css).
These tokens can later be mapped to Tailwind/shadcn and CSS variables.
They are *not yet* backend template styles.

| Token | Light | Dark | Role |
| --- | --- | --- | --- |
| `--canvas` | `#faf9f6` | `#101c20` | Main background |
| `--surface` | `#ffffff` | `#17272b` | Cards and conversation |
| `--surface-alt` | `#f3f2ee` | `#203338` | Grouped input / bubbles |
| `--ink` | `#182b31` | `#f3f4ef` | Primary readable content |
| `--ink-soft` | `#46575a` | `#ccdad8` | Secondary content |
| `--ink-muted` | `#637174` | `#a9c2bf` | Metadata / labels |
| `--brand` | `#176b5e` | `#83d8be` | Trust cue / outline / accent |
| `--brand-quiet` | `#e2f0e9` | `#1d4841` | Verified-fact surfaces |
| `--danger` | `#a52a39` | `#ffb6b6` | Access / provider failures |
| `--warning` | `#80551a` | `#ffce8d` | Quota / no evidence |
| `--line` | `#e3e4df` | `#32484a` | Dividers |

**Typography:** system Inter/Aptos-style sans serif for controls and body
content; Iowan Old Style/Baskerville/Georgia fallback for editorial accents.
No hosted font files or third-party network requests. Display headings are
responsive, with a maximum ~76px; body text primarily ~12–17px in the
prototype, subject to accessibility review before release.

**Spacing:** 4px base: 4/8/12/16/24/32/48/64px.
**Corners:** 10px controls, 16px components, 24px feature containers,
32px hero art. **Elevation:** light shadows only on illustrative layers
and the chat surface. **Width:** 1216px content cap, with responsive
24px/17px side gutters.

**Layout breakpoints:** 1060px for compressed desktop navigation, 850px
for stacked cards and agent sidebar, 620px for mobile layouts. Layout
must be usable from 320px without horizontal scrolling.

## Component patterns

| Pattern | Interaction | Accessibility contract |
| --- | --- | --- |
| Header navigation | Hash-routed review pages | Proper links and `aria-current` |
| Primary / secondary actions | Navigate to sample profile/agent | Focus visible; text label |
| Evidence details | Disclosure for approved fact list | Native `details/summary` |
| Candidate preview | Fictional initial badge | Decorative initials excluded from AT |
| Prompt suggestions | Populate message composer | Focus moves to the field |
| Agent input | Submit predetermined sample answer | Semantic form and visible label |
| Usage counter | Show 3 fictional questions remaining | Text, not color-only |
| State selector | Switch sample Agent UI states | Associated select label |
| Theme switch | Toggle theme per view session | Descriptive label and pressed state |

No role/permission state is inferred from browser state. All actual
authentication, candidate access, CSRF, Turnstile, session quota, budget,
citation validation, profile privacy and AI safety policies remain the
responsibility of Django.

## Conversation and exceptional states

**Ready:** short explainer, 3 suggested questions, input, evidence list
disclosed on request. **Loading:** visibly pending and composer disabled.
**No facts:** decline to fabricate; explain the candidate must approve
information. **Quota reached:** disable further submissions and explain
the limit. **Access denied:** avoid exposing whether private facts exist.
**Agent unavailable:** report a temporary error with a path back to the
public profile. **Unsupported request:** explicit grounded refusal, no
fake evidence. **Evidence withdrawn (React requirement):** preserve the
backend's existing historical-answer redaction when evidence is revoked.

The sample replies are **hardcoded fictional text**, not LLM output.
The 3-question sample counter is a UX demonstration only and does not
replace backend quotas. **No API key, JWT, cookies, external requests or
tracking** appear in the prototype.

## Accessibility and responsive acceptance

- WCAG 2.2 AA as target before React publication.
- Text/non-text contrast should be checked against each rendered
  background in **both** themes. Status is conveyed by text and
  position, not solely color.
- Semantic landmarks, skip navigation, visible keyboard focus, sensible
  tab order, native controls and no keyboard traps.
- Mobile touch targets should be at least 44 CSS px in the eventual React
  implementation; this prototype flags compact metadata controls for review.
- Content must not overflow horizontally at 320, 390, 768 or 1440px.
- Animation is nonessential and reduced under `prefers-reduced-motion`.
- Message evidence remains expandable and readable by assistive technology.
- UI states must not depend on fake provider success or network availability.

## Review and handoff

1. Open `prototypes/visual/index.html` in a browser, or use
   `python3 -m http.server 4173 --directory prototypes/visual`.
2. Review Overview, Sample profile and Candidate Agent in desktop and
   mobile widths, including dark mode and the six UI state options.
3. Run the visual browser tests, inspect their screenshots/artifacts and
   record any contrast or keyboard failures before approving the design.
4. Only **after** explicit visual approval, implement
   [Phase 4 React frontend issue #32](https://github.com/rrafaelpinto/mychatbot/issues/32),
   using a separate `frontend/` build and standalone deployment.
5. Reuse the versioned DRF API as data source. Replace all hardcoded
   fictional profile/answer content and mock states with typed API data,
   protecting source documents, consent flags and evidence authorization.

No profile, API, authentication, production style or deployment changes
are included in this design PR.
