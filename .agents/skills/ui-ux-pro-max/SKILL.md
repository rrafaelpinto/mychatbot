---
name: ui-ux-pro-max
description: Focused UI/UX design guidance for ResumeBot using the relevant design intelligence and accessibility principles adopted from Talent Pool.
---

# ResumeBot UI/UX design intelligence

This is a scoped adaptation for the React frontend, not a copy of the external UI/UX Pro Max searchable dataset. The canonical design constraints are `docs/design/DESIGN_SYSTEM.md`.

For public pages, prefer an **editorial engineering portfolio** with a short, factual introduction, prominent profile navigation, a single primary CTA, and a useful conversation surface. Avoid artificial testimonials, speculative metrics, decorative robot illustrations, and large sections explaining the technology before the candidate's experience is visible.

## Targeted review patterns

- **Recruiter discovery:** Candidate identity, professional specialty, and a direct path to questions should be visible on the first screen. Avoid long introductory marketing.
- **Information hierarchy:** Use a readable 16px base, concise copy, limited line length, grouped facts, one dominant action per section, and restrained typographic contrast.
- **Conversation:** Distinguish user/assistant turns; show remaining usage, disabled/verification states, retry guidance, and expandable evidence. Suggestions should populate the real input and preserve keyboard access.
- **Mobile:** Start at 320px, avoid fixed-width columns and clipped scroll surfaces, preserve the composer and skip navigation, and ensure controls do not require hover.
- **Accessibility:** Target WCAG 2.2 AA, visible focus, text contrast at least 4.5:1, semantic headings and landmarks, accessible names on icon-only controls, and reduced-motion support.
- **React performance:** Preserve API state ownership, avoid redundant requests, and do not introduce UI dependencies for problems solvable with existing components.

Document why a recommendation is applicable rather than applying unrelated catalog examples. For broader catalog searches, the original `ui-ux-pro-max` skill remains available in Talent Pool; its scripts and datasets are not bundled here.
