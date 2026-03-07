# Accessibility

Alcove targets **WCAG 2.1 Level AA** compliance for its web UI.

## Keyboard Navigation

| Key | Action |
|-----|--------|
| Tab | Move focus through interactive elements (skip link, search input, search button, upload zone, back link) |
| Enter / Space | Activate the upload zone (opens file chooser) |
| Enter | Submit the search form |
| Escape | No custom handler; browser-native behavior (dismiss dialogs, cancel file chooser) |

The skip link is the first focusable element in the DOM. Activating it moves focus directly to `#main-content`, bypassing the header.

## Screen Reader Support

Tested landmarks and regions:

- `<html lang="en">` — language declared at document root
- Skip link (`<a href="#main-content">`) — first in DOM, visible on focus
- `<header>`, `<main>`, `<footer>` — native landmark roles; no additional `role` needed
- Search form — `role="search"` with a visible `<label>` (`.sr-only`) linked to the input via `for`/`id`
- Upload zone — `role="button"`, `tabindex="0"`, `aria-label`, `aria-describedby` pointing to the supported-formats note
- Upload status — `aria-live="polite"`, `aria-atomic="true"`, `aria-busy` toggled during file processing
- Results region — `role="region"`, `aria-label="Search results"`, `aria-live="assertive"` so new results are announced immediately
- Result cards — `aria-describedby` pointing to the per-card metadata (`source`, file type badge, relevance score)

Screen readers verified with:
- VoiceOver (macOS / Safari) — navigation by landmark, form interaction, live region announcements
- NVDA (Windows / Firefox) — browse mode, forms mode, live region announcements

## Known Limitations

- Color contrast has not been programmatically audited against WCAG AA ratios (4.5:1 normal text, 3:1 large text). Visual inspection suggests the amber-on-dark and cyan-on-dark pairs are within range, but a tool pass (e.g. axe, Colour Contrast Analyser) is pending.
- No automated WCAG test in CI yet. A template-attribute test exists in `tests/test_accessibility.py`; browser-level axe integration (pytest-axe / pa11y) is tracked in [#80](https://github.com/Pro777/alcove-starter-private/issues/80).
- The file-badge contrast (amber on amber-glow background) may be marginal for non-bold text — to be verified.
- Mobile screen reader testing (TalkBack, VoiceOver iOS) has not been performed.
