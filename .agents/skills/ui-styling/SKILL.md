---
name: ui-styling
description: Implement responsive ResumeBot UI styling using existing CSS variables, Tailwind Vite support, React semantics, and accessible interaction patterns.
---

# ResumeBot UI styling

Use the project's existing React/TypeScript components and semantic CSS variables in `frontend/src/styles.css`. Tailwind is available, but new design libraries and shadcn components are not required for routine improvements.

- Prefer the existing `--canvas`, `--surface`, `--ink`, `--brand`, `--line`, spacing, and radius tokens rather than isolated literal colors.
- Build a clear primary CTA, calm surfaces, professional typography, and consistent density across Home, Public Profile, Candidate Agent, and Owner Workspace.
- Avoid decorative emoji as navigation controls; ensure visible textual actions and accessible labels.
- Preserve light/dark contrast, keyboard focus, form labels, actual disabled states, and text wrapping at mobile widths.
- Do not claim a visual change is complete solely because TypeScript or CSS compiles. Run Playwright and inspect screenshots as required by `ui-ux-review`.
