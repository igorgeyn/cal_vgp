# Codex: load and publish San Mateo (A5)

> **This is the step that changes what the public sees.** Everything
> before it was reversible: snapshots are immutable and additive, and
> the site never moved. This one writes to
> `scraper/data/ballot_measures.db` and regenerates the deployed
> artifacts.
>
> Work in the order below. The artifact diff in §7 is a **gate**, not
> a formality — the last time this project regenerated the site, the
> generator silently dropped a field from every record and the only
> thing that caught it was reading the diff.
>
> Self-contained; assume no session memory. Written 2026-08-31 against
> `main` after San Mateo was enabled (`04db0dc`).

---

## 1. Preconditions

Confirm each; stop and report if any fails.

- A **production** San Mateo snapshot exists under
  `prod/smc/2026-11-03/{snapshot_id}/` with its manifest written last.
- `python -m pytest tests/ -q -k "registrar or website"` from
  `scraper/` is green (239 at last run).
- Working tree clean, `main` up to date with origin.
- The deployed `index.html` and `measures-data.json` currently contain
  **20** registrar measures, all San Bernardino.

## 2. Parse the production snapshot — read-only

```
python scraper/scripts/parse_registrar_snapshots.py \
    --county=smc --election-date=2026-11-03 --env=prod
```

Expect **29 records, 29 unique IDs**, all prefixed
`REG_SMC_20261103_`. Document counts may exceed the fixture's 135/167
if San Mateo has filed since 2026-08-31 — **that is a finding to
report, not a failure to correct.** Never adjust an expectation to
match reality without saying so.

## 3. Dry-run the load, and read the plan

The loader defaults to dry-run; `--commit` is what mutates.

```
python scraper/scripts/load_registrar_measures.py <jsonl-path>
```

Report the planned actions before doing anything. What you should see
is **29 inserts and zero updates, zero deactivations**. San Mateo has
never been loaded, so anything touching an existing row means
something is wrong — most likely a collision with the 458 historical
CEDA `SAN MATEO` rows, which are a separate lineage and must not be
disturbed.

**If the plan contains any update or deactivation, stop and report.**

## 4. Two site fixes, before you regenerate

**4.1 — `LOCAL_COUNTY_ROADMAP` is stale and user-facing.**
[`generator.py:11021`](../../scraper/src/website/generator.py#L11021)
reads:

```js
const LOCAL_COUNTY_ROADMAP = [
    'San Bernardino', 'Los Angeles', 'Orange', 'San Diego', 'Riverside'
];
```

Uncaptured entries render to visitors as *"— not yet captured"*, so
the site is currently promising **Los Angeles**, which recon
established publishes only at or after Election Day, and omitting
Alameda, which is genuinely next. Replace with the counties we
actually intend to capture, in order:

```js
const LOCAL_COUNTY_ROADMAP = [
    'San Bernardino', 'San Mateo', 'Alameda', 'San Francisco', 'Contra Costa'
];
```

Santa Clara is deliberately absent: every one of its hosts hard-blocks
us at HTTP 403, and advertising it would be a promise we cannot
currently keep. Los Angeles, Orange, San Diego and Riverside are out
for the same reason — none is the next build. This list is display
only; it gates no behavior.

**4.2 — Confirm the regional measure renders sanely.** San Mateo's
regional transit measure has an intentionally empty `measure_letter`.
`createLocalMeasureCard` does
`getDisplayMeasureId(measure) || 'Local measure'`, so it should show
**"Local measure"** with jurisdiction *Public Transit Revenue Measure
District*. Verify that, and verify **no raw `REG_SMC_…` identity
string appears anywhere** in the generated HTML or JSON.

Do not try to improve that label here. "Regional Measure" would be
better and is San Mateo's own published section heading, but the
measure-group is not carried into the database today, so doing it
properly means schema work. It belongs with the cross-county regional
measure key, which is a separate task.

## 5. Commit the load

```
python scraper/scripts/load_registrar_measures.py <jsonl-path> --commit
```

`--commit` backs up before mutating. Follow the existing backup
naming convention, e.g.
`scraper/data/ballot_measures.db.bak.smc_load_<YYYYMMDD_HHMMSS>`.
**Confirm the backup file exists before continuing.**

## 6. Verify the load before regenerating anything

- **Layer 1 — prior state unchanged.** All **20** San Bernardino
  registrar measures are byte-identical to before the load: same IDs,
  same fields, none deactivated. This is the check that matters most.
- **Layer 2 — source reconcile.** Exactly 29 new `REG_SMC_` rows,
  matching the parsed JSONL one for one.
- **Layer 3 — spot trace.** Pick three measures — one composite
  (`Resolution, Full Text and Tax Rate Statement`), one of the four
  sharing the county packet, and the regional measure — and trace each
  from the snapshot through the JSONL into the database row.
- The **458 historical CEDA `SAN MATEO` rows are untouched**, and the
  new rows carry `data_source = SMC_County_Registrar`.
- Total measure count rises by exactly 29.

## 7. Regenerate, and read the diff

```
python scraper/scripts/generate_site.py
```

Omit `--output`. An explicit path is scratch-only; the default writes
both tracked pairs, which is the contract.

**Watch the log for degradation.** The `historical_context` step
fetches a sentence-transformers model over the network and **swallows
a failure into a warning**, then publishes a degraded artifact
anyway. That has already happened once on this project: a
regeneration silently dropped `historical_context` from every record,
and it was caught only by reading the diff. If you see that warning,
**stop — do not commit a degraded artifact.** Re-run once the model
is reachable.

Then read `git diff` on `measures-data.json` and `index.html` and
report:

- 29 measures added, **zero removed, zero modified** beyond the
  expected additions.
- No existing measure loses a field. Compare `historical_context`
  population before and after; a drop is the failure above.
- The stat "N of 58 counties" moves from 1 to **2**.
- The county dropdown offers San Bernardino and San Mateo as enabled,
  with the corrected roadmap as disabled entries.

## 8. Commit — and stage only the tracked pair

The generator writes **two** pairs. Only the **repository-root**
`index.html` and `measures-data.json` are tracked and published; the
byte-identical `scraper/` pair is a gitignored local preview.
**Never stage the mirror.** Name every file explicitly; do not
`git add .` — the repo carries many untracked data artifacts that
would otherwise be swept in, including the `.db.bak.*` file you just
created.

Then **ask before pushing**, and say plainly that pushing publishes
29 new measures to the live site.

## 9. Report

The dry-run plan and whether it was 29 clean inserts. Then the Layer 1
result, the artifact diff summary, whether the `historical_context`
warning appeared, and anything that differed from the fixture
contract.
