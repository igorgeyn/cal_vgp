# F1 release after the review corrections — September 8, 2026

This supersedes the September 7 candidate's historical-context values and
post-load verification instructions. The document/identity release scope is
unchanged. Igor approved the reviewed candidate on September 8. Production
loading, backups, identical-snapshot replay and the actual paired-build gate
have passed. Release `ec89711` is published and verified at
https://cal-vgp.igorgeyn.com/.

## Approved production execution

Evidence is in the ignored `_ready/production/` directory: `dry-runs.json`,
`execution.json`, `build.log`, and `verification.json`. This is the actual
production execution, distinct from the two rehearsals below. All source/code
and sealed-reference hashes matched before loading; enrichment inputs stayed
unchanged afterward. The gate verified 12,361 active measures, 272 document
roles, 239 displayed links and 49 measures with documents. Both county loads
created backups and identical-snapshot replay left the database byte-identical.

Production artifact SHA-256:

- `index.html`: `c7b8c1cb3ece1bfd95923fbf1db6e8a6a3eead7e278681c28d7fec27cbd3d40f`
- `measures-data.json`: `f35c845f6e983250ca83acce7018ed5cc5a06d08064a6a5bee9334f415449c72`

The release commit uses `[skip ci]` to avoid the push-triggered registrar
scrape. Only Pages ran for this commit; its deployment succeeded at
2026-09-08 14:11:13 UTC (run `34236586413`). No county scrape was triggered.

Both public files returned HTTP 200 and match their committed bytes. Git
normalizes the generated HTML's 14,301 CRLF line endings to LF; that is the
only difference from the production file above. Its committed/served SHA-256
is `8d1cabf15232cc121de1286ffb04880d848511b0de6c79e487862c49e912bf53`.
The JSON hash is unchanged. `production/deployment-verification.json` records
this exact production-to-commit-to-served comparison.

Live Chromium checks passed at desktop (1440px) and mobile (390px): SB J/I,
SMC R/regional document modals, September 7 capture dates, keyboard navigation,
clearing documents on historical measures, Finance content, and untruncated
context statistics in both counties. There were no JavaScript page errors.
Reports and screenshots are under `production/`. No county documents were
fetched during these checks. Publication is complete; refresh handoff is next.

## Corrections

Historical context now excludes unresolved normalized outcomes before counting
the sample, calculating the pass rate, choosing its earliest year, and applying
the minimum of five outcomes. Raw outcome flags, vote shares, and election
records are not changed or inferred.

| County/category | Previous sample/rate | Corrected sample/rate |
|---|---|---|
| SB GO Bond | 90 / 67% | 87 / 69% |
| SB Ordinance | 71 / 56% | 70 / 57% |
| SB Property Tax | 16 / 19% | 15 / 20% |
| SB Sales Tax | 31 / 55% | 30 / 57% |
| SMC GO Bond | 105 / 85% | 102 / 87% |

The SB sales-tax cohort now starts in 2004 rather than 2000, because its lone
2000 row has an unresolved normalized outcome. Counts of recorded passes are
unchanged. Relative to the existing root pair, 21 existing context panels
change, six remain equal, and Measure I gains its reviewed sales-tax context:
28 panels total. Measure I retains its actual two-thirds threshold.

The cards show the rate, sample count, and date range in a compact line. The
shared note explicitly defines the sample as recorded pass/fail outcomes for
the same county/type, says voting rules and purpose are not matched, and says
the comparison does not predict this election. No historical thresholds were
invented. Card height can grow above its 120px minimum so the regional measure's
wrapped label does not clip the statistic on mobile.

## Verification suitable for production

`scraper/scripts/verify_official_documents_release.py` has two commands:

- `seal`: record exact hashes of separate, frozen pre-release baseline files,
  reviewed database/site files, and normalized inputs. Refuses to overwrite an
  existing manifest. This does not constitute an external approval.
- `check`: require explicit actual database/site paths, compare them against
  the sealed evidence, and optionally check the independent mirror pair.
  The tool opens SQLite in read-only mode and never initializes or loads it.

The gate checks all measure fields and database tables against the reviewed
load, forbids unexpected registrar fields as well as historical edits, verifies
active IDs and exported fields, reconciles every normalized document role, and
independently calculates context counts/rates with SQL. Finance, Insights,
recommendations, and topic payloads must match the frozen baseline. Actual HTML
must match the reviewed HTML apart from the bounded build date. The mirror must
be a separate pair of files and match byte-for-byte.

Only timestamps justified by the specific reviewed load may differ. They must
fall inside the declared load/build window, and exported load timestamps must
equal the actual database values. The 129 pre-existing null `last_seen_at`
values may be filled at build time inside that same window; this exception
does not apply to capture dates or arbitrary historical timestamps. Actual and
sealed file hashes are checked again at completion. The report records hashes
of the actual output files for subsequent deployment verification.

## Rehearsal and evidence

Current evidence is under
`scraper/data/registrar_recon/f1_release_20260908_ready/` (ignored local files).
Earlier `f1_release_20260908/` and `f1_release_20260908_final/` bundles are
superseded UI iterations; their sealed files were not overwritten.

- `baseline/`: frozen copy of production SQLite and the existing root pair.
- `reviewed/`: fresh backed-up load and full CLI build.
- `actual/`: a second, independent fresh load and full CLI build; the verifier
  reads these files as the post-load target, not the reviewed files.
- `sb.jsonl`, `smc.jsonl`: unchanged pinned September 7 normalized inputs.
- `review-manifest.json`, `verification.json`: sealed evidence and comparison.
- Each build's `execution.json` and `build.log`: exact load/build times and logs.
- `browser-context.json` and context screenshots: both counties at desktop and
  mobile widths, including horizontal and vertical clipping checks.
- `browser-verification.json` and document screenshots: actual candidate
  document grouping, dates, keyboard navigation, clearing and Finance checks.

Both builds use the real CLI and real enrichment inputs, with the cached model
offline. Only the two default output destinations are redirected into scratch
directories; the production paired writer executes. No finance, semantic,
recommendation or Insights provider is mocked. Each load creates a backup;
same-snapshot replay performs no write.

The registrar/site/context suite passed **293 tests**. Subsequent focused
gate/site checks passed **31 tests**, including an additional mirror-alias
rejection test (294 distinct tests across the runs). Tests cover missing
outcomes, all-unknown samples, the minimum-sample boundary, unexpected public
fields, removed null fields, actual-output corruption, stale capture dates,
timestamp bounds, wrong target paths, and tampered sealed references.

## Unchanged release scope

- SB snapshot `20260907T172437Z`: 20 measures, 15 source-field updates,
  105 document roles. No inserts/deactivations of measures.
- SMC snapshot `20260907T172914Z`: 29 unchanged measure rows, 167 document roles.
- 272 roles yield 239 displayed links on 49 measures.
- 12,361 active measures; integer and canonical IDs preserved.
- Five semantic historical-context payloads, existing summaries/titles, and
  unrelated enrichments are preserved. Only the documented local-context
  corrections are intentional analytical changes.
- Remote main was rechecked on September 8 and remains
  `04db0dc1ed6298d7e784e191fb9eb9f904098ac1`. Publishing also delivers the 29 SMC
  measures already committed locally but absent from remote main.

## Execute only after production/publication approval

Recheck source/enrichment hashes against `source-hashes.json`, code hashes and
remote main. Any intervening source or code change needs a new comparison.
Record the process-local ISO time immediately before the first load and after
the final build; the loader uses that clock for its naive timestamps.

Dry-run and then load the pinned SB and SMC JSONLs into
`scraper/data/ballot_measures.db`, confirming the exact rehearsed plan and each
backup. Generate the normal root and scraper pairs with `HF_HUB_OFFLINE=1` and
`TRANSFORMERS_OFFLINE=1`, without `--output` or `--deploy`. Then run:

```powershell
python scraper/scripts/verify_official_documents_release.py check `
  --manifest scraper/data/registrar_recon/f1_release_20260908_ready/review-manifest.json `
  --db scraper/data/ballot_measures.db `
  --site index.html `
  --mirror scraper/index.html `
  --started-at <actual-load-start-local-ISO-time> `
  --finished-at <actual-build-finish-local-ISO-time> `
  --report <new-production-verification-report.json>
```

The placeholders must be replaced by measured values, not the rehearsal's times.
The command reads actual production paths while the baseline/reviewed files
remain fixed. Do not run the old September 7 `E/verify.py` after production
changes. Its assumptions are appropriate only to its original rehearsal.

Review the actual output and stage only the explicit task code/tests/docs and
root HTML/JSON pair. Include new untracked task files; exclude databases,
backups, scratch evidence, ignored mirrors, and unrelated work. Push within
approval, verify the Pages deployment and served pair against the actual
production report hashes, and spot-check the live modals.

The corrective review itself used only isolated copies. The later approved
production execution is recorded above. Refresh handoff remains next after
publication.
