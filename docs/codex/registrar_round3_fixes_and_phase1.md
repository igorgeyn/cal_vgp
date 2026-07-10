# Codex review: round-2 fix verification + Phase 1 (SB scraper) pre-review

> **For Codex:** Two-part engagement, round 3 of the registrar
> pipeline series. Part A verifies that your round-2 findings were
> applied correctly (you reported them; we applied them; now check
> our work). Part B pressure-tests the Phase 1 plan — the first
> REAL county scraper — before any design is committed.
>
> **Self-contained request.** Prior sessions may have hit session
> limits; assume no carried context. Rounds 1 and 2 live at
> `docs/codex/registrar_pipeline_infra_review.md` (design) and
> `docs/codex/registrar_phase05_impl_review.md` (implementation) if
> you want the framing, but everything needed is below.

## State of the world (30 seconds)

CalBallot registrar pipeline, Phase 0.5 (framework) is **complete
and verified in production** as of 2026-07-09: Cloudflare R2 bucket
live, GH Actions cron + dispatch + push triggers all green against
the real bucket, 101 registrar tests. No real county scraper exists
yet — the NoOp scraper validated the wiring. Phase 1 (San
Bernardino first) is next.

Round-2 fixes landed in commit `6207efb` ("apply Codex round-2
findings"); `git show 6207efb` gives the full diff.

## Part A — verify the round-2 fixes

For each, confirm the fix is correct AND complete (no missed code
path), in these files:
`scraper/src/scrapers/registrar/{storage,base,runner}.py` +
`scraper/tests/test_registrar_{storage,base,runner}.py`.

1. **Blocker — prod CI local-storage fallback.** `make_store()` now
   raises `StoreConfigurationError` (naming missing vars) when
   env=prod AND `GITHUB_ACTIONS` is set AND any R2 var is missing.
   Dev-in-CI and prod-outside-CI keep the local fallback. Run
   manifest carries `store_backend: r2|local`. *Scrutinize: is the
   guard condition airtight? Can any CI path still reach
   LocalArtifactStore with env=prod?*

2. **Snapshot existence = manifest existence.** `list_snapshots` +
   snapshot-level `exists()` in BOTH stores key on manifest.json
   presence. R2 `list_snapshots` filters `{sid}/manifest.json` keys
   (no more CommonPrefixes); snapshot `exists` is a manifest HEAD.
   *Scrutinize: any remaining API that can surface an orphan?*

3. **Immutability enforcement.** SnapshotWriter rejects duplicate
   filenames; `open_snapshot` rejects completed snapshot IDs but
   allows retry-over-orphan (deliberate self-heal);
   `finalize(extra=)` can't override core fields; `manifest.json`
   reserved at the store boundary. *Scrutinize: the
   retry-over-orphan choice — any way it corrupts a manifest?*

4. **Retry-After.** Honored on 429/5xx, delta-seconds + HTTP-date,
   NaN-guarded, clamped to [0, `retry_after_cap_seconds`=300].
   *Scrutinize: parsing edge cases; is the 300s cap sane?*

5. **Per-request + per-hop politeness.** Rate limit inside the
   retry loop; robots fetch itself rate-limited; redirects followed
   manually (`allow_redirects=False`, cap `max_redirects`=10) with
   per-hop robots check + rate limit. *Scrutinize: hop handling —
   307/308 semantics, Location edge cases, cross-origin correctness.
   Note the Playwright path deliberately delegates redirects to the
   browser — acceptable?*

6. **Storage path validation.** `_validate_component` on county /
   election_date / snapshot_id / filename / run_id in both stores;
   hostile `ArtifactRef.filename` rejected on read. *Scrutinize:
   bypasses? Is rejecting ":" too strict or not strict enough on
   Windows?*

7. **Empty `--counties=enabled` guard.** Exits nonzero once real
   (non-noop) scrapers are registered; still exits 0 today (noop
   only). Plus the deferred nit, done early: Playwright `goto()`
   returning None now raises FetchError.

## Part B — Phase 1 pre-review (no design doc exists yet; this IS the input)

Phase 1 target: `SbScraper(CountyRegistrarScraper)` for San
Bernardino — recon-confirmed cleanest of the five counties. Read
`docs/plans/registrar_manifest.md` (SB section + cross-county
takeaways) for the recon findings. Shape:

- URL pattern `elections.sbcounty.gov/elections/{year}/{mmdd}/measures/`;
  cross-election landing at `/elections/measures/`.
- Measures page is a structured HTML table: Letter | Jurisdiction |
  Measure Description | Analysis (PDF link) | Arguments (4 PDF
  links) | Percentage to Pass.
- Plan: enumerate elections, fetch each measures page, save
  page.html + linked analysis/argument PDFs into one snapshot per
  (election_date), then flip `ENABLED_COUNTIES` to include "sb" and
  the workflow arg from `--counties=noop` to `--counties=enabled`.
- Parser stage (artifacts → normalized JSONL) is a SEPARATE
  deliverable after the scraper — scraper only captures raw truth.

Questions we want opinions on before designing:

1. **Election enumeration.** Options: (a) scrape the `/elections/`
   index page and derive {year}/{mmdd} pairs; (b) maintain a static
   list of known election dates in code/config; (c) hybrid — static
   anchor list + index-page discovery for new ones. Which failure
   mode is worse for a weekly cron: missing a new election (b) or
   scraping garbage when the index page changes shape (a)?
2. **Backfill vs. forward-only.** Scrape all historical elections
   SB publishes on day one, or current/upcoming only and backfill
   deliberately later? Immutable snapshots make backfill safe
   anytime; is there a reason to front-load it?
3. **Change detection.** Weekly re-scrapes of the same election
   create a new snapshot each time (immutable design). Should the
   scraper skip re-download when content is byte-identical
   (ETag/Last-Modified or sha compare against the latest snapshot),
   or is "always snapshot, dedup at parse time" cleaner? Cost is
   trivial either way — what's the better audit story?
4. **PDF link hygiene.** Analysis/argument links may be absolute,
   relative, or off-domain. Per-hop robots+rate-limit is already in
   the base class; anything else the scraper contract should pin
   down (e.g., filename derivation from link text vs URL basename —
   note storage rejects path separators in filenames)?
5. **Failure semantics within a county.** If the measures page
   fetches but 2 of 9 PDFs 404: complete-with-gaps snapshot
   (finalize with per-artifact status), or fail the county? The
   run-manifest schema currently only knows county-level
   success/failed.
6. **What are we not thinking of** before the first real HTML
   flows? (Encoding, pagination on the measures table, elections
   with zero measures, the 2026 primary page being populated late,
   etc.)

## Calibration

Part A: verification pass — bullet verdicts per finding
(applied-correctly / gap found, with severity). Part B: design
taste + practical experience; opinionated recommendations over
option menus. Don't review code outside the listed files.
