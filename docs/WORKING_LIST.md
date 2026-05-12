# CalBallot Working List

> Snapshot: **2026-05-06**. Branch: `main`. Last shipped: commit `fcd1345`
> (Finance v2 rebuild + Insights Finance panel redesign + cleanups), pushed
> to `origin/main` on 2026-05-04.
>
> This is the canonical resume point. Memory in `.claude/projects/...` is
> per-machine and won't follow you — start here when picking up on a new
> machine.

---

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

      **Two small follow-ups discovered post-impl:**

      - [ ] Annual-receipts attribution: recoveries get counted in their
            CalAccess year (e.g. PROP_4_2010 in the 2010 bar of the
            spending-arc chart) instead of the actual election year (2008).
            $1.9M total spread across 5 years — small. Either reattribute
            in `build_finance_insights` or accept as a known quirk.
      - [ ] Modal-lookup determinism: each recovery shares a `measure_db_id`
            with the corresponding exact-year campaign. `_load_finance_data`
            keys by `str(measure_db_id)` so one campaign overwrites the
            other; on-cycle currently happens to win via SQLite insertion
            order, but this is brittle. Add `ORDER BY election_year` to
            `get_all_campaigns` and `resolve_campaign` to lock in the
            on-cycle-wins behavior.

      **Remaining ~$1.81M of expected Bucket A recovery is dropping at
      the stance gate** (PROP_4_2010 alone has 1,427 unknown_stance rows
      / $0.70M from committees like "Planned Parenthood Advocacy Project").
      Captured under the stance-recovery item below — now meaningfully
      bigger scope than the "residual 42 rows" framing implied.

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

- [ ] **Donor-sector classification.** ~12 prominent donors hand-curated
      lookup, or LLM pass. Sector field is currently null for all 517
      donors in the v2 top-donors table. Enables tech / labor / gambling
      / healthcare $ aggregation. Likely prerequisite for the
      hot-button-donor narrative work above.

- [ ] **Per-campaign transaction table** for `get_contribution_breakdown`.
      Currently returns zero-buckets because v2 doesn't have
      transaction-level attribution. Flagged in
      [`scraper/src/finance/operations.py:147`](../scraper/src/finance/operations.py#L147)
      docstring. Future v2 data-layer extension.

- [ ] **Calendar-year aggregation view of the spending arc.** Alternative
      cut to election-year. Defer until per-week attribution is trusted
      (Codex catch from Module 2).

- [ ] **Pre-2010 statewide finance backfill.** v2 coverage is thin
      pre-2010 (1999–2008 has a handful of measures). **Narrowed by the
      audit above:** most pre-2010 misattribution should resolve once
      Bucket A's matcher fix lands. Genuine pre-2010 gaps (e.g. PROP_0_*
      junk excluded) appear smaller than initially feared.

- [ ] **Deeper donor canonicalization** + formatter edge cases. Known
      variants: M. Quinn Delaney, SEIU/hospital, DAVITA, Pechanga, Munger,
      CAR. Formatter polish: post-comma "Sponsored" lowercasing; expand
      brand-display map beyond DaVita/FanDuel/DraftKings/JPMorgan/YouTube/
      eBay.

- [ ] **Stance recovery for residual 42 rows / $7K** (Chico Chamber, etc.).
      Tiny dollars, low priority.

- [ ] **Rewrite `scripts/evaluate_data_quality.py` for v2 schema.**
      Currently still pointing at legacy DB with TODO marker.

- [ ] **Expand finance coverage beyond 181 statewide propositions.** Modern-
      era gaps; local-ballot finance scoped out per panel deck.

- [ ] **Reconsider marquee fights placement** — keep in Finance panel vs
      promote to Key Findings #6. Open question from redesign plan.

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
