# Part 2: complete release candidate and private recovery

**Status:** complete candidate and private recovery verified; production and
published files are unchanged. See the
[sealed evidence and R2 receipt](statewide_part2_evidence_20261003.json).
Part 2's publication and served-site checks remain open.

**Recommendation:** review this combined Part 1/Part 2 candidate next, then
publish it once concrete blockers are resolved. Do not add county expansion,
card redesign, topic classification, or a new finance ingestion to this release.
Those would consume the remaining October 5 window without improving the
corrected slate or access to the two counties' official documents.

## What changed

The standalone page builder now requires `--site-dir`, rejects unsafe IDs and
document URLs, and refuses to replace an existing page set or sitemap. Every
page comes from the same export as the explorer. County pages show the existing
grouped document model, including multiple roles on a single packet link,
capture dates, county hosting, and a stable `/#m=<id>` explorer link. Mobile
source URLs wrap; document links have visible keyboard focus and darker text.

The real site CLI accepts `--strict`. Missing or failed finance, Insights,
recommendation metadata, research projection, or semantic context aborts a
release build. Legitimate records with no relevant context remain valid.
Strict builds do not initialize title-generation providers. A local model path
can be supplied, and the recovery driver uses the bundled model with downloads
disabled. The default development mode retains its previous fallback behavior.

New tools:

- `scraper/scripts/build_release_bundle.py`: build from an explicitly frozen
  workspace into a new directory; preserve all input hashes and DB contents.
- `scraper/scripts/verify_release_bundle.py`: exact pages/sitemap/assets,
  document grouping, explorer targets and local-link validation.
- `scraper/scripts/recovery_bundle.py`: seal a private directory or restore into
  a fresh destination, verifying the archive and every file.
- `scraper/scripts/materialize_recovery_sources.py`: reconstruct all county
  snapshots from the archive's deduplicated, verified source objects.
- `scraper/requirements-release.txt`: explicit model dependencies; the private
  archive also records all installed package versions and the model revision.

The Part 1 corrected database is logically unchanged. A SQLite backup can alter
file headers; its Part 2 digest differs from the original Part 1 file, and the
whole-database preservation gate verifies its content against the baseline.
The old candidate and intermediate Part 2 builds are retained separately.

## Accepted source vintage

The 23 statewide source artifacts remain the September 13 captures. Bounded
October 3 reads of the
[qualified list](https://www.sos.ca.gov/elections/ballot-measures/qualified-ballot-measures)
and all 14 linked voter-guide proposition pages confirm the same November
slate, withdrawal notice, titles and descriptions. Title capitalization,
whitespace and curly apostrophes are normalized for comparison; descriptions
remain case-sensitive. The new 2028 sections are outside this release.

The existing production R2 captures were read and fully replayed, without
starting a scraper or a new capture:

| County | Latest stored snapshot checked | History replayed | Records | Document roles | Reader-content changes |
|---|---|---:|---:|---:|---:|
| San Bernardino | `20260928T192225Z` | 10 snapshots | 20 | 105 | 0 |
| San Mateo | `20260928T192608Z` | 5 snapshots | 29 | 167 | 0 |

Keep the accepted September 7 loaded vintage. The newer captures have the same
identities, reader fields, document URLs and document hashes. Rechecking an
unchanged file does not justify relabeling the older loaded capture as new.

All **236 distinct county document URLs** returned HTTP 200/206 and a PDF
signature. The health check deduplicates requests while retaining all measure
associations, uses the project's identifying User-Agent, robots policy and
two-second per-host interval, checks redirects, and reads at most 1 KiB per URL.
There were no unresolved responses. This proves current PDF responses, not
byte-for-byte equality of the complete live PDFs with the archived versions.
The full archived files were separately verified against their manifests.

## Validation and review locations

Scratch root: `scraper/data/statewide_recon/20261003_part2/`.
The reviewable site is `capsule/candidate-final/site/`. Use a local HTTP server,
not `file://`, because the explorer fetches its JSON:

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory scraper/data/statewide_recon/20261003_part2/capsule/candidate-final/site
```

Open `http://127.0.0.1:8765/`. A representative county document page is
`/measures/12420.html`; San Mateo's checked page is `/measures/12442.html`.
The withdrawn record remains `/measures/1.html` and `/#m=1`.

Evidence includes the strict real build, **81 passing focused tests** plus two
additional source-materialization cases, the
expected missing-model failure, exact preservation of historical/finance/
editorial data, all **12,372 detail pages**, **12,374 sitemap URLs**, and **239
grouped document links on 49 measures**. All local links are checked. Browser
checks cover both viewports, all 14 proposition modals, typed searches,
withdrawal routes/status, representative Finance, and county document pages
with keyboard navigation and explorer links. External requests are blocked in
those browser tests; live county probes are a separate report.

The browser rehearsal found and fixed a mobile source-URL overflow. A first
recovery test also exposed Windows ZIP-path normalization in the test harness;
the unsafe-path check now tests that normalization explicitly. The post-restore
source comparison initially compared a tuple with a list; normalization fixed
the comparator, and the source replay was rerun independently. The sealed ZIP
retains that dated preparation script as evidence of the first attempt; use
the final post-seal replay report/checker stored alongside the archive. The
documented restore, rebuild and source-materialization entry points are
unaffected. Intermediate
outputs are not the release candidate. Refer to the final evidence manifest.

## Recovery boundary

Igor selected the **existing private R2 bucket under a separate recovery
prefix**. No further storage approval is needed. The package contains both the
pre-change baseline and corrected candidate, real finance and semantic inputs,
code, source evidence, identity/scope state, and file manifests. Credentials
remain outside the package; the only `.env` is a comment-only placeholder.

Read [the recovery runbook](statewide_part2_recovery_20261003.md). The rehearsal
restored all **25,223 files**, rebuilt using restored inputs and model, and
verified SQLite integrity/foreign keys, **272 document-role joins** and **181
finance joins**. All 12,372 public records match, and 12,380 public files are
byte-identical; sitemap URL membership is also identical. The only JSON
difference is the 129 legacy null
`last_seen_at` timestamps generated at build time; source DB rows remain intact.
The archived site itself restores exactly. Sitemap build dates may differ on
a later-day rebuild.

All **1,464 county source files** were reconstructed from 268 unique objects;
both counties' full histories replay to exactly the same accepted records.
The **907,462,456-byte** archive was uploaded to private bucket
`cal-vgp-registrar-raw`, under
`recovery/20261003-part2/f0e016922367350b466bbe1ec2f8cd6c29edff06c5f432e1e28c40151df322c9/`.
Its independently downloaded copy has the same SHA-256:
`f0e016922367350b466bbe1ec2f8cd6c29edff06c5f432e1e28c40151df322c9`.
The verification receipt is dated October 3 at 23:16 Pacific (October 4 UTC).
No ACL, public-access setting or production capture object changed.

The rehearsal uses the installed Python environment; a fresh OS/package install
is not claimed. Optional AI chat, browser DuckDB, external map/CDN services,
external font rendering and credential recovery remain outside this check.

## Production promotion and rollback gate

No production load, Git commit, push, Pages deployment or live rollback occurs
in this preparation batch. Previous F1 approval is not sign-off on this release.
Use [the independent review prompt](../codex/statewide_part2_review.md).

After review and release approval:

1. Compare HEAD, intended source changes, accepted manifests and all production
   hashes. If anything drifted, reconcile on a fresh copy and rerun affected gates.
2. Establish a maintenance window: stop all DB/site writers and confirm no
   outstanding jobs or handles. Inspect actual SQLite WAL/SHM/journal state.
   Make a fresh consistent backup; never delete sidecars to satisfy a hash check.
3. Promote the reviewed corrected database and complete site together under
   that writer exclusion. The existing reconciler intentionally refuses direct
   production mutation; do not disable that guard. Use a reviewed cutover step.
4. Verify the production DB/public projection, synchronize the scraper mirror
   HTML/JSON/use page, and stage only the reviewed code/docs and complete public
   bundle. Inspect staged paths; unrelated untracked data must not be included.
5. Publish one reviewed Git revision, avoiding unintended registrar workflow
   execution. Verify the served main pair, statewide and county detail pages,
   sitemap, document destinations, deep links and representative Finance.
6. Record the actual release revision and served hashes, and preserve an
   accepted-state recovery receipt. If verification fails, retain failure
   evidence and restore the matching baseline DB/site under the same writer
   exclusion; publish a revert commit rather than rewriting shared history.

An offline restore is not a production cutover rehearsal. The concrete cutover
and served checks above remain gates, not completed work.

## Next work and effort

Proceed to Part 3 only after publication establishes the accepted baseline.
Its first task is a bounded compare-and-review refresh command that records
capture, parser, load and publication status separately. Follow with the
election-date/status transition work in Part 4; October 5 is still a reader
deadline, not permission to claim unfinished operational work is complete.

This batch used one Igor storage decision. Agent execution spans source checks,
implementation, real builds, browser checks and recovery; report timestamps
provide the actual chronology. No reliable human/agent hour total was recorded.
