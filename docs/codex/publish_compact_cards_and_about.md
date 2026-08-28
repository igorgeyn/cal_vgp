# Codex: reconcile and publish the compact cards + About promotion

> **For Codex:** Finish the in-flight compact-card work, reconcile it
> with a committed About-modal change, verify, and **publish to the
> live site**. This regenerates deployed artifacts — read §4 before
> committing anything.
>
> Self-contained; assume no session memory. State verified 2026-08-27.

---

## 1. Exact starting state

`HEAD` is `164cdc6`. Deployed artifacts (`index.html`,
`measures-data.json`, `sitemap.xml`, `use-calballot/index.html`,
`measures/*.html`) were last regenerated at `a5518ca` and therefore
reflect **neither** of the two changes below.

**Committed but not yet published — `164cdc6`:**
The About modal's "Who uses CalBallot?" section moved from fourth
position to second (directly after the intro), and its inline link
became a button styled `.about-section a.about-use-cta` in the
primary gold. No prose changed. **Preserve this exactly** — it is
already in your working tree via HEAD.

**Uncommitted, in flight (yours):**
```
 M docs/plans/local_measures_widget_redesign.md
 M scraper/scripts/generate_site.py
 M scraper/src/website/generator.py
 M scraper/tests/test_use_calballot_page.py
 M scraper/tests/test_website_upcoming.py
?? scraper/src/website/local_measure_context.py
?? scraper/tests/test_local_measure_context.py
```
This is the compact card variant per
`docs/codex/compact_local_measure_cards.md`. The redesign plan's
status note says it is implemented and scratch-verified; finish
anything outstanding, then proceed.

**Both changes touch `generator.py`.** Confirm the About promotion
survives: the modal's section order must be intro → *Who uses
CalBallot?* → Background → Features → Data Pipeline, with the button
present. Consider asserting this in a test so it cannot silently
regress.

## 2. Finish and commit the source work

1. Complete the compact-card implementation.
2. Full suite from `scraper/`:
   `python -m pytest tests/ -q -k "registrar or website or use_calballot"`.
   The wider legacy suite has 18 known pre-existing failures (string
   DB paths, `Statewide` county default) — not yours.
3. Commit **source only** first, separately from artifacts. Name files
   explicitly; never `git add .`.

## 3. Regenerate — and the trap that must not be repeated

From `scraper/`, the same sequence `make website` uses:

```
python scripts/generate_insights.py
python scripts/generate_site.py --force
```

**Do not pass `--output`** — that is scratch-only and will not write
the deployed pair.

> ### ⚠ The `historical_context` degradation trap
>
> `generate_site.py` builds `historical_context` for pending measures
> using a sentence-transformers model **downloaded from the Hugging
> Face Hub**. When that download fails, the exception is caught, a
> warning is logged, and generation **continues with a silently
> degraded artifact** — the field vanishes from every record that
> should have it.
>
> This happened during the 2026-08-27 publication and was caught only
> because the artifact diff was reviewed. Re-running succeeded.
>
> **Required:** confirm the run logs
> `Added semantic historical context to 5 pending measures`
> (the 4 statewide 2026 measures plus Prop 50). If it logs a warning,
> or a count other than 5, **re-run before doing anything else.** Do
> not commit artifacts from a degraded run.

## 4. Review the artifact diff BEFORE committing

`measures-data.json` is ~35 MB. Do not commit it blind. Extract the
currently deployed copy and compare structurally:

```
git show HEAD:measures-data.json > ../old_measures.json
```

Then verify:

- **Record count unchanged at 12,332.** No load happened, so any
  delta is a bug.
- **Zero added, zero removed** records.
- **`historical_context` present on exactly 5 records**, and on
  **zero** registrar rows (`data_source == 'SB_County_Registrar'`).
- **No dropped schema keys.** New keys are expected from the compact
  card work (e.g. `local_measure_type_short`); dropped keys are not.
- Field-level drift on pre-existing records should be explicable —
  timestamp churn and genuinely new fields only.

Report the diff summary in your write-up.

## 5. Verify the rendered artifacts before pushing

Serve the repo root and drive it headless:

- **Local measures band is now compact** — report measured card height
  versus the previous ~230px.
- **Statewide carousel unchanged** — still exactly 4 cards.
- **About modal**: section order as in §1, button present, resolves to
  `/use-calballot/`.
- **`/use-calballot/` still loads**, still makes no data-bundle or
  chart-library request.
- Measure detail pages under `measures/` still resolve.
- **Zero page errors.**

## 6. Commit and push the publication

Stage explicitly. Expected: `index.html`, `measures-data.json`,
`scraper/data/insights.json`, and — only if genuinely regenerated —
`sitemap.xml` and `measures/*.html`.

**Never stage** `scraper/index.html` or `scraper/measures-data.json`;
they are the gitignored local mirror. `scraper/data/ballot_measures.db`
is also gitignored — the deployed artifacts carry the data.

Then push to `main`.

## 7. Constraints

- **Do not modify `scraper/data/ballot_measures.db`.** No load is part
  of this task; the 20 SB measures are already in it.
- Static output only; no framework, no runtime external requests.
- Publishing goes through `generate_prepared(..., output_paths=[...])`;
  `test_website_output_contract.py` asserts root and mirror copies are
  byte-identical. Keep that contract.
- Windows-compatible; `pytest` runs from `scraper/`.

## 8. Report

State: what the compact card height came out at, the artifact diff
summary, the `historical_context` count from the generation log, the
headless verification results, exactly which files you staged, and
anything you assumed or deferred.
