# Grid and List: section navigation

October 8, 2026. Requested by Igor: research the design first, put statewide
measures first, and provide three jump destinations in Grid and List.

## Research and decisions

The sources support a small contents navigation for this page. They do not
establish that a particular visual treatment will work best for CalBallot;
the choices below adapt their guidance to three destinations and our existing
sticky header. No user usability study has been conducted.

| Primary source | Relevant guidance | CalBallot decision |
| --- | --- | --- |
| [USWDS in-page navigation](https://designsystem.digital.gov/components/in-page-navigation/) | Useful on long pages with distinct sections; labels should match headings; keyboard access precedes content and moves focus to the target. Its component uses a side rail. | Three visible links before content, in reading order. Use a compact top bar as requested: only three destinations, no loss of card width to a side rail. |
| [GOV.UK tabs](https://design-system.service.gov.uk/components/tabs/) | Tabs display one section at a time and can hide relevant content; a single page with headings and contents links is an alternative. | Keep all three sections available. Jump links are ordinary links, visually distinct from Grid/List view buttons. |
| [W3C link pattern](https://www.w3.org/WAI/ARIA/apg/patterns/link/) | Native anchors provide built-in link behavior; an ARIA role alone does not. | Real `href` values: keyboard activation, copyable destinations, modified clicks and browser history. No `tablist` semantics. |
| [W3C focus not obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html) | Sticky content can obscure keyboard focus; scrolling offsets can prevent it. | Measure the existing header with ResizeObserver, set document scroll padding, and leave a small gap above target headings. Do not add another sticky bar. |
| [GOV.UK skip link](https://design-system.service.gov.uk/components/skip-link/) | Keyboard users need a way past repeated header navigation to main content. | Separate first-focus skip link to main content, then the visible Jump to links. Section headings can receive programmatic focus without adding extra Tab stops. |
| [W3C target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) | Minimum target dimensions or adequate spacing reduce accidental activation; the minimum criterion is 24 CSS pixels with exceptions. | Use at least 44px-high jump/return links as a more generous design choice. Underlines and visible outlines identify links and focus without relying on color alone. |
| [W3C reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) | Content should reflow at narrow effective viewport widths without requiring two-dimensional scrolling, subject to specific exceptions. | Allow links to wrap; no horizontally scrolling navigation or mobile dropdown. Check 320 CSS pixels, intermediate widths and enlarged text. |
| [MDN scrollIntoView](https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollIntoView) | Scroll offsets accommodate fixed headers; behavior can be instant or animated. | Use instant jumps, also suitable for reduced-motion preferences. Check target visibility after asynchronous records load. |

## Resulting behavior

1. The actual document order is Jump to → Statewide measures → Local measures
   → Full grid/list. This is not a visual-only CSS reorder. The introductory
   explainer moves below the full collection; its existing dismissal survives.
2. The first two destinations are identical in Grid and List. The third link and
   heading change together to **Full grid** or **Full list**. Current-election
   cards and their complete detail views remain shared between both modes.
3. Local and catalog headings offer a return to the jump links. Only the existing
   main header stays sticky. Insights and Explore hide this browse navigation.
4. Catalog filters do not hide the current-election destinations. Searching from
   the header scrolls to the collection's controls/results. Jumps preserve active
   in-session filters, county selection and pagination.
5. Fragment IDs name sections; `?view=list` and `?page=2` retain view and page in
   shared links. Older `#page=2` links still work. Existing `#m=<id>` measure
   links remain valid; closing a measure opened from a section restores that URL.
   Filters and selected county are not newly serialized for sharing/reload.
6. Keyboard activation moves focus to the matching heading; the next Tab reaches
   its following control. Mouse jumps scroll without explicitly moving focus.
   List result rows also support Enter/Space.

## Implementation and verification

- Source: `scraper/src/website/browse_navigation.py` and integration in
  `scraper/src/website/generator.py`.
- Behavioral browser check: `scraper/scripts/check_browse_navigation_browser.py`.
  Exercise both modes, keyboard navigation, repeated jumps, responsive offsets,
  filters, county selection, pagination, Back/Forward, reload, legacy pagination,
  measure permalinks, modal return URLs and Insights/Explore transitions.
- Candidate build uses the current generator, published prepared records and
  embedded analysis payloads, and database statistics read through SQLite
  `mode=ro`. No source refresh or enrichment. The records JSON, all databases,
  finance, research and standalone measure pages must remain unchanged.
- Local build and browser evidence:
  `scraper/data/statewide_recon/20261008_navigation/` (ignored).
- Verification: 83 focused tests passed; the navigation matrix passed at 1440,
  768, 640, 390 and 320 CSS pixels, including enlarged text at 640. The final
  initialization/ARIA adjustment passed the desktop and 320px matrix again.
  All 14 statewide detail views and standalone pages passed at 1440/390/320.
  These are Chromium checks, not a claim of a full assistive-technology audit.
- The [evidence record](browse_navigation_evidence_20261008.json) distinguishes
  the tested revisions. The standard output writer preserves the published
  Windows line endings; normalized final HTML exactly matches the final browser
  test. JSON and embedded analysis payloads are byte-identical to the baseline.
- Status: implementation and verification complete; independent review underway.
