---
name: ui-ux-review
description: Review user-facing changes for usability, accessibility, responsive behavior, consistency and browser-verified evidence. Use when UI structure, styling, navigation, forms or interactions change.
---

# UI/UX review

Review the affected user journey and the actual rendered interface, not just the source diff. The repository's `AGENTS.md`, design system, accessibility policy and application-specific workflow are authoritative for product behavior, stack and commands.

## Workflow

1. **Scope:** Identify the user, route, task, primary action, starting state, previous/next steps, and the change under review. Read the smallest relevant project conventions and components.
2. **Diagnose:** Inspect information hierarchy, semantics, keyboard navigation, focus, responsive layout, feedback and error states. Separate observable defects from subjective preferences. Report actionable findings with severity.
3. **Decide:** Prefer the smallest coherent change. Reuse existing components and tokens. Never introduce architecture changes, relax access control or shift business rules into the browser as part of a visual review.
4. **Validate:** Execute the repository's prescribed build, tests and browser-based checks. Inspect actual screenshots for applicable desktop/mobile viewports. Validate keyboard interaction, zoom, overflow, contrast and accessible states. Do not infer visual approval from compilation or test success alone.
5. **Refine:** Repeat capture, inspection and correction for at most three cycles unless explicitly authorized otherwise. Escalate remaining limitations rather than iterating silently.

## Review checklist

- Purpose and primary action remain clear across the relevant journey.
- Headings, landmarks, labels, links and buttons are semantic and operable.
- Focus is visible; tab order, error announcements and interactive states are usable.
- Mobile widths, long text, loading, empty, error, disabled and success states are handled when applicable.
- Design tokens, spacing, typography and navigation remain consistent.
- Contrast and meaning do not depend solely on color, hover or motion.
- Changes preserve privacy, authorization and application business invariants.

## Handoff

Report the pages and states reviewed; viewport sizes; executed commands and outcomes; screenshot locations actually inspected; findings and changes; refinement count; and any blocked or incomplete validation.

Do not claim browser or screenshot inspection without inspecting the rendered artifact. If browser access is unavailable, report the gap explicitly.

## Boundaries

This skill does not define framework-specific build commands, product copy, responsive breakpoints, screenshot fixtures, component architecture, or a project's risk and approval policy. Obtain them from local project instructions. For external design guidance, use only installed and approved companion skills.
