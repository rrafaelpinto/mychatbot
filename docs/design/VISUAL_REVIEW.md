# Visual prototype review checklist

**Issue:** #31. **Status:** Design direction accepted with PR #35. The
checklist remains useful for ongoing responsive and accessibility review.

## Reviewable pages

- [Overview](../../prototypes/visual/index.html#home) | overview,
  differentiated value proposition, candidate ownership and navigation
- [Sample profile](../../prototypes/visual/index.html#profile) | approved
  facts, public bio, permissioned contacts and candidate CTA
- [Candidate Agent](../../prototypes/visual/index.html#agent) | prompt
  suggestions, user/agent messages, evidence disclosure and scenario controls

## Test surfaces

| Screen | Desktop | Mobile | Dark mode |
| --- | --- | --- | --- |
| Overview | 1440 × 900 | 390 × 844 | Both |
| Public profile | 1440 × 900 | 390 × 844 | Both |
| Candidate Agent | 1440 × 900 | 390 × 844 | Both |
| Agent exceptional states | Quota, empty, denied, unavailable, loading | Repeat key cases | Both |

Automated Playwright tests save desktop/mobile screenshots to
`prototypes/visual/screenshots/` for local review. CI can publish them
as a short-lived workflow artifact. The screenshots are generated from
static fictional copy and are **not production UI evidence**.

## Reviewer approval criteria

- [ ] Credible, recruiter-oriented visual hierarchy
- [ ] Approved facts remain easier to discover than generic AI marketing
- [ ] Public/private boundary communicated accurately
- [ ] No unsupported candidate claims or real-person imagery
- [ ] No awkward layouts or horizontal overflow at target widths
- [ ] Both themes have acceptable text, controls and state contrast
- [ ] Keyboard navigation, focus, landmarks and evidence disclosure are usable
- [ ] Loading, denial, quota, no-facts and provider-failure states are clear
- [ ] Chat does not imply unsupported answers are authoritative
- [ ] Scope remains design-only: no new provider costs or Django UI replacement

A design reviewer may approve this direction or request a second visual
iteration. Do not merge the design direction into the React UI solely
because unit tests pass.
