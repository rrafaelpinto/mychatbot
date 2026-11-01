---
name: ui-ux-review
description: Review ResumeBot public and owner interfaces for recruiter usability, responsive behavior, accessibility, clarity, and visual consistency.
---

# ResumeBot UI/UX review

Apply this skill whenever a task changes React components, CSS, public navigation, or browser interaction. Follow `docs/engineering/UI_UX_WORKFLOW.md` and `docs/design/DESIGN_SYSTEM.md`.

## Workflow

1. Identify the audience, primary task, current route, data state, and next action. Recruiters should be able to find professional experience and start a grounded conversation immediately.
2. Report actionable issues by severity, distinguishing observed defects from aesthetic preferences. Consult `ui-ux-pro-max` for pattern decisions and `ui-styling` for component-level styling.
3. Implement the smallest coherent change using existing tokens and React components. Keep Django responsible for authorization, publication, policy, source evidence, and usage limits.
4. Run `npm --prefix frontend run build`, `npm --prefix frontend test`, and `npm --prefix frontend run test:e2e` when dependencies are present. Capture desktop and mobile screenshots at 1440 and 390px widths and inspect the rendered files before claiming visual approval.
5. Limit capture/inspection/refinement to three cycles. Report missing browser access or incomplete reviews explicitly.

## Acceptance checklist

- Main action is understandable on first view and profile details appear before product marketing.
- Headings, landmarks, links, controls, and form labels are semantic; focus is visible and order is predictable.
- No horizontal overflow at 320/390/768/1440px; interactive targets aim for at least 44px on touch screens.
- Guest disabled, loading, quota, Turnstile, error, and authorized states remain usable and accurately described.
- Candidate Agent responses stay first person; facts remain evidence-backed and private/unpublished data is never exposed.
- Both color themes have usable contrast; reduced motion preferences are respected.
- Playwright test coverage exercises public flows, and README images show the tested React UI, not an unrelated visual prototype.

Never call a change visually validated without opening the captured image.
