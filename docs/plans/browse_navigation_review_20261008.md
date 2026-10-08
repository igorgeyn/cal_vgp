# Navigation review and dispositions

October 8, 2026. Read-only Claude CLI review; no command execution, edits,
publishing or source capture was available to the reviewer. Verdict:
**READY WITH CONDITIONS**. Codex assessed both conditions as resolved before
release; there was no second Claude verdict.

## Codex dispositions

1. **About ARIA: accepted and already fixed.** The final navigation selector names
   only Grid, List, Insights, Explore and their view cards. About receives no
   `aria-pressed` attribute. The review read the earlier selector while work was
   in progress.
2. **Navigation evidence: resolved.** The reviewer inspected the evidence before
   the running tests finished. The five-width navigation report now exists;
   the final initialization/ARIA change also passed the full desktop/320px
   matrix. The final output writer changes only line endings relative to that
   browser-tested HTML, verified by normalized SHA-256. The earlier content
   report is a deliberately separate all-proposition regression, not the
   navigation proof. Calling that content report unrelated overstates the issue.
3. **Search landing:** retain the documented heading/controls destination so
   users can see and change catalog filters. At 320px, rows require scrolling
   past controls; this is a known design tradeoff, not a claim that rows always
   appear above the fold.
4. **History behavior:** actual Back/Forward, reload, legacy pagination, List
   mode and modal return-URL checks passed. No functional regression reproduced.
5. **Further accessibility coverage:** Chromium checks do not constitute a
   screen-reader or cross-browser audit. Modal focus trapping/return predates
   this work. Combined 320px plus doubled text and landscape coverage remain
   follow-ups, not newly claimed passes.

The final input and output hashes and tested revisions are in
[browse_navigation_evidence_20261008.json](browse_navigation_evidence_20261008.json).

## Reviewer output (retained as written; references its earlier snapshot)

I have completed a thorough static review. Here is my assessment.

---

# Review: Grid/List section navigation — VERDICT: READY WITH CONDITIONS

The change is well-scoped, research-grounded, and functionally sound in static analysis. Document order is genuinely reordered (not CSS), native links/headings and the offset logic are implemented correctly, and the build receipt (`build.json` + asserts in `build.py:39,42`) confirms the records JSON and all three DBs are hash-unchanged. I found **no confirmed functional regression**, **one confirmed low-severity a11y defect**, a few concerns that want browser confirmation, and a notable **evidence gap**: there is no navigation browser report yet.

## Evidence gap (blocks a clean READY)
- `scraper/data/statewide_recon/20261008_navigation/claude-result.json` is empty, and `content-browser/report.json` is a **stale/unrelated artifact** — it reports `html_sha256: bc19aa82…` and checks statewide-guide measure IDs, whereas the candidate HTML is `3419b4cd…` (`build.json:9`). The behavioral test (`check_browse_navigation_browser.py`) writes `report.json` with `grid_and_list`/`keyboard_focus_and_offset` keys; no such file exists. So the 5-width browser pass is **not yet demonstrated**.

## Confirmed defect (low severity)
1. **About button receives `aria-pressed="false"`.** `syncBrowseNavigation` (`browse_navigation.py:92–96`) iterates `.view-btn, .view-card` and sets `aria-pressed` on every match. The About control (`generator.py:788`, a `.view-btn` with no `id`, `onclick="openAboutModal()"`) is a modal launcher, not a toggle, so it gets announced as an unpressed toggle button. This is newly introduced (no view button carried `aria-pressed` before; `setView` at `generator.py:15229–15235` only toggles `.active`). Fix: restrict the loop to the four real view controls, or skip buttons whose `id` isn't a view id. (Applying `aria-pressed` to Grid/List/Insights/Explore is defensible; the About case is the clear error.)

## Concerns needing browser reproduction
- **Header search lands on the heading, not results.** `setupEventListeners` scrolls to `#full-catalog` on each debounced keystroke (`generator.py:10790`). That heading sits above the view-switcher cards, stats ribbon, and filter panel (`generator.py:865,928,1230`), so the filtered results in `#resultsContainer` (`generator.py:1408`) can be well below the fold at shorter viewport heights. Matches the plan's stated intent ("controls/results"), but worth confirming results are visible after a header search at ~700–850px heights. Not a defect.
- **Back/Forward scroll relies on `hashchange` firing during history traversal.** The `popstate` handler (`generator.py:10795–10803`) updates view/page but does **not** scroll or close the modal; re-scroll and modal-close come from the separate `hashchange` handler (`10804–10815`). For the jump scenarios every history step is a pure fragment change (same search, different hash), so Chromium fires `hashchange` and it works — but the test exercises exactly this, so it should be confirmed green in the browser rather than assumed. History steps that change only search params (same hash) won't re-scroll; that's acceptable and not a regression.
- **Very tall wrapped sticky header at narrow/landscape widths.** The ResizeObserver offset (`browse_navigation.py:99–104`) correctly tracks `.header` height (header is `position: sticky; top:0`, `generator.py:2610–2617`), and `positioned()` passes at the tested portrait heights. A heavily wrapped header (search goes full-width at ≤768px, `generator.py:5448`) in landscape could still push targets low; low risk, worth a glance.

## Pre-existing limitations (note only — not blockers, not worsened here)
- The measure modal does not trap focus or return focus to the triggering row on close (`closeMeasureDetail`, `generator.py:15195–15203`). The new list-row `Enter`/`Space` support (`handleLocalCardKey`, `generator.py:11275–11279`) and `measureReturnURL` URL-restoration are correct and don't worsen this; focus-return would be a natural follow-up, out of scope here.

## Things verified clean
- DOM order `browse-navigation → statewide-measures → local-measures → full-catalog → resultsContainer`, all IDs unique in the candidate (`site/index.html:6814,6831,6862,6884`; test assertion `check_browse_navigation_browser.py:52–55`).
- Native `href`s with modified-click/middle-click passthrough and `preventDefault` only on primary click (`browse_navigation.py:106–112`) — no double-scroll on click; native anchors remain a working fallback if the data fetch fails before `initializeBrowseNavigation` (`generator.py:9813–9818, 9826`).
- Keyboard vs mouse focus split via `event.detail === 0` (`browse_navigation.py:111`) matches plan item 6; headings are `tabindex="-1"` focus targets (`generator.py:813,844`, `browse_navigation.py:17`).
- Legacy `#page=N` rewritten to `#full-catalog` (`generator.py:10774`) with `loadPageFromURL` honoring both legacy hash and `?page=` (`10761–10766`); `?view=list` restored on load (`9767`); `applyFilters` does not reset `currentPage`, so deep links survive.
- `#m=<id>` permalink + section return URL round-trips via `viewMeasure`/`closeMeasureDetail` (`generator.py:14770–14772, 15199–15202`); cross-file `measureReturnURL`/`browseTargetIds` bindings (declared in `browse_navigation.py:71–72`, used in generator) share one script scope and resolve at call time — no TDZ/ReferenceError.
- Hero/local sections are outside `#resultsContainer` and guarded by `heroSection.dataset.rendered` (`generator.py:11160–11163`), so catalog filtering/search never hides the current-election destinations. Insights/Explore hide `#browse-navigation` and `#catalogHeader` in both views (`generator.py:12522–12524`).
- Research mapping in the plan is honest (explicitly no usability study; sources don't dictate the visual) and the implementation matches each cited guideline (native links, skip link, 44px targets, focus outlines, reflow/wrap, instant scroll, scroll-padding + measured offset). Scope is disciplined — no card redesign, no filter serialization.

## Test gaps
- **Primary:** produce the real navigation `report.json`; the present browser artifact is stale/unrelated.
- No assertion that a **mouse click does not move focus** (plan item 6).
- Explore is only checked for `heroSection` hidden (`:133`); not that `#browse-navigation`/`#catalogHeader` are hidden in Explore (only Insights, `:130–131`).
- 320px is tested at normal text and 640px at 200% separately; the **320px + enlarged-text** combination isn't exercised.
- About-button `aria-pressed` semantics unchecked; `local-measures` Tab target (return link precedes county select) unasserted.

## Conditions for READY
1. Land a passing `check_browse_navigation_browser.py` `report.json` for the current candidate (`3419b4cd…`) before public promotion.
2. Fix the About-button `aria-pressed` in `syncBrowseNavigation`.

Everything else is optional polish.
