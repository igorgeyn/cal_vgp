# Codex action-plan request: Phase 5 step 2b follow-ups

> **For Codex:** This is a planning request, not a review. You just
> reviewed commit `bec2abe` (see `phase5_step2b_review.md` in this
> directory) and flagged 5 issues. We want your help thinking through
> the order of operations, scope per fix, and what's blocking-to-ship
> vs nice-to-have before we move to Phase 6 (final verification +
> CHANGELOG + methodology docs).

---

## Your 5 findings (verbatim recap)

**1. Combined donor metrics are not truly "all donors" for the v2
monetary slice.** `operations.py:1015` calls
`aggregate_for_measure(... donor_limit=10_000)`, but v2
`finance_top_donors` is already materialized as top 20 per
campaign/stance — 207 v2 campaign/stance slices are at that cap. So
combined `top5_share`, `hhi`, `get_combined_top_donors`,
`top_donors_overall`, and `repeat_donors` can omit monetary donors
below the v2 top-20 cutoff, even though denominators use full
monetary totals. HHI systematically low; a donor whose v3 total
plus below-top-20 monetary total would change ranking can be
undercounted. Either fix from a fuller v2 donor aggregate or
document these as "visible/top-donor aggregates," not exact all-
donor concentration metrics.

**2. Exact-name donor merging creates visible split donors in the
new public lists.** Merge key is raw `donor_name_canon` in
`operations.py:1145` and `1156`. Live PROP_27_2022 support: FanDuel
appears as both `FanDuel Sportsbook (Betfair Interactive US)` and
`BETFAIR INTERACTIVE US LLC D/B/A FANDUEL GROUP, INC`; FBG also
split. PROP_22 has `UBER TECHNOLOGIES, INC` and
`UBER TECHNOLOGIES INC`. Affects displayed top donors + concentration
metrics. Not a total-dollar blocker, but user-visible.

**3. Calendar-year n_measures is wrong in the combined helper.**
`operations.py:1257` uses `max(v2_count, v3_count)` instead of the
union of measure IDs. Dollars reconcile, but `n_measures` undercounts
in 7 years: 2001, 2003, 2005, 2007, 2009, 2010, 2013. Example: 2005
reports 20, true union is 25. Fix by querying distinct
`(year, measure_db_id)` from both sources and unioning in Python,
similar to `_build_finance_supplements`' annual logic.

**4. n_transactions in combined summary is v3-only but exposed as
if it were combined.** `operations.py:1062` sets `n_transactions`
from v3 only; v2 has no transaction count. API exposes it on
`FinanceSideResponse` at `server.py:793`. Live DB has 287 mixed
v2+v3 summary rows exposing a partial count. Return None, rename to
`non_monetary_transactions`, or omit it from combined summary
responses.

**5. Some public/generated copy is still v2-era.**
`generate_insights.py:1615` still says "independent expenditures,
in-kind contributions, and loans are not included."
`generator.py:12099` displays `measure_count` as "campaigns," but
it is now measures. Not arithmetic bugs but undermine the
methodology update.

## Context we're navigating

**Severity ladder we're working with:**
- **Material** (Finding #1): real numbers shift on the static site
  if fixed. HHI / top5_share / repeat_donors visible.
- **UX** (Finding #2): visible to anyone who looks at PROP_27_2022 /
  PROP_22 modals + the new "flow_types" field. Numerically the
  combined total is still correct, but the donor card shows two
  entries that are obviously the same entity.
- **Tooltip** (Finding #3): `n_measures` is in chart tooltips. Off
  by ~25% in some early years.
- **Honesty** (Finding #4): semantically misleading field. Easy fix.
- **Copy** (Finding #5): cheap, embarrassing-if-shipped.

**Constraints / preferences:**
- Igor's project pattern is conservative: prefer None / explicit
  "not applicable" over wrong-looking numbers.
- The static site is already live with the new numbers. Each fix is
  another regen of `insights.json` + `index.html`.
- Phase 6 (final verification + CHANGELOG + methodology docs) is
  the next chunk after these fixes. Phase 6 is mostly
  documentation work.
- The Codex review arc has had 4 rounds so far (1 review for step
  1, plus this step 2b review). Igor pays per-round so we don't
  want to burn unnecessary reviews.
- v3 doesn't yet ingest monetary contributions — the combined-method
  stitch is the workaround. A separate phase ("v3 monetary ingest")
  would simplify all of these but is bigger scope.

## What we're asking you for

### A. Prioritized order

Given the 5 findings, what's the right order of operations? Options
we've considered:
- **Ship #4 + #5 first** (cheap + obviously right), then **#2 + #3
  as a follow-up commit**, then **#1 last** as the biggest behavioral
  shift. Three commits, each reviewable independently.
- **Bundle all 5 into one "round-4 fixes" commit**, single review.
- **Split material vs cosmetic**: #1 + #2 + #3 as "arithmetic /
  shape" commit, #4 + #5 as "copy / API" commit. Two commits.

What's your call?

### B. Finding #1 — concentration metrics from a partial donor pool

Two approaches Codex outlined:

**B.1.** Fix from a fuller v2 donor aggregate: extend
`aggregate_for_measure` (or add a sibling) to read directly from
the v2 raw transactions table (or wherever the full set lives) so
the merged donor list is exhaustive. Concentration metrics become
exact.

**B.2.** Document as "visible/top-donor aggregates" not exact: leave
the math as-is, change the field semantics in the docstring + API
response model + methodology copy.

Trade-offs we see:
- (B.1) is the right answer numerically, but requires understanding
  what v2 raw data exists. Looking at `rebuild_finance_db.py`, the
  pipeline drops to the per-donor SUM before storing in
  `finance_top_donors` (capped at top-20). So getting a fuller list
  means re-running an aggregation against the v2 raw cleaned CSV or
  the v1 measure-committee-link table — both feel out of scope for
  step 2b.
- (B.2) is honest but means the methodology copy reads as a caveat
  ("HHI computed against top-20 monetary + all v3 donors") which is
  awkward.

What would you recommend? Is there a third path we're missing
(e.g., recompute HHI from full v2 by querying `finance_summary`'s
top5_share/hhi columns directly per campaign + recomputing across
the merge)?

### C. Finding #2 — donor canonicalization drift

Two approaches we see:

**C.1.** **Small high-dollar alias pass**: add a curated dict
mapping known cross-source variants to a single canonical name
(FanDuel / Uber / FBG and any others spotted in top-N donor lists
for the marquee fights). Apply at merge time. Scope: ~10-20
entries to cover all visible cases.

**C.2.** **Generic normalization at merge time**: e.g., strip
punctuation + trailing INC/LLC/CORP variations + uppercase. Risk:
false-positive merges (different entities normalizing to the same
key).

**C.3.** **Punt**: keep the split, add a methodology note that
donor canonicalization is partial across v2 + v3.

Trade-off intuition: C.1 covers the visible cases without
over-merging risk. C.2 is sketchier — donor canonicalization is
notoriously error-prone (Codex round-6 of Phase 4 caught us on this
when we tried generic patterns).

What's your read? Specifically: is C.1 sufficient for the marquee
fight cases you saw? And how should the curated alias dict relate
to the existing `src/finance/canonicalization.py` (or wherever v2's
canonicalization lives)?

### D. Finding #3 — n_measures fix

Codex suggested "query distinct (year, measure_db_id) from both
sources and union in Python, similar to `_build_finance_supplements`'
annual logic."

That sounds straightforward but requires changing
`get_calendar_year_receipts` (v2) and `get_calendar_year_receipts_v3`
to return per-(year, measure_db_id) sets instead of counts. Or we
could compute the union INSIDE the new `get_combined_calendar_year_receipts`
helper by going to the flow tables directly.

What's your preferred shape? Add a new helper, or modify the
existing methods?

### E. Finding #4 — n_transactions semantics

You suggested three options: (a) Return None, (b) Rename to
`non_monetary_transactions`, (c) Omit from combined summary
responses.

Which would you recommend? Igor's preference is "honest over
clever." (b) seems most informative if the metric is useful at all;
(c) is cleanest if it isn't.

### F. Finding #5 — copy cleanup

Two strings to fix. Are there others you spotted that I should
hunt for proactively? (E.g., the "campaigns" / "measures"
terminology appears in lots of places.)

### G. Testing posture

For each of the 5 fixes, what test additions would you require
before shipping?

For #1 (concentration metrics): can we even write a test that
catches the "missing low-rank donors" case hermetically? Or is this
inherently a live-data assertion?

### H. Phase 6 readiness

After these fixes land, the WORKING_LIST has Phase 6 next: final
verification + CHANGELOG + methodology docs. Is there anything from
this review you'd want documented in Phase 6 that we wouldn't
naturally capture in commit messages?

## What we want back

A short action plan (under 800 words) that addresses:
1. Recommended commit ordering for the 5 fixes.
2. For each fix: which option you'd take and why.
3. What test additions to require.
4. Anything to surface in Phase 6 docs that's not obvious.
5. Any 6th issue you'd flag now that you've thought through the plan
   (sometimes new things surface in the planning pass).

Plain prose, no need to format as a formal plan doc. We trust your
calibration from rounds 1-4.
