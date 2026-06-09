# CalBallot Lessons Learned

> Pitfalls catalog. Things this project has hit; documented here so
> they don't bite again. Distinct from
> [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) (open data-quality issues)
> and [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) (chronological
> narrative).
>
> Each entry: the trap, the lesson, where the fix lives. Newest at
> the top of each section.

---

## Code / pipeline traps

### `id` must be in `valid_fields` when constructing `BallotMeasure` from dicts

**Trap:** `scraper/scripts/generate_site.py` filters incoming dicts
through a `valid_fields` set before passing to `BallotMeasure(**...)`.
The first iteration omitted `'id'`, which silently broke the Finance
modal lookup for **all 12,365 measures** because `financeData[String(measure.id)]`
in the JS could never find a match.

**Detection:** Igor noticed Prop 27's Finance tab showed "No campaign
finance data available" despite `financeData["10939"]` being present
in the HTML. The bug was site-wide, not measure-specific.

**Fix:** Always include `'id'` in the construction filter. Commit
`a76e51e` (2026-05-20).

**Lesson:** When filtering dataclass-construction kwargs, the
field-list is load-bearing. A silent omission can break far downstream
in ways that don't show up in any single record. Test the consumer
contract, not just the dataclass.

---

### Dedup gates must key on canonicalized donor names, not raw

**Trap:** `rebuild_finance_db.py` Gate 7 (cross-source dedup) was
keyed on `donor_raw` rather than `canonicalize_donor(donor_raw)`.
Donor canonicalization patterns existed but the dedup gate bypassed
them, so casing/punctuation variants of the same donor stayed
distinct and inflated totals by $78M. Affected high-profile fights:
PROP_27_2022 DraftKings/FanDuel casing (−$35M), PROP_32_2012 Munger
Jr name variants (−$20M), PROP_8_2018 SEIU UHW Nonprofit 501(c)(5)
suffix (−$11.4M).

**Detection:** Investigating the PROP_8_2018 UHW pair (donor pair
that should have merged but didn't) exposed the structural bug.

**Fix:** Switched Gate 7 to key on
`canonicalize_donor(donor_raw)`. Commit `9fb9dc0` (2026-05-12).
Total receipts $3.32B → $3.24B (−$78M); win rate 64.6% → 65.2%.

**Lesson:** Any gate that's supposed to be "are these the same
thing?" must run through the canonical form. If you have a
canonicalizer, USE IT at every comparison boundary — don't leave
a side-door where raw values get compared.

---

### Don't trust vendor "year" fields as election year

**Trap:** CalAccess reports finance transactions under a reporting
year that often runs 1-2y after the actual election year. Schwarzenegger
2005 special-election props show up as 2006 in CalAccess. If you key
your crosswalk on `(prop_num, calaccess_year)`, you'll fail to match
~14 entries totaling significant dollar volume.

**Detection:** "Missing crosswalk entries" audit decomposed the
unmatched bucket; Bucket A (~10-15 entries, most of the $) traced
to year-misattribution.

**Fix:** Crosswalk matcher v2 looks back up to 2 years (the
`MAX_YEAR_LOOKBACK` constant in `build_finance_crosswalk.py`) when
the on-cycle year fails. `_actual_election_year` in
`src/finance/schema.py` remaps for downstream queries. Commit on
2026-05-12.

**Lesson:** Vendor year fields can be administrative, not
ground-truth. Always have a remap path back to the actual event
year, and a `match_via` field documenting how the match was made.

---

### CEDA's `pass_fail` encoding can lie about thresholds

**Trap:** Five CEDA measures show `passed=1` with
`vote_threshold='66.67%'` but have `percent_yes` well below 66.67%
(e.g. 54.55%, 55.61%). The threshold field is derived from CEDA's
`pass_fail` code which was miscoded for these.

**Detection:** Internal data-quality sweep.

**Status:** Documented in [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) #1.
Not yet auto-corrected; needs manual source verification.

**Lesson:** When deriving secondary fields from vendor codes,
spot-check at least the implied invariants (e.g. "if passed=1 with
threshold 66.67%, then percent_yes ≥ 66.67%"). Document the cases
the invariant catches as KNOWN_ISSUES rather than silently fixing.

---

### CSS class names can collide across panels

**Trap:** The Finance modal redesign in 2026-05-20 introduced
donor-list classes that happened to match classes already used by
the Insights panel. Both lived in the same generated stylesheet;
the Insights versions, defined later in the file, overrode the
modal versions with a column-stacked layout the modal didn't want.

**Detection:** Modal donor list rendered with wrong layout despite
the local CSS looking correct.

**Fix:** Scoped modal CSS under a parent selector
(`.finance-side .donor-row`) so it can't collide with Insights-panel
rules at the same depth.

**Lesson:** A generated stylesheet with many co-located rules is a
collision risk. Scope styling under a parent selector when adding
new components to an existing context. Don't assume class names
are namespaces.

---

### Static site regenerates to TWO `index.html` locations

**Trap:** `src/website/generator.py` writes to both repo-root
`index.html` (the GitHub Pages serve target) and
`scraper/index.html` (the build artifact). For a brief window in
2026-05-04 only the root one was being written; users got stale
content because the local-dev preview path looked at scraper/.

**Fix:** Generator dual-writes both locations. Always.

**Lesson:** When a build output has more than one consumer (GH
Pages + local preview), explicitly enumerate every output path and
keep them in sync. Don't rely on developers remembering to copy.

---

### Atomic UI flips beat half-migrated state

**Pattern (not a trap):** When migrating UI consumers from
data-layer v1 to v2, OR from v2 monetary to v2+v3 combined, the
project consistently flips ALL consumer surfaces in one commit
rather than incremental migration.

**Why:** Half-migrated state is invisible to users but
catastrophic for invariants. If `get_top_donors` returns v2 numbers
but `get_summary` returns v3 numbers, every cross-check breaks. One
commit, one flip, one verification pass.

**Canonical example:** Phase 5 `bec2abe` (2026-05-19) flipped the
v2/v3 combined read layer across `src/finance/operations.py`,
`src/api/server.py`, `src/research/sources/finance.py`,
`scripts/generate_insights.py`, `src/website/generator.py` — all in
one commit. Five Codex rounds reviewed it before merge.

**Lesson:** For data-layer migrations, design the flip to be
atomic. The verification step that runs after is the proof; the
pre-flip period is the design space.

---

## Scraping / external source traps

### Polite User-Agent is non-negotiable

**Trap:** Generic User-Agent strings (Python `requests` default,
browser defaults from headless tools) get blocked outright by some
county registrar sites. San Diego (`sdvote.com`) returned 403 on
generic UAs but 200 on a polite UA that identifies the project +
contact.

**Detection:** Phase 0 reconnaissance pass with the local probe
harness (2026-06-08). 4 of 5 counties accepted generic UAs; SD did
not.

**Fix:** Standard polite UA shape:
```
cal-vgp-registrar-recon/0.1 (+https://github.com/igorgeyn/cal_vgp; contact: igorgeyn@gmail.com)
```
Carries the project name, version, source link, and a real contact
email. Set as the default in `scraper/scripts/recon/probe.py` and
in the Phase 0.5 `CountyRegistrarScraper` base class.

**Lesson:** Polite scraping isn't "nice to have." It's the
difference between 200 and 403 on at least some sites. Build it
into the base class from day one, not as an afterthought.

---

### Cloudflare bot challenges need JavaScript execution

**Trap:** Riverside County (`voteinfo.net`) sits behind Cloudflare's
"Just a moment..." JS challenge page. Returns HTTP 403 with a
5.5KB HTML body containing the challenge script. Polite UA does
not help — the block is based on missing JS execution, not UA
filtering.

**Detection:** Phase 0 recon. Polite UA worked for SD but Riverside
still 403'd; the response body itself is the giveaway.

**Fix path:** Use Playwright (or headless Chrome) which executes
the JS challenge and gets a real cookie. Documented as the fetch
mode of last resort in
[`docs/plans/registrar_pipeline_infra.md`](plans/registrar_pipeline_infra.md).

**Lesson:** Bot detection isn't monolithic. Some sites filter on
UA; some filter on JS execution; some filter on TLS fingerprints.
Diagnose the response body before assuming the cause. Plan for
heavier fetch modes (Playwright) from architecture day one — they
won't bolt on cleanly.

---

### Vendor URLs go stale; verify before trusting plan docs

**Trap:** The Jan 2026 registrar plan listed `sbcrov.com` as the
San Bernardino registrar URL. By June 2026 that DNS no longer
resolved. Real URL is `elections.sbcounty.gov` (also reachable via
`www.sbcountyelections.com`).

**Detection:** First probe attempt with `sbcrov.com` failed with
`getaddrinfo failed` (DNS-level).

**Lesson:** When picking up a plan written months ago, verify
external URLs before building against them. A 5-second `curl -I`
or DNS lookup beats discovering the URL is dead after writing the
scraper.

---

## Documentation traps

### Doc rot needs explicit snapshot-disclaim banners

**Trap:** `PROJECT_HISTORY.md` was written in Feb 2026 with current
stats ("11,483 measures"). By May 2026 the project had moved on
(v2 finance, v3 finance, combined $5.75B totals, etc.) but the doc
still showed Feb stats. A reader could plausibly use it as ground
truth and be wrong.

**Fix:** Added a top banner explicitly framing the doc as a
snapshot and pointing at the live truth ("see
`scraper/data/finance/README.md` for current state"). Same pattern
applied to `DATA_PIPELINE.md` Section 9.

**Lesson:** Don't try to keep snapshot docs current — that's a
losing fight. Disclaim them. Either:
- (a) Add a header banner ("Snapshot, not current state. See X for live."),
- (b) Promote them to "history" status and start fresh.
Both are fine; silently letting them rot is not.

---

### WORKING_LIST.md drifts faster than anything else

**Trap:** The doc that's supposed to be the "where we left off"
cross-machine resume point goes stale within 2-3 weeks of active
work if not updated. The 2026-05-20 snapshot wasn't refreshed until
2026-06-09 despite a major project pivot (finance → registrar) and
several commits in between.

**Lesson:** Update WORKING_LIST.md at the **end** of every active
work arc, not at the start of the next one. If the arc shipped
real commits, capture them in "Recently shipped" while the context
is fresh. The first sentence of the header should always answer
"what's the current state?" in plain English.

---

## Process / verification traps

### Sentinel checks beat aggregate sanity checks

**Pattern (lesson, not trap):** When ingesting data with implicit
attribution (year, prop number, donor, etc.), per-sentinel checks
(specific known-good values with min/max year + in-year %
thresholds) catch attribution drift that aggregate sanity checks
miss.

**Example:** `evaluate_data_quality.py` Finance dimension uses
per-sentinel checks for ~10 known marquee fights — "PROP_22_2020
oppose-side should be in the $200M-$220M range, all rows should be
in 2020." If a rebuild starts attributing 2020 dollars to 2022,
the aggregate stays ballpark-correct but the per-sentinel check
catches the regression.

**Lesson:** Always have a layer of checks below the aggregate.
Sentinels are cheap to write, expensive to live without.

---

### Verification stacks: Layer 1 / 2 / 3 / Phase G

**Pattern:** For data-layer migrations, the project consistently
runs four layers of verification:
- **Layer 1 — prior state unchanged.** Self-hash + value-match
  against the pre-migration database. Catches "did we accidentally
  touch v2 while building v3?"
- **Layer 2 — source reconcile.** Sum of derived layer matches sum
  of source layer to $0 diff.
- **Layer 3 — per-row traces.** Spot-check ~10 individual records
  through the full pipeline.
- **Phase G — cross-layer integrity.** Combined-layer (v2 stitched
  with v3) invariants like "no double-counting between layers,"
  "n_measures is union not max."

**Lesson:** For anything that affects total dollar amounts, build
all four layers. They catch different bugs. Layer 2 alone passes
on a "we lost some rows AND gained equally fake rows" failure;
Layer 3 catches that. Layer 1 catches "we corrupted v2 while
building v3" that the others miss.

---

### Codex review for architectural decisions

**Pattern:** Before committing to a major architectural decision
(new pipeline shape, new data source, schema rewrite), draft the
plan and run a Codex review pass. The project has ~15+ Codex review
rounds across its lifetime; they've caught:
- Cross-cycle finance contamination (drove the v1 → v2 rebuild)
- The Gate 7 raw-vs-canonical bug
- The R2 prefix needing explicit `snapshot_id` (Phase 0.5)
- Polite scraping defaults validity (later empirically validated
  by Phase 0 recon)
- ORDER BY non-determinism in crosswalk resolution
- Donor sector coverage misclaim ("95%" → actual "43%")

**How it works:** Write a Codex review prompt in `docs/codex/`
framing what's being decided, what's already locked, what concerns
to scrutinize. Igor runs Codex separately and pastes the feedback
back. Apply the feedback, commit, optionally do a round-2.

**Lesson:** External review catches things you can't catch from
inside the decision. Use it before locking in architecture, not
after.

---

### Pause for direction-check on tier transitions

**Pattern (Igor's stated preference):** When transitioning from
small/concrete work to higher-effort work — even within an
authorized arc — pause and check in. "Should I proceed to Phase X,
or do you want to QC the foundation first?"

**Why:** The foundation is harder to revise after the next floor
is built on it. The 30-second check-in is cheaper than the
hour-long revision.

**Example:** Phase 0.5 storage layer (c40c09c) shipped with 17
passing tests; instead of immediately layering on base scraper +
NoOp + runner + workflow in the same session, I paused and asked
for sanity check on the storage interface. Igor agreed; we wrapped
that session and picked up fresh.

**Lesson:** Foundation commits deserve a beat. Confirm before
building the next floor.

---

## Quick reference: where the wisdom lives

- **Per-machine memory** (`.claude/projects/.../memory/`) — Igor's
  preferences, conversational context, in-flight project state.
  Per-machine; won't follow across machines.
- **[`CLAUDE.md`](/CLAUDE.md)** (repo root) — rules of engagement,
  short summary of the hardest-learned rules, doc pointers.
- **This file (`LESSONS_LEARNED.md`)** — full pitfalls catalog with
  context. Read before substantive work.
- **[`KNOWN_ISSUES.md`](KNOWN_ISSUES.md)** — open data-quality
  issues. Different from this file: those are *current state*;
  these are *patterns to avoid*.
- **Commit messages** — finest-grained record of why something
  changed. `git log -p path/to/file` is often more informative than
  any doc.
- **`docs/codex/`** — past architectural debates, frozen as review
  prompts.
- **`docs/plans/`** — current arc plans, including registrar
  pipeline planning (`registrar_pipeline_infra.md`, the canonical
  Phase 0.5 design).
