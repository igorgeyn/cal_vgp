# Codex: enable San Mateo in production (A4)

> **The rollout step San Mateo's build and round two both deferred.**
> Small change, real consequence: it starts weekly production scraping
> of a county government website under this project's name.
>
> **This does NOT publish anything.** Enabling writes immutable
> snapshots to R2 and touches nothing else. The database and the live
> site stay exactly as they are — parse → load → publish is A5, a
> separate reviewed step. Do not do it here.
>
> Self-contained; assume no session memory. Verified against `main`
> at `57c516d` on 2026-08-31.

---

## 1. Preconditions — confirm before changing anything

These are already true; confirm rather than assume, and stop if any is
not.

- `main` is at the round-two commit, working tree clean.
- `python -m pytest tests/ -q -k "registrar or website"` from
  `scraper/` is green (239 at last run). The wider legacy suite's 18
  failures are pre-existing and unrelated.
- `smc` is registered in `runner.REGISTRY` and in
  `county_config.COUNTY_CONFIGS`, and is **absent** from
  `ENABLED_COUNTIES`.
- San Mateo's fixture contract still reconciles: **29 measures, 135
  captured links, 167 role records, 29 unique IDs.**

## 2. The change

**2.1** [`runner.py:59`](../../scraper/src/scrapers/registrar/runner.py#L59):

```python
ENABLED_COUNTIES: tuple[str, ...] = ("sb", "smc")
```

**2.2** [`test_registrar_runner.py:53`](../../scraper/tests/test_registrar_runner.py#L53)
currently asserts `"smc" not in runner.ENABLED_COUNTIES`. That guard
exists so this cannot happen by accident, and it has done its job.
**Replace it with a positive assertion** that both `sb` and `smc` are
enabled — do not simply delete it. The suite should keep failing if
someone changes the production set without meaning to.

**2.3** [`registrar_pipeline.yml`](../../.github/workflows/registrar_pipeline.yml)
carries a stale comment: *"Production set: ENABLED_COUNTIES in
runner.py (SB as of Phase 1)."* Update it.

While you are there, one more stale comment on the **Upload
normalized JSONL** step: *"Parser stage doesn't exist yet (Phase 1);
ignore until then."* The parser has existed since `7861bb0`. Fix the
comment; do not change the step's behavior.

## 3. What pushing this will set off, on its own

Know this before you push — it is not a surprise, it is a designed
pre-flight, but you should be watching for it.

The workflow triggers on **push** to `scraper/src/scrapers/registrar/**`,
which this change touches. That push run will:

1. Scrape **both** counties to the **dev** R2 prefix
   (`R2_ENV: dev` on push), not prod. Harmless, and it is the first
   real two-county run of the pipeline.
2. Run `verify_registrar_identity.py`, which replays the five
   immutable **prod** San Bernardino snapshots and compares IDs to the
   20 reviewed production values. This gate runs on push only.

**If the identity gate fails, stop and report — do not proceed to
§4.** It would mean San Bernardino's live measure IDs no longer
reproduce, which is a data-integrity problem that outranks this
rollout entirely.

Note that the gate is San-Bernardino-only by construction (`COUNTY =
"sb"`, `REQUIRED_SNAPSHOT_COUNT = 5`). San Mateo has zero production
snapshots, so no equivalent gate can exist for it yet. Do **not**
generalize the script in this task — flag it as follow-up work for
once San Mateo has a snapshot history worth pinning.

## 4. First production capture

Do not wait for the Monday cron. San Mateo is still filing —
San Bernardino's document count went 16 → 105 across five weeks — and
every week without a capture is a week of the filing record that is
gone.

Trigger `registrar-pipeline` via **workflow_dispatch** with
`counties=smc`.

Use `smc` rather than `enabled` deliberately: this is San Mateo's
first production capture, and isolating it means a failure is
unambiguous. The Monday cron will exercise the real two-county
`enabled` path a week later, which is the right order. Manual dispatch
and cron share the prod concurrency group, so this cannot overlap a
scheduled run.

## 5. Verify the production snapshot — read-only

- The run manifest reports 1 county attempted, 1 succeeded.
- A new prod snapshot exists under
  `prod/smc/2026-11-03/{snapshot_id}/`, with the manifest written
  **last** (that ordering is what signals completeness).
- Manifest `pdf_counts.expected` equals `saved` equals **135**, and
  every referenced artifact is present.
- Parse the **real production snapshot** offline and confirm it
  reconciles with the fixture: **29 measures, 167 role records, 29
  unique measure IDs**, all prefixed `REG_SMC_20261103_`.
- The regional transit measure carries an **empty** `measure_letter`,
  jurisdiction `Public Transit Revenue Measure District`.
- Live counts may legitimately exceed the fixture if San Mateo has
  filed documents since 2026-08-31. **A difference is a finding, not a
  failure** — report what changed rather than adjusting anything to
  match.

If capture or parse fails, follow
[`registrar_drift_runbook.md`](../setup/registrar_drift_runbook.md)
and report. Do not relax a rule to make a failure go away.

## 6. Constraints

- **Do not** load into `scraper/data/ballot_measures.db`. Not with the
  loader, not by hand.
- **Do not** regenerate or commit `index.html` or
  `measures-data.json`. The published site must be byte-identical when
  you are done.
- Do not push to `origin/main` without confirming — except that this
  change only takes effect once pushed, so **ask before pushing** and
  say plainly that pushing starts the dev run in §3.
- Never `git add .`; `pytest` runs from `scraper/`.

## 7. Report

The identity gate result first. Then: the production snapshot id, its
manifest counts, the offline parse reconciliation against the fixture
contract with any differences called out, and anything you deferred.
