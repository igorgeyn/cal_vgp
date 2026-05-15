# CalBallot Working List

> Snapshot: **2026-05-15 evening**. Branch: `main` (in sync with
> `origin/main`). Last shipped: commit `40ea27d` (Phase 4 Block E
> final: trace tests).
>
> **WHERE WE LEFT OFF — Phase 4 done, Phase 5 next.**
>
> v3 finance expansion through Phase 4 is fully shipped and verified.
> v3.db now carries **48,259 accepted rows / $2.568B** flowing across
> loans + in-kind + independent expenditures. All 11 Codex rounds
> integrated. 60 unit tests + 6 trace tests + 7 verification checks
> all green. The next discrete chunk is **Phase 5: atomic frontend
> commit** — see "Phase 5 next steps" below.
>
> This is the canonical resume point. Memory in `.claude/projects/...` is
> per-machine and won't follow you — start here when picking up on a new
> machine.

---

## Phase 5 next steps (resume here)

Phases 0-4 of the v3 finance expansion are shipped + verified. The
v3.db now carries:

  Loans:    269 accepted / $186.16M (LOAN_CD B1)
  In-kind:  23,878 accepted / $416.01M (RCPT_CD Schedule C)
  IE:       24,112 accepted / $1,965.93M (EXPN_CD F461P5/F465P3 + S496_CD)
  TOTAL:    48,259 accepted / $2,568.10M

All 11 Codex rounds integrated. 60 unit tests + 6 trace tests pass.
7 source-reconciliation checks all $0 diff. v2 baseline untouched
(Layer 1 8/8 PASS).

**Concrete next chunk: Phase 5 atomic frontend commit (~1 day).**

The big visible-product shift. Order of operations:

1. **Library / API migration first** (no UI change yet). Add to
   `FinanceDatabase` class in `scraper/src/finance/operations.py`:
   - `get_finance_summary_total(measure_db_id)` — uses
     `finance_summary_total` view
   - `get_finance_breakdown_by_type(measure_db_id)` — uses
     `finance_summary_by_type`
   - `get_top_donors_total(campaign_id, stance, limit=N)`
   - `get_top_donors_by_type(campaign_id, stance, receipt_type,
     limit=N)`
   - Existing v2 methods (`get_top_donors`, `aggregate_for_measure`)
     keep reading v2.db monetary-only tables — no breakage.

2. **Atomic visible-change commit.** All UI surfaces flip in ONE
   commit because half-flipped UIs make headline numbers
   inconsistent. Touches:
   - Modal Finance tab: total + breakdown layout ("Total
     support-side money: $X · Direct receipts $Y · Independent
     spending $Z")
   - Hero card / Insights Module 1: total replaces monetary
   - Insights Module 4 (marquee fights): includes IE
   - Insights Module 3 (top donors): uses `_total` ranked list
     across types
   - Briefing pipeline finance facts: uses `_total` view
   - API endpoint: returns both `total` and `breakdown` payloads
   - **Methodology note**: updated to explain what's now included
     and what's still out (Schedule E excluded, recalls excluded,
     etc.)
   - `insights.json` regenerated, `index.html` regenerated

3. **Win-rate math re-runs.** Current 65% "better-funded wins"
   number uses v2 monetary only. With IE included, the math
   changes — historically IE money is heavier on losing sides of
   contentious props. Number will probably shift down. Document
   the shift in the methodology copy.

4. **Headline number shift.** Homepage total receipts going from
   $3.24B (v2 monetary) to ~$5-6B (v3 total support-side). Ship the
   methodology note in the same commit so users see what changed
   and why.

**Verification at end of Phase 5:**
- Layer 1 still 8/8 (v2 untouched)
- All 6 trace tests still pass
- Re-eyeball 3-5 specific prop modals against Ballotpedia
- Codex round-12 sanity check on the visible-product result

**After Phase 5:**
- **Phase 6: Final verification + docs** (~½ day). Re-run all 68
  checks from `plans/finance-rebuild-verification.md`, add Phase G
  checks (IE / in-kind / loan integrity), update CHANGELOG +
  methodology + finance README.
- **Schedule E sub-phase** (non-blocking). Diagnostic to identify
  true cross-prop IE in Schedule E rows. If material, ingest as
  separate sub-phase with explicit double-count safeguards.

## Recently shipped

### 2026-05-04 — Finance v2 rebuild + Insights panel redesign (`fcd1345`)

- **Finance DB v2** (`scraper/data/finance/finance_statewide_v2.db`):
  year-scoped `finance_campaign_id` (e.g. `PROP_16_2020`) replaces bare
  `PROP_xx`. 8 row-level acceptance gates. 181 matched campaigns / $3.32B
  retained. New scripts: `build_finance_crosswalk.py` +
  `rebuild_finance_db.py`. Old `build_statewide_prop_finance_db.py` raises
  on import.
- **All consumer surfaces wired to v2**: `src/finance/operations.py` +
  `schema.py`, `src/api/server.py`, `src/research/sources/finance.py`,
  `scripts/generate_insights.py`, `src/website/generator.py`. Per-stance
  `ROW_NUMBER()` in `get_top_donors` so the smaller side of an imbalanced
  fight isn't crowded out. Modal lookup keys on `String(measure.id)` so
  PROP_1 disambiguates between 2022 and 2024.
- **Insights Finance panel redesigned**: 5 modules (hero anchor / spending
  arc by election year / top-15 donors + repeat players / 3 marquee fights
  with neutral "Won" badge / bridge prose). Client-side donor-name
  formatter title-cases ALL-CAPS strings via brand-display map + acronym
  allow-list.
- **Cleanups**: dropped dead `measures.campaign_finance` column (313 KB
  shed from `index.html`); restored generator dual-write (root +
  scraper-local `index.html`); rewired `extract_calaccess_finance.py
  --build-db` to v2 pipeline; refreshed `CHANGELOG.md` with 2.2.0 stub;
  snapshot-disclaimers on `PROJECT_HISTORY.md` + `DATA_PIPELINE.md`;
  marked `KNOWN_ISSUES.md #8` resolved.

Verification: `plans/finance-rebuild-verification.md` (68/68 automated
checks pass; Phase F manual checklist signed off via browser spot-check).

---

## Pending — by area

### NARRATIVE / IDEATION (new product directions)

- [ ] **Thematic policy explorations.** Build visualizations + compelling
      prose around recurring policy issues — e.g. local school funding
      flow over time, residential zoning + ADU rules, minimum wage laws.
      Show the long-arc story across measures, not just per-measure
      browsing. Hypothesis: most voters care about issue areas (school
      funding, min wage); wonks care about specific measures.
      **Stage: IDEATION** — needs scoping (which themes? what
      topic-classification coverage exists? what visual + narrative
      forms?) before any execution plan.
      **Probable prerequisite**: topic classification gap fix (currently
      75% of records bucket to "Other").

- [ ] **Hot-button issue / controversial-donor lenses.** Visualizations +
      prose around specific actors and the policy areas they shape — e.g.
      PG&E's influence on utility-regulation + wildfire-accountability
      measures, charter-school money in school-funding measures, tobacco
      / pharma / gambling / labor influence patterns.
      **Stage: IDEATION** — needs scoping (which actors? threshold for
      inclusion? does v2 finance + measure topics support the joins, or
      do we need donor-sector classification first?) before plan.
      **Probable prerequisite**: donor-sector classification.

### FINANCE

> **2026-05-?? audit of 37 missing crosswalk entries** decomposes them
> into three buckets:
>
> - **A. Year-misattribution (~10-15 entries, most of the $)** — CalAccess
>   reporting-year often runs 1-2y after the actual election. Schwarzenegger
>   2005 Props 73-80 show up as 2006 in CalAccess; ICPSR has them as 2005
>   (e.g. `CA1143` = Prop 73, 2005). Same pattern for PROP_4_2010 / 2012
>   (really 2008's Prop 4 = `CA1167`), PROP_39_2002 (really 2000's Prop 39
>   = `CA1084`), PROP_40_2016 (really 2012 = `CA1211`), PROP_49_2003 (really
>   2002), etc.
> - **B. Genuine coverage gaps (~5-10 entries, ~$25M)** — ICPSR caps at
>   2016; NCSL only carries Nov 2018 props. June 2018 primary props
>   (PROP_68_2018 = $21.8M Parks/Water Bond, PROP_69_2018 = $2.89M
>   Transportation lockbox, PROP_70_2018) are absent everywhere.
> - **C. Junk (~6-9 entries, ~$0.2M)** — `PROP_0_*` ($0, no prop number),
>   `PROP_92_2009`, `PROP_1_2020`, `PROP_1_2021` (stale committee filings),
>   `PROP_25_2026` (future).
>
> Implications drive the three new items at the top of FINANCE below.

- [x] ~~**Crosswalk matcher v2 (Bucket A fix).**~~ **DONE 2026-05-12.**
      Recovered 14 of the ~22 Bucket A entries (181 → 195 matched campaigns;
      37 → 23 missing). Sister fix in `rebuild_finance_db.py` widens the
      date-off-cycle gate to accept transactions within 1y of EITHER the
      CalAccess year or the actual election year. $1.91M of recovered $
      now in v2 summaries; sentinels still pass.

      **Codex round-4 follow-ups — RESOLVED 2026-05-12:**

      - [x] ~~Modal + briefing collision rollup~~ — new
            `FinanceDatabase.aggregate_for_measure(measure_db_id)` rolls
            campaigns sharing a measure_db_id into a single measure-level
            view (sums receipts per stance, unions donors with merged
            amounts, unions timeline weeks with recomputed cumulative,
            recomputes top5_share + HHI against the merged donor list).
            `_load_finance_data` and `src/research/sources/finance.py`
            both use it; modal now exposes recovered late-filing $ that
            previously got shadowed.
      - [x] ~~Insights measure_count mislabeling~~ — `build_finance_insights`
            now counts distinct measure_db_ids (181 not 193) and rolls up
            better_funded counters at the measure level (117/64.6% not
            126/65.3%). Adds `campaign_count` field for transparency.
      - [x] ~~ORDER BY determinism~~ — `resolve_campaign` and
            `get_all_campaigns` now sort by `election_year ASC` so the
            on-cycle (earliest year) campaign wins collisions independent
            of SQLite insertion order.
      - [x] ~~Audit-note preservation in resolve_pair~~ — when neighbor-
            year lookback bails on ambiguity, the ambiguity reason now
            surfaces in the missing row's `notes` instead of being
            overwritten with the generic "no measures-DB record".

      ~~**Annual-receipts year attribution**~~ **RESOLVED 2026-05-12.**
      The annual_receipts SQL in `build_finance_supplements` now uses a
      CASE expression on `match_via` to remap year-offset recoveries to
      their actual election year, and counts DISTINCT measure_db_id
      (`n_measures`) so collision pairs don't double-count. Visible
      shifts: $1.0M moved 2002→2000 (PROP_39_2002), $0.7M moved 2003→2002
      (PROP_49_2003), $0.33M moved 2010→2009 (PROP_1A_2010), the 8
      Schwarzenegger 2006→2005 recoveries (~$0.32M aggregate). Tooltip
      copy updated to "X measures" from "X campaigns" to match the rollup
      semantics.

      **Tests added 2026-05-12:** `tests/test_finance_crosswalk.py` (8
      tests covering lookback recovery, ambiguity bail, max-offset bound,
      audit-note preservation, id-preference within recovery);
      `tests/test_finance_db.py` (14 tests covering `_actual_election_year`,
      `resolve_campaign` collision determinism, `aggregate_for_measure`
      rollup semantics including donor union, top5/HHI recomputation, and
      timeline week-union with cumulative recompute). 22/22 pass.

      **Remaining ~$1.81M of expected Bucket A recovery is dropping at
      the stance gate** (PROP_4_2010 alone has 1,427 unknown_stance rows
      / $0.70M from committees like "Planned Parenthood Advocacy Project").
      Captured under the stance-recovery item below — now meaningfully
      bigger scope than the "residual 42 rows" framing implied.

- [x] ~~**Audit Prop 27 (2022) coverage gap.**~~ **RESOLVED BY DIAGNOSTIC
      2026-05-13.** Investigated the ~$99M gap between Ballotpedia
      ($169.1M Yes-on-27) and our v2 ($69.8M). Three root causes
      identified, none of which are bugs in the dedup commit `9fb9dc0`:
      (1) Our scope is monetary contributions to the official recipient
      committee only — we don't include in-kind, loans, or independent
      expenditures (which is where sportsbooks' direct-to-ad-agency
      spending sits). (2) `extract_calaccess_finance.py` filters
      amendments per FILING_ID, but each underlying transaction
      legitimately appears in multiple distinct FILING_IDs (Form 497
      24-hour late + Form 460 pre-election + 460 semi-annual + 460
      annual all carry the same Schedule A entries); Gate 7 in
      `rebuild_finance_db.py` correctly collapses this. (3) Crosswalk has
      1 oppose committee for Prop 27; Ballotpedia lists 2 (untagged
      second committee in CAL-ACCESS — separate small follow-up below).
      Spot-check ground truth: FanDuel raw CSV has 40 rows with only 8
      distinct (date, amount) tuples summing to $18.34M — matches v2 to
      the penny. Same pattern verified across PROP_22_2020, PROP_32_2012,
      PROP_8_2018. Methodology note added to Finance panel + insights
      methodology block + `scraper/data/finance/README.md` clarifying
      what's in/out of scope and why our totals run ~40-60% of headline
      press figures for high-IE-spending props.

- [ ] **Expand finance extract scope** (medium-large, future). Extend
      `scripts/extract_calaccess_finance.py` to ingest `LOAN_CD` (loans
      received), Form 460 Schedule C (in-kind contributions), and
      `S496_CD` / Form 461 (independent expenditures by major donors)
      alongside `RCPT_CD`. Closes the gap with Ballotpedia headline
      numbers but touches the entire 181-campaign DB; requires a
      verification rerun and a new column in `finance_summary` to
      distinguish receipt types. Worth doing only if the methodology
      note proves insufficient or if a downstream use case (briefing
      prose, donor-power narrative) needs the full picture.

- [ ] **Hunt missing second oppose committee for PROP_27_2022** (small,
      10-15 min). Ballotpedia lists "Coalition for Safe, Responsible
      Gaming" as a second No-on-27 committee. Our crosswalk has only
      1443032 ("Californians for Tribal Sovereignty"). Either the second
      committee didn't tag its filings with `BAL_NUM=27` in CAL-ACCESS,
      or its filings exist but don't survive our prop-number extraction.
      Check `finance_row_quarantine` and the raw `CVR_CAMPAIGN_DISCLOSURE_CD`
      dump for filer_id-of-other-committee. If it's a tagging gap, add
      to `COMMITTEE_STANCE_OVERRIDES` or extend the crosswalk to accept
      named committee fallbacks for known cases.

- [ ] **Backfill June 2018 statewide props (Bucket B).** Manually add
      PROP_68_2018 (Parks/Water Bond), PROP_69_2018 (Transportation
      lockbox), PROP_70_2018, and any other June 2018 props CalAccess
      knows about into the measures DB. Recovers ~$25M of currently-
      unmatched finance data. Source options: Ballotpedia (currently
      ingested only for 2020+), CA SOS archive, manual entry.

- [ ] **Filter Bucket C junk in `build_finance_crosswalk.py`.** Add
      a build-time filter so `PROP_0_*` (zero-prop-number) and explicit
      stale-committee patterns don't pollute the `status='missing'`
      bucket. Tiny code change; makes the next audit cleaner.

- [x] ~~**Donor-sector classification.**~~ **DONE 2026-05-12.** Codex-
      blessed conservative scope: hand-curated `donor_name_canon` →
      sector lookup in `scraper/src/finance/donor_sectors.py`. 12-category
      taxonomy (Labor / Gig Economy / Tribal Gaming / Commercial Gambling
      / Healthcare / Real Estate / Tobacco / Utilities / Energy /
      Individual / Party-Political-org / Other). ~80 curated entries
      covering 100% of top-15 donors and 97% of marquee-fight donors
      (only ALG Polling — vendor, not a sector — left blank).

      Wired end-to-end (Codex round-7 catch — not just generate_insights):
      `FinanceDatabase.get_top_donors()` + `aggregate_for_measure()` both
      attach `donor_sector` per row; insights payloads
      (`top_donors_overall`, `repeat_donors`, `marquee_fights`) carry it;
      API endpoint replaces hardcoded `donor_sector=None` with real
      lookup; briefing pipeline picks it up automatically (already
      referenced `d.get('donor_sector')`).

      Frontend renders a small neutral pill chip next to each donor name
      in Module 3a / 3b lists and marquee-fight donor lists.
      Unclassified donors render without any chip.

      19 new tests covering: known donors return expected sectors,
      unknown returns None, all dict values are recognized sectors, PG&E
      variants all classify as Utilities, Tribal Gaming distinct from
      Commercial Gambling, sector flows through get_top_donors and
      aggregate_for_measure. 94/94 finance tests pass.

      Coverage caveat documented in module docstring: top-25 covers ~43%
      of total donor dollar volume in `finance_top_donors` per Codex
      measurement — NOT 95% as initially claimed. The scope is "prominent
      visible donors" not "majority of volume."

- [ ] **Per-campaign transaction table** for `get_contribution_breakdown`.
      Currently returns zero-buckets because v2 doesn't have
      transaction-level attribution. Flagged in
      [`scraper/src/finance/operations.py:147`](../scraper/src/finance/operations.py#L147)
      docstring. Future v2 data-layer extension.

- [x] ~~**Calendar-year aggregation view of the spending arc.**~~ **DONE
      2026-05-12.** Pill toggle in Module 2 switches between "By election
      cycle" (default) and "By calendar year." SQL lives in
      `FinanceDatabase.get_calendar_year_receipts()` for testability;
      reconciles exactly to election-year totals ($3.32B either lens).
      Codex round-5 review caveats addressed: copy describes data as
      "accepted weekly receipts," method note warns about week-boundary
      attribution (2007 / 2012 visibly affected), tooltip uses dynamic
      "active campaigns" / "measures with accepted receipts in this year"
      labels per mode, toggle handlers wired via `onclick =` (idempotent
      across re-renders). 4 new tests added: aggregation losslessness,
      collision-counts-one-measure, week-start-year boundary, status-
      filter defense in depth.

- [x] ~~**Pre-2010 statewide finance backfill.**~~ **RESOLVED BY AUDIT
      2026-05-12.** Post-matcher-v2 pre-2010 coverage is at 103 matched
      campaigns (essentially complete: all of 2000's 19 props, 11 in
      2002, the Schwarzenegger 2005 specials, 22 in 2006 including 8
      year-offset recoveries, 16 in 2008, 5 in 2009). Remaining gap is
      5 entries totaling $0.49M of edge cases: LA-municipal `PROP_1_2001`
      misclassified as statewide ($0.13M); two `PROP_127` filings from
      a non-qualifying initiative ("Life on the Ballot", $0.31M); one
      `PROP_54_2006` late filing for 2003's Prop 54 (needs offset=3,
      currently capped at 2; $0.02M); one mystery `PROP_98_2006` ($0.03M).
      Bumping MAX_YEAR_LOOKBACK to 3 for the PROP_54 case alone isn't
      worth the false-positive risk.

- [x] ~~**Deeper donor canonicalization + formatter edge cases.**~~
      **DONE 2026-05-12.** Codex-blessed conservative scope: legal-entity
      merges only, no parent-org grouping. Six clusters consolidated:
      M. Quinn Delaney (5→1, $6.77M), DaVita (2→1, $70.58M), Pechanga
      (3→1, $48.44M), Charles T. Munger Jr. (4→1, $60.17M with ambiguous
      "MUNGER, CHARLES T" left distinct), CAR Issues Mobilization PAC
      (9→1, $10.95M), Instacart/Maplebear (1→1, $17.69M). DoorDash +
      Instacart added to frontend brand-display map. JS formatter
      early-return removed so connective lowercasing fires on mixed-case
      strings ("Committee, Sponsored By CAHHS" → "Committee, sponsored
      by CAHHS"). 36 new parametrized tests including negative cases
      (other Delaneys, Mungers, parent CAR + National Realtors stay
      distinct, SEIU locals stay distinct). 75/75 finance tests pass.

      **SEIU UHW + structural dedup-gate fix — DONE 2026-05-12 (`9fb9dc0`).**
      Investigation of the PROP_8_2018 UHW pair revealed Gate 7 was keyed
      on `donor_raw` rather than the canonical name — donor canonicalization
      patterns were running but the dedup gate bypassed them. Added
      SEIU-UHW Nonprofit 501(c)(5) suffix-variant canonicalization and
      switched Gate 7 to key on `canonicalize_donor(donor_raw)`. Cascade
      caught additional CalAccess reporting-duplicates already covered by
      existing canonicalization: PROP_27_2022 DraftKings/FanDuel casing
      (−$35M), PROP_32_2012 Munger Jr name variants (−$20M), PROP_8_2018
      SEIU UHW (−$11.4M), Cal Apt Assn paired entries, etc. Total receipts
      $3.32B → $3.24B (−$78M); win rate 64.6 → 65.2%. Sentinels still pass.
      10 new tests (118/118 finance tests pass). Added SEIU-UHW Nonprofit
      501(c)(5) → Labor to `donor_sectors.py`.

- [x] ~~**Stance recovery**~~ **DONE 2026-05-12.** Item promoted from
      "residual 42 rows / $7K" to ~1,500 rows / $0.75M after matcher v2
      exposed PROP_4_2010's late-filed Planned Parenthood committees.
      Authoritative source check via CalAccess "Ballot Measure Committees
      linked to this Ballot Measure" view confirmed Planned Parenthood
      Affiliates of California at $8.83M oppose on Prop 4 (2008).
      Broadened the existing PROP_4_2008 override substring from
      "PLANNED PARENTHOOD ADVOCACY PROJECT LOS ANGELES COUNTY" to just
      "PLANNED PARENTHOOD" + added parallel PROP_4_2010 entry. Result:
      unknown_stance dropped 1,514 → 87 rows (94% reduction); PROP_4
      measure-level oppose rolled up $6.79M → $7.06M (+$0.27M); the
      remaining $0.43M of formerly-unknown was exact-duplicate rows
      previously hidden by the unknown_stance gate firing first. 8 new
      tests cover override fires on both campaign ids, per-campaign
      scoping prevents cross-campaign matches, regex patterns still
      work, ambiguous yes/no names stay unrecovered. Residual 87 rows
      / $0.05M (PROP_66_2006 F.A.C.T. sentencing campaign, Chico Chamber)
      stay quarantined — not worth per-case research.

- [x] ~~**Rewrite `scripts/evaluate_data_quality.py` for v2 schema.**~~
      **DONE 2026-05-12.** Codex-blessed rewrite of the Finance dimension
      (other 8 dimensions left intact — they weren't broken). Path now
      imports `FINANCE_DB_PATH` from `src/finance/schema.py` instead of
      hardcoding legacy. v1 checks rewritten for v2 schema: coverage
      (3 cuts — matched campaigns / distinct measures / 2000+ coverage%);
      no negative totals; summary integrity (top5/HHI in valid ranges);
      no orphan matched campaigns. Added Codex's dollar reconciliation
      check (summary vs crosswalk totals — strongest observability
      signal). Added quarantine reason distribution, stance distribution
      (including 0-stance "matched but all gates failed" cases), Bucket A
      recovery audit, and structured sentinel checks (per-sentinel
      min/max year + in-year %, explicit ≥90% threshold). Transaction-
      table-shaped checks (zero amounts, missing dates) intentionally
      absent — labeled in the report payload as
      "not_available_in_v2_until_per_campaign_transaction_table_exists".
      Live run: Finance dimension scores 100/100; report identifies 1
      matched campaign with 0 surviving stances (useful signal).

- [ ] **Expand finance coverage beyond 181 statewide propositions.** Modern-
      era gaps; local-ballot finance scoped out per panel deck.

- [ ] **Reconsider marquee fights placement** — keep in Finance panel vs
      promote to Key Findings #6. Open question from redesign plan.

### FEATURE

- [ ] **Per-card deep-link URLs.** Add hash routing so each measure modal
      has a unique URL (e.g. `index.html#measure=PROP_27_2022`, optionally
      `&tab=finance`). On page load, parse hash → open the matching modal
      and set the requested tab. On modal open/close, `history.replaceState`
      to keep URL in sync. Cards get `id="measure-{db_id}"` anchors for
      scroll-linking. Pure client-side; works on GitHub Pages. **Effort:
      ~30-60 min** (90 if polished with back-button state restore).
      Unlocks: shareable measure links, briefing prose deep-linking to
      modals, working-list items pointing at specific cards, faster
      "go look at this prop" chat workflow.

### DATA HYGIENE

- [ ] **Audit other dead/null fields in JS data blob.** The
      `campaign_finance` rip shed 313 KB; `research_status`,
      `research_depth`, etc. may have similar opportunities.

- [ ] **Methodology / corrections tracker doc.** Single place to
      acknowledge data-quality issues + methodology choices. (Asked for
      during the Topics panel work; never landed.)

### INSIGHTS PANELS

- [ ] **Decide whether to reintroduce the Close Calls panel.** Was pulled
      mid-redesign; vague "revisit" should resolve to keep-or-kill.

- [ ] **Rules panel follow-ups**: mobile labels, third landmark.

- [ ] **Topics panel further revisit.** Depends on classification gap fix.

- [ ] **Measure Types follow-up.** Specifics unclear; needs scoping pass
      before work.

### DATA

- [ ] **Fix topic classification gap.** ~75% of records bucket to "Other"
      because CEDA doesn't supply topic. Heavy: needs LLM classification
      pass. Also a likely prerequisite for the thematic-policy narrative
      work above.

- [ ] **Audit topic-flag accuracy in `ca_historical_measures`**.

- [ ] **Expand statewide-measure historical coverage.** Separate from
      finance backfill.

### BRIEFINGS

- [ ] **Resume summary regen at scale.** ~8,500 measures missing summaries.
      Path forward via Anthropic Batch API (~$30-50, needs API key) or
      chunked subagent runs (free via subscription, slower). Production
      script ready at `scraper/scripts/regenerate_summaries_v02.py`.

- [ ] **Surface new context layers in card/modal UI** (demographics,
      finance, election cycle, author history, cross-state, CPI).

- [ ] **Build multi-stage validator harness** as a generation-time gate
      (6-stage Codex-flavored version).

- [ ] **Brief bakeoff** applying summary lessons; include GPT-5.5 column.

- [ ] **Pre-generate research briefs** on curated subset.

---

## Closed by decision (don't re-add)

- ~~Geography Regions revisit~~ — explicitly dropped during Geography
  panel work ("let's just drop regions for now"). Keep county-level only.
- ~~Measures-DB ID reconciliation (2014/2016 soft duplicates)~~ — self-
  deferred until next refresh exposes blocking ambiguity.
- ~~CHANGELOG cosmetic refresh~~ — done 2026-05-04.
- ~~`extract_calaccess_finance.py --build-db` rewire~~ — done 2026-05-04.
- ~~Drop dead `measures.campaign_finance` column~~ — done 2026-05-04.

## Calendar / external waits (not actionable)

- CEDA 2025 raw file — download when published.
- LinkedIn / Twitter writeups — drafts ready; post when ready (user task).

---

## Reference docs

- [`docs/PROJECT_HISTORY.md`](PROJECT_HISTORY.md) — project narrative
  (snapshot-disclaimed for finance specifics; points readers at v2 docs).
- [`docs/DATA_PIPELINE.md`](DATA_PIPELINE.md) — pipeline architecture
  (snapshot-disclaimed for the Finance section).
- [`docs/KNOWN_ISSUES.md`](KNOWN_ISSUES.md) — data-quality issues with
  status tracking.
- [`scraper/data/finance/README.md`](../scraper/data/finance/README.md) —
  v2 finance schema, build pipeline, acceptance gates, current state.
- `plans/finance-rebuild-verification.md` (gitignored) — Phase A–F
  verification plan with Phase E follow-up flag table.
- `plans/finance-panel-redesign.md` (gitignored) — original 4-module
  redesign plan with deferred items + open questions.
