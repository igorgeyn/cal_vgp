# County expansion workplan

> Written 2026-08-27. Replaces the stale five-county list in
> `docs/WORKING_LIST.md`, which still showed San Bernardino and the
> parser/loader as pending after both shipped.
>
> **Bottom line:** the five recon'd counties cover **28.8%** of
> California's local ballot measures, not the majority. Reaching half
> the state takes ten counties, and five of those ten have never been
> looked at. But construction is not the binding constraint —
> **maintenance is**, and it breaks somewhere between counties five and
> ten unless the architecture changes first (§5).

---

## 1. Where we actually are

| | Status |
|---|---|
| Framework (store, base scraper, runner, cron) | Shipped, 6 review rounds |
| Parser + loader | Shipped, 4 integrity blockers closed |
| San Bernardino scraper | **Live in production** since 2026-07-27 |
| SB measures on calballot.com | **Live** since 2026-08-27 (20 measures) |
| Developer guide + drift runbook | Written 2026-08-27 |
| Counties 2–58 | **Nothing built. Four have recon; 53 have not been looked at.** |

Coverage today: **1 county of 58 — 3.3% of historical local measure
volume.**

## 2. The prioritization finding

The original five were chosen by population. Ballot-measure production
does not track population.

| Rank | County | Measures | Cumulative | Recon? |
|---:|---|---:|---:|:--|
| 1 | Los Angeles | 1,389 | 12.6% | ✓ |
| 2 | **Alameda** | 598 | 18.0% | — |
| 3 | **Santa Clara** | 531 | 22.9% | — |
| 4 | San Diego | 516 | 27.5% | ✓ |
| 5 | **San Mateo** | 458 | 31.7% | — |
| 6 | Orange | 454 | 35.8% | ✓ |
| 7 | Riverside | 447 | 39.9% | ✓ |
| 8 | **San Francisco** | 386 | 43.4% | — |
| 9 | **Contra Costa** | 370 | 46.7% | — |
| 10 | San Bernardino | 364 | **50.0%** | ✓ **shipped** |

**Five of the top ten have no recon at all** — Alameda, Santa Clara,
San Mateo, San Francisco, Contra Costa. Each individually out-produces
Orange, Riverside, and San Bernardino. They are all Bay Area counties,
which suggests a regional pattern of frequent local measures that the
population-based selection missed entirely.

Further out: 20 counties reach **72.9%**; the remaining 39 hold 27.1%,
with a genuinely long tail (Alpine has 7 records total, Mariposa 9).

## 3. Itemized backlog

### Tier 0 — shipped

- [x] **San Bernardino.** Live. 20 measures, 88 documents, 5 prod
      snapshots. Three drift events absorbed.

### Tier 1 — the 50% tier (9 counties)

Ordered by volume; the recon'd ones are cheaper to start.

- [ ] **T1.1 Los Angeles** — 1,389 records, 12.6%. `results.lavote.gov/text-results/{election_id}`,
      sequential integer IDs. **Structurally different from SB:**
      section-organized text rather than a table, and it carries vote
      totals, so LA may deliver *results* data, not just pending
      measures. Expect the extractor to share little with `sb.py`.
      Recon done; historical depth unknown (see §6).
      **Est. 3–4 days.**
- [ ] **T1.2 Alameda** — 598 records, 5.4%. **No recon.**
      Est. 0.5d recon + 2–3d build.
- [ ] **T1.3 Santa Clara** — 531, 4.8%. **No recon.** Est. 0.5d + 2–3d.
- [ ] **T1.4 San Diego** — 516, 4.7%. Recon partial: polite UA
      validated, **measures page never found** (§6). Est. 0.5d recon +
      2–3d.
- [ ] **T1.5 San Mateo** — 458, 4.2%. **No recon.** Est. 0.5d + 2–3d.
- [ ] **T1.6 Orange** — 454, 4.1%. Slug-based
      `/elections/{slug}/measures-on-the-ballot`. Pre-2020 pattern
      unknown (§6). Est. 2–3d.
- [ ] **T1.7 Riverside** — 447, 4.1%. **Cloudflare challenge; needs
      Playwright.** Blocked on a prerequisite: the Playwright fetch
      path delegates redirects to the browser, so the per-hop
      robots/rate-limit guarantees do not apply. Resolve before
      enabling. Est. 1d prerequisite + 3–4d.
- [ ] **T1.8 San Francisco** — 386, 3.5%. **No recon.** City-county;
      structure may differ from ordinary counties. Est. 0.5d + 2–3d.
- [ ] **T1.9 Contra Costa** — 370, 3.4%. **No recon.** Est. 0.5d + 2–3d.

**Tier 1 total: roughly 22–30 working days of construction**, plus
compounding maintenance (§5).

### Tier 2 — to ~73% (10 counties)

Marin (342), Sonoma (317), Monterey (302), Fresno (289), Kern (240),
El Dorado (222), Ventura (213), Santa Cruz (207), Tulare (197),
Stanislaus (190). No recon on any. **Do not start Tier 2 until the
maintenance model in §5 is resolved** — ten more counties at the
current drift rate is not survivable.

### Tier 3 — the long tail (39 counties, 27.1%)

Individually 0.1–1.6% each. Per-county adapters are almost certainly
the wrong tool here; see §5 for alternatives. **Explicitly out of
scope until Tiers 1–2 are stable.**

### Cross-cutting items

- [ ] **Recon sweep for the five unexamined top-10 counties**
      (Alameda, Santa Clara, San Mateo, SF, Contra Costa) using the
      existing probe harness. One session, ~half a day, and it
      converts five unknowns into estimates. **Do this before
      committing to a build order.**
- [ ] **Fix the `SAN BERNADINO` county misspelling** — 5 records from
      2000 sit under a misspelled county name, appearing as a 59th
      county. Display-time correction may mask it; the DB value should
      be fixed.
- [ ] **Post-election results ingestion.** Every county after LA may
      supply outcomes. There is no design for turning a pending
      measure into a decided one while preserving identity.

## 4. What each county costs

Observed from San Bernardino, the only real data point:

| Phase | Effort |
|---|---|
| Recon (if none) | 0.5 day |
| Fixtures + pure extractor | 1–1.5 days |
| Scraper + tests | 1 day |
| Review round + fixes | 0.5–1 day |
| **Build subtotal** | **2–4 days** |
| Maintenance | **~1 drift event / 2 weeks / county, ~1 session each** |

The build cost is roughly linear. The maintenance cost is linear too —
which is the problem.

## 5. The maintenance wall — the real blocker

San Bernardino has produced **three drift events in five weeks live**
(2026-08-10 tax rate statement, 2026-08-24 notice of election, plus
launch-week surprises). That is about **one event per county per two
weeks**.

| Counties | Expected red crons | Reality |
|---:|---|---|
| 1 | 1 per 2 weeks | Current. Comfortable. |
| 5 | ~2.5 per week | Most weeks have a broken pipeline. |
| 10 | ~5 per week | Effectively a daily job. |
| 20 | ~10 per week | Not a hobby project anymore. |

Every drift event so far was the pipeline **correctly refusing to
guess**, and that strictness caught a real misattribution (five tax
rate statements about to be filed as impartial analyses). So the
answer is not to relax the rules.

Four options, and a recommendation:

**(a) Decouple capture from interpretation — recommended.**
Today the scraper must recognize a document's *role* to download it,
so a new document type breaks the weekly cron. It need not. The
scraper could capture the page plus **every** linked document in the
measures table, recording each link's label and URL without
classifying it. Role assignment moves to the **parser**, which runs
offline against stored snapshots.

Consequence: a new document type no longer turns the cron red. It
turns a *parse* red — fixable on your schedule, from stored bytes,
with no re-scrape and no lost data. Two of the three SB drift events
were exactly this class. Immutable snapshots already make it safe.
**Estimated 2–3 days, and it should land before county three.**

**(b) Automated drift triage.** The failure already names the cell,
row, and rule. It could classify itself and open a PR with the
proposed role addition and a pinned fixture. Reduces cost per event
rather than event count. ~3 days. Worth doing after (a).

**(c) Batch fixing.** Let counties sit red and fix weekly in one
session. Free, but a red cron means *no snapshot that week* — and this
data is perishable. Acceptable only if (a) lands first, because then
red means "unparsed", not "uncaptured".

**(d) Relax extraction.** Rejected. It converts loud failures into
silent misattribution, which is the failure mode this project has
worked hardest to eliminate.

## 6. Open questions blocking specific counties

1. **San Diego's measures page has never been found.** Recon confirmed
   the polite UA defeats the 403 on the homepage, but the per-election
   measures listing was never located. Blocks T1.4.
2. **Orange pre-2020 URL pattern.** Does
   `/elections/{slug}/measures-on-the-ballot` exist for older
   elections, or only recent ones? Affects backfill scope, not the
   forward scraper.
3. **LA text-results historical depth.** Back to 2007, or modern only?
   Determines whether LA can backfill or only capture forward.
4. **Sample ballot booklet PDFs** for LA / OC / SD — URL patterns
   unknown. SB embeds documents in the measures page; others may not,
   which could change the artifact model.

## 7. Recommended sequence

1. **Land the decoupling change (§5a)** — before county three, ideally
   before county two. It is the difference between linear and
   unsustainable maintenance.
2. **Recon sweep** of the five unexamined top-10 counties. Half a day;
   removes five unknowns from the estimate.
3. **Los Angeles.** Largest single gain (12.6%), recon done, and its
   structural difference will prove the framework generalizes beyond
   SB's table shape.
4. **Re-sequence Tier 1** on the recon results rather than on the
   current population-derived order.
5. **Revisit the widget design** once 3+ counties are in — the
   carousel-vs-scroll question resolves itself with real multi-county
   volume.
6. **Decide Tier 3 separately.** 39 counties for 27% of measures via
   per-county adapters is likely the wrong trade; that tier may want a
   different technique entirely, or may simply not be worth it.

## 8. Decisions needed

- **Target coverage.** Is the goal 50% of local measures (10 counties),
  73% (20), or all 58? The answer changes whether §5a is a nice-to-have
  or a precondition.
- **Maintenance appetite.** How many red crons per week is acceptable?
  That number, more than anything else, sets the ceiling on county
  count.
- **Backfill vs forward-only.** Every county so far is forward-only.
  Historical backfill multiplies both value and the cross-source
  reconciliation problem (KNOWN_ISSUES #12), which has never been
  exercised against overlapping data.
