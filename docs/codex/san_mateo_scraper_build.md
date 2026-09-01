# Codex: San Mateo County scraper (county #2)

> **For Codex:** Build the project's second live county scraper.
> Follow [`docs/setup/registrar_developer_guide.md`](../setup/registrar_developer_guide.md)
> — it encodes what San Bernardino cost six review rounds and three
> production drift events to learn. **Read it before writing code.**
>
> Self-contained; assume no session memory. Facts verified 2026-08-31
> against the live page.

---

## 1. Why San Mateo, and what is already known

Recon across five counties (`docs/plans/registrar_manifest.md`)
established that **San Bernardino is not unusual in publishing ahead**
— current-election coverage is reachable this cycle. San Mateo won the
recommendation on forward publication, document richness, and
structural simplicity, with no anti-bot barrier.

**Election page (verified live, 2026-08-31):**
`https://smcacre.gov/elections/november-3-2026-statewide-general-election`
— 278 KB, HTTP 200, server-rendered, polite UA sufficient.

**29 measures**, letters running single through double: D–Z plus AA,
BB, CC, DD, EE.

**139 PDF links**, of which ~134 are measure documents:

| Label | Count |
|---|---:|
| Impartial Analysis | **29 — every measure** |
| Primary Argument in Favor | 25 |
| Resolution and Full Text | 24 |
| Primary Argument Against | 18 |
| Rebuttal to Argument Against | 17 |
| Rebuttal to Argument in Favor | 16 |
| Resolution, Full Text and Tax Rate Statement | 4 |
| Primary Argument In Favor *(casing variant)* | 1 |

This is richer than San Bernardino, which has 19 arguments-for but
only 4 against. San Mateo has genuine both-sides coverage.

## 2. Four facts that will shape the build

These were found by direct inspection and are **not** in the recon
document. Treat them as constraints, and confirm each against a
pinned fixture before designing around it.

**2.1 — There are no tables.** The page has **zero `<table>` elements**
and 104 `<div>`s. San Bernardino's extractor identifies its measures
table by header set and scopes traversal by table ownership; **none of
that transfers.** This is a panel structure and the extractor is a
genuine rewrite, not an adaptation. You will need an equivalent
ownership discipline for whatever container delimits a measure — the
*reason* for that rule still applies (see 2.4).

**2.2 — Composite documents break the one-role model.** *"Resolution
and Full Text"* (24×) and *"Resolution, Full Text and Tax Rate
Statement"* (4×) are **single PDFs carrying multiple roles**. San
Bernardino ships each role as its own file, so the existing model
assumes one document → one role. Decide deliberately: a role *set*
per document, a composite role name, or one document record repeated
per role. Whatever you choose, a later parser must be able to answer
"does this measure have a tax rate statement?" correctly. **State the
choice and its rationale in the design.**

**2.3 — A label casing variant already exists.** *"Primary Argument in
Favor"* (25×) versus *"Primary Argument In Favor"* (1×). Under a
case-sensitive label map that single measure fails. San Bernardino
normalizes with `_norm_text(...).lower()` before matching; do the
same, deliberately, and cover it with a test. Expect more variants
over time — this county has 29 measures filed by 29 different
jurisdictions.

**2.4 — Non-measure PDFs share the page.** Roster of Candidates,
Randomized Alphabet Drawing (State and Local), List of Offices with
Extended Candidate Filing Period. A global anchor scan sweeps these in.
This is the same trap as San Bernardino's Form 9600 statement-by-
proponents link, which is why extraction must be scoped to measure
containers rather than the page.

## 3. Required approach

**Fixtures before code.** Pin the November 2026 election page and a
representative sample of PDFs into
`scraper/tests/fixtures/registrar/smc/` with `.meta.json` sidecars,
and write the extractor against those bytes. San Bernardino's fixtures
overturned its design on contact with reality — the plan assumed five
document roles and the real page had seven. Also pin the archive/index
page used for election enumeration.

**Pure extraction.** `extract_*` functions take bytes plus the page
URL and return typed rows and document descriptors. No network, no
storage, no clock. This is what lets the parser replay stored
snapshots forever.

**Capture, then interpret.** The pipeline was refactored (`edb2978`)
so the scraper downloads every linked document **without classifying
it**, and role assignment happens in the offline parser. Follow that
split: a new document label must not be able to red the weekly cron.
Register San Mateo in `county_config.py`.

**Base-class primitives only.** `fetch()` and
`open_snapshot()`/`SnapshotWriter` handle politeness, retries,
robots.txt, per-hop redirect policy, and manifest-last snapshots. Do
not touch `requests` directly. If a primitive is missing, say so
rather than working around it.

**`county_name` must match the database.** Verify the exact existing
string for San Mateo in `ballot_measures.db` rather than guessing, or
new rows will not group with the 458 historical ones.

## 4. Fail loudly, in the right place

Unknown labels, duplicate labels, and cardinality violations belong to
the **parser** now. Structural failures — measure containers not
found, malformed panels, fetch failures, non-PDF content, off-origin
redirects — still fail **capture**.

Do not relax a rule to make a failure go away. San Bernardino's strict
cardinality rule caught five tax rate statements about to be filed as
impartial analyses.

## 5. Verification

- Fixture-pinned extraction tests asserting the exact contract: 29
  measures, the label census in §1, and the per-label URL distribution
  (that census is how the San Bernardino `AIF_` filing anomaly was
  found).
- A synthetic schema-failure matrix, mirroring
  `test_registrar_sb.py`.
- Clock-controlled enumeration tests if San Mateo uses an anchor
  lifecycle.
- Integration against `LocalArtifactStore` with injected session,
  clock, and sleep. **No test may touch the network or the live
  database.**
- A live smoke: `python scraper/scripts/run_registrar_pipeline.py
  --counties=smc --env=dev`.
- Existing suite green: `python -m pytest tests/ -q -k "registrar or
  website"` from `scraper/`. The wider legacy suite has 18 known
  pre-existing failures — not yours.

## 6. Constraints

- **Do not** add San Mateo to `ENABLED_COUNTIES` or flip the workflow
  in this task. Going live is a separate reviewed step, as it was for
  San Bernardino.
- **Never** write to `scraper/data/ballot_measures.db`; never
  regenerate or commit deployed site artifacts.
- Polite User-Agent is non-negotiable, with rate limiting. This
  project intends to scrape these county sites weekly for years.
- Update `docs/plans/county_status.md` when the build lands.
- Never `git add .`; `pytest` runs from `scraper/`;
  Windows-compatible.

## 7. Report

State: the container structure you used in place of a table, your
decision on composite documents and why, the label map, election
enumeration approach, what fails in capture versus parse, fixture
inventory, and anything you assumed or deferred.
