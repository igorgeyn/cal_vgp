# Statewide content review disposition — October 8, 2026

Codex verdict: ready to publish the complete reviewed public delta after the
private recovery update is stored and verified. No production database mutation.

Claude's first read-only review was READY WITH CONDITIONS; the bounded correction
review is READY. Codex independently reproduced the source issues and checked the
fixes. The first review's missing-evidence conditions are now satisfied by the
83-case suite, the strict frozen-input rebuild, complete preservation report and
all 14 propositions at desktop, 390px and 320px. These were executed by Codex;
Claude inspected code and recorded artifacts without executing checks.

| Finding | Disposition |
|---|---|
| F1 contributor names flattened with attribution | Fixed. Each source anchor retains its own text and URL; attribution paragraphs remain separate. Multiple named entities retain one unallocated source-row amount with an explicit note. The suggested first-link shortcut would have lost some source entities, so it was not used. All 195 FPPC donor amounts/ranks/sides and all 14 SOS finance records are unchanged. |
| F2 FPPC donor can exceed SOS total | Clarified that the two sources are not a total and its breakdown. No fabricated reconciliation. |
| F3 other cards lack keyboard activation | Pre-existing and outside the statewide component update. Retained as a broader card-accessibility follow-up. Current statewide cards support Enter/Space. |
| F4 reviewed topic not searchable | Fixed; reviewed statewide topic and short title are included. Browser search for Housing & Land Use finds Props 1 and 37. |
| F5 selected-sample outcome statistics in JSON | Removed pass_rate/avg_yes/median_yes/closest_races for statewide context; guarded the card fallback. Historical and county context paths are preserved. |
| F6 standalone pages can fail after partial writes | Added statewide prevalidation before the output directory is created, with a failure-before-write acceptance test. |
| F7 source typography | Retained source spellings and valid currency whitespace; malformed amounts remain explicitly flagged. |

Codex also caught and fixed mobile overflow, the CSS font-import ordering and
unintended loss of historical briefing/context attribution. The 2028 assignments
remain separate from the November slate. No claim is made that caching caused
the user's screenshot.

Claude's advice to publish only root HTML/JSON was rejected: the 14 changed
individual pages must ship in the same Git revision. The scraper mirror is
synchronized locally and not committed. Current finance is a dated snapshot;
transaction timelines, concentration and sectors are not invented from it.

## Initial independent review

I've independently traced the data path end-to-end: raw SOS/FPPC HTML → parser → package JSON → rendered explorer modal and standalone pages. Here is my review.

---

# Independent review — statewide reader content vs. main `7b7a4b5`

## Verdict: **READY WITH CONDITIONS**

The implementation is substantively sound. I tried to break the attribution, fiscal interpretation, pro/con ownership, finance-table association, escaping, and leakage, and the code holds up under the specific stress cases the brief named. I found **no correctness, safety, or leakage blockers in the code**. The conditions are (a) completion of the still-in-flight verification evidence the caller already flagged, and (b) one visible finance-presentation blemish I'd fix fast.

---

## What I verified against raw sources (skeptic's pass)

All confirmed against `sources/*.html`, the package JSON, and the built pages (`candidate-final2`):

- **All 14 identities** present and internally consistent across `review.json` ↔ `statewide_2026.json` ↔ built pages. Reused legacy ids render correctly: `measures/10960.html` is Prop 3 (canonical `INIT_1993`), `12471.html` is Prop 39, etc. (`statewide_content.py:406`, `test_statewide_ballot.py:186-189`).
- **Props 2 & 5 finance absence** → `no_committees_identified`, rendered as "No committees identified by the SOS as of 2026-10-06" + "not a finding of zero contributions or spending." Correct (`statewide_content.py:126-127`).
- **Prop 3 FPPC "Propostion 3" typo** tolerated (`statewide_content.py:340`); panel still matched; 2 supporting committees; opposing "No committee…" correctly yields no opposing group (`fppc.html:877,1022`).
- **Prop 39 $1 discrepancy**: oppose rows sum $29,637,419 vs published $29,637,418 → `source_row_difference_cents: 100`, rendered "differ … by $1.00. The total above is the SOS-published figure." SOS total retained (`statewide_content.py:137-139`; `12471.html`).
- **Prop 39 malformed `$2,000,0000`** (`fppc.html:1375`) → "Amount needs verification" + "The source displays $2,000,0000." Not silently dropped (`statewide_content.py:150-153`).
- **Normal currency whitespace** `$<span>3,204,703.12</span>` → accepted, amount preserved, no false "needs verification" (`money_cents` strips `^\$\s+`, `:262`).
- **Multiple-measure money**: e.g. "TAX THE ULTRA-RICH NOW, YES ON 3 & 40, NO ON 41 & 42" ($703,494) appears under Props 3/40 support and 41/42 oppose. Within each measure, committee rows reconcile to the SOS published total (diff 0); the "do not add these figures across measures" disclaimer is present (`:120,144`). Conservative and correct — no cross-measure summing.
- **Escaping**: injected `<img onerror>` is escaped (`render_sections` uses `escape()` throughout; `test_…:145`). **Unsafe links** (`javascript:`, embedded credentials, non-http) rejected in `link()` (`:62-66`) and `safe_http_url()` (`build_measure_pages.py:41`).
- **Election scoping**: projection gates on `ballot_status=='qualified'` AND `election_date=='2026-11-03'`, with a strict `(id, measure_id, proposition_number, source_url)` match or `ValueError` (`:422-428`). Withdrawn ACA 13 and 2028 assignments are untouched and listed separately (`future_ballots`, `:73-81`).
- **Drift fails closed**: builder re-hashes every manifest entry + requires HTTP 200 before parsing (`build_statewide_content.py:20-25`); parsers raise on wrong prop id, wrong election string, unexpected overview labels, unknown FPPC side headings, or column changes.
- **No current/historical finance leakage**: the modal renders `guideSections.finance` with precedence over legacy `financeData[id]` (`generator.py:15142-15150`); the browser script explicitly asserts historical prop 10939 still shows CalAccess finance but *not* "2026 reported campaign contributions" (`check_…:103-109`).
- **Stale-cache mitigation**: explorer fetches `measures-data.json?v=<sha256[:20]>` with `cache:'no-cache'` (`generator.py:9807`) — a plausible fix for the old-four-records screenshot without inventing a cache "cause."
- **Honest dates**: capture date ("source captured 2026-10-08") is kept distinct from data as-of ("Reported through 2026-10-06", "FPPC list updated 2026-10-06").
- **Related statewide history** is populated for **all 14** props (my first `count:1` was a minified single-line artifact; `-o` shows 14 contexts, 12 comparisons each, integer-id linked, year<2026, `scope:statewide`). The modal shows only the 3 tiles + "selected set, not a representative sample" and **does not** print a pass-rate — the forecast guarantee holds at the render layer.

---

## Blockers

**None in the code.** The genuine gating items are publication conditions the caller already said are in progress — list them as conditions, not defects:

1. `browser-final/` (desktop/390/320) has not produced `report.json`. The `check_statewide_content_browser.py` logic is rigorous (14-measure count, versioned fetch, Enter-to-open, per-prop Main/Research/Finance, no horizontal overflow, cross-measure/withdrawn/historical non-leakage, carousel to Prop 45, standalone pages). It must actually pass on the published bundle. I did not run it; I only read it.
2. `preservation.json` full-record/page audit not confirmed present.
3. `candidate-final2/build.json` strict build completion with unchanged input hashes.

These are real pre-publish gates, but they are evidence-completion, not implementation flaws.

---

## Follow-ups (prioritized)

**F1 — Donor-name concatenation in FPPC lists (high; reader-facing; not a correctness/safety blocker).**
`name = text(cells[1])` swallows the whole contributor cell — the `<a>` plus FPPC's "Top Donor(s) to Contributor: …" sub-paragraph and parent-org notes — and the entire blob is then hyperlinked (`statewide_content.py:375,383-384` → rendered at `:149`). Evidence in the shipped page `measures/10960.html`:
- "National Education Association (MPO) **Top Donor to Contributor: National Education Association**"
- "SEIU California State Council for Working People **Top Donors to Contributor: SEIU California State Council**"
- worst case, an ACLU row visibly merges two contributor entities into one link.

It's faithful and escaped, and the link target (first `<a>`) is correct, but it reads as though the sub-donors are part of the committee name — directly undercutting the release's "clear attribution" goal, and it appears on nearly every proposition. Fix: set `name` from the first `<a>`/first text line and render the "Top Donor to Contributor" note as separate, non-linked sub-text (or omit). Low-risk, high readability payoff.

**F2 — Cross-source magnitude can confuse (medium; note).** Prop 39 "In support" SOS total is $15,785,413 (1 committee), yet that committee's FPPC top donor Richard Uihlein alone shows $17,000,000. This is inherent to the two sources' coverage and is disclaimed ("Amounts may differ … different reporting coverage"), but the juxtaposition invites "the math is broken" reactions. Consider a one-line inline hint on the committee row, or ordering/labeling that makes the coverage difference more obvious.

**F3 — Keyboard activation added only to statewide cards (low).** `role="button" tabindex="0" onkeydown="activateStatewideCard"` is attached solely when `statewide_guide` is present (`generator.py:14709`); all other measure cards remain mouse-only. Not a regression, but the new a11y affordance is inconsistent. Either extend it generically or note the scoping decision.

**F4 — Reviewed topic isn't searchable for statewide (low).** Search indexes `measure.topic_primary` (`generator.py:10978`), but statewide topics live in `display_topic`. Searching e.g. "Housing & Land Use" won't surface the props (official_title/description still match). Add `display_topic` to the search string.

**F5 — Latent pass-rate exposure (low).** `historical_context` for statewide still carries `pass_rate`/`avg_yes`/`median_yes` in the public JSON (`generate_site.py:461-472`) though unused in the statewide render path. Separately, the card-summary fallback would print "They passed X% … median YES Y%" for a pending measure lacking a summary (`generator.py:14664-14666`); it's masked for statewide only because `official_description` is always present (guarded by `load_package`). The "no selected-sample pass-rate displayed" promise is therefore render-layer-only and a bit fragile. Consider omitting those keys for `scope=='statewide'`.

**F6 — `build_page` not pre-validated before the write loop (low).** `build_site_pages` pre-validates `official_documents_html` for every measure but not `render_statewide_sections` (`build_measure_pages.py:297-302`). An unsafe statewide link would raise mid-loop after partial pages were written. The fresh-dir guard + upstream validation make this unlikely, but adding a dry pass closes it.

**F7 — Cosmetic (trivial).** The preserved "$ 3,204,703.12" renders with a space after `$`; SOS committee names are ALL-CAPS while FPPC names are mixed-case for the same committee. Both are faithful to source and explicitly accepted by the plan.

---

## Out of scope / correctly not attempted
- No finance timeline, donor-concentration, or sector breakdown is computed from the snapshot — the renderer says so explicitly (`:157`). Good; don't invent these from per-measure totals.
- Election-day status transitions remain pre-existing open work; I saw no *new* regression there.
- The reuse of legacy record ids (2/10956/10960) for Props 5/4/3 is the sealed Oct-8 reconcile's decision, enforced by `test_statewide_ballot.py` byte-preservation/rollback tests; not re-litigated here.

---

## What should happen next
1. Fix **F1** (fast; it's the only thing that looks broken to a reader) and re-run the focused suite.
2. Complete and attach the three publication-condition artifacts (browser `report.json` across 1440/390/320, `preservation.json`, strict `build.json`); confirm the browser suite passes on the exact bytes to be published.
3. Publish the paired root `index.html` + `measures-data.json` only (never the `scraper/` mirror).
4. Defer F2–F6 to a follow-up pass.

Note on evidence provenance: I treated `tests-final.xml` (81 passing) and the recorded browser/preservation runs as *claims to verify*, not as checks I performed. My confidence rests on reading the code, the pinned sources, and the already-built `candidate-final2` output — not on re-running anything.

## Focused correction review

I've inspected all the corrections against the source fixture and acceptance tests. Here are my concrete findings.

## F1 — Donor flattening (the main fix)

`contributor_blocks()` (`statewide_content.py:410`) now walks each `<p>` (or the bare cell when there are no `<p>` children), emitting per-child parts: anchors carry their own `{text, url}`, `<br>` becomes a `\n` marker, and each block is flagged `attribution` when its text starts with `Top Donor`. The all-attribution / empty guard still raises. Verified against the fixture:

- **ACLU row** (`fppc.html:1480-1483`): four paragraphs → blocks `[False, True, False, True]`, with links ending `id=1423278` then `id=1440576`, both attribution paragraphs retained. `grouped_names` = True (two named entities, one row amount). Matches `test_...:174-178`.
- **NEA** (`fppc.html:908-909`): `name` is built by joining only non-attribution blocks (`:394`), so it is exactly `National Education Association (MPO)` and the following `Top Donor` paragraph is excluded (`:171-172`). Also correctly *not* confused with the Prop 3 rows where NEA appears inside a `Top Donors` attribution line (`:994`, `:1617`).
- **a/br/a cell shape**: handled by the `or [cell]` branch — one block, two links, `grouped_names` True. The same holds for the p/p/p "Homeownership" grouping (`fppc.html:1057-1059`).

Rendering (`:149-163`) emits one anchor per part linking only its own text, wraps attribution blocks in `sg-contributor-block sg-note` (smaller text), and appends the explicit "amount is not split between them here" note only when `grouped_names`. No anchor can contain "Top Donor" text. This satisfies all assertions in the last two tests, including the injected-donor render check (`:179-185`). Your decision to keep the full paragraph/link structure rather than a first-link shortcut is correctly implemented and does preserve the two-named-entity rows.

## F2 — Finance semantics
`:145` now states the FPPC lists "are not a breakdown of the SOS totals above" and that "even one FPPC donor amount can exceed a displayed SOS total." Present and correct.

## F4 — Search coverage
`generator.py:10979-10980` adds `display_topic` and `statewide_guide.short_title` to the per-measure search string for statewide measures. Correct.

## F5 — Stat fields + card fallback
`generate_site.py:473-475` pops `pass_rate/avg_yes/median_yes/closest_races` from `historical_context` when `statewide`. The card fallback at `generator.py:14666` now gates on `!measure.statewide_guide`, so a statewide measure can no longer hit the `${ctx.pass_rate}%`/`${ctx.median_yes}%` sentence and render `undefined%`. Both halves of F5 are consistent.

## F6 — Pre-write validation
`build_measure_pages.py:297-300` validates every measure (`official_documents_html` + `render_statewide_sections`) before `out_dir.mkdir()` at `:301` and the write loop at `:303`. An unsafe statewide link raises before any directory/page exists, matching `test_...:188-196`. The symlink/existing-tree guards (`:291-294`) remain. The duplicate render in `build_page` (`:256`) is idempotent and harmless.

## Remaining defects
None found in the reviewed locations. The parsing, rendering, test fixtures, and the five companion fixes are internally consistent and match the fixture bytes.

Two non-defect observations (no action needed): the parsed `name` for an a/br/a grouped cell embeds a literal `\n` between the two names — cosmetic only, since rendering uses `contributor_blocks` with real `<br>`; and `render_statewide_sections` is invoked twice per statewide page (prevalidation then build), which is intentional and safe.

**READY** for these corrections — on the understanding stated in your message that I have not executed the suite, browser, or preservation checks; final evidence verification remains with you.
