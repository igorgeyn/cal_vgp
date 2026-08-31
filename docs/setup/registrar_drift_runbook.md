# Runbook: the registrar cron went red

> **When to use this:** the weekly `registrar-pipeline` GitHub
> Actions run failed. This has happened three times (2026-08-10,
> 2026-08-24, plus launch-week surprises) at a cadence of roughly
> once per two weeks per county, and each was resolved in about one
> session. This is a routine maintenance event, not an incident.
>
> **The reassuring part:** every failure so far was the pipeline
> refusing to guess about something new on a county website. Capture
> now preserves unrecognized document types before interpretation;
> structurally incomplete captures still have no manifest and remain
> invisible downstream.

---

## 0. What a failure means

The pipeline separates **capture** from **interpretation**. The live
scraper stores every linked document in the identified measures table,
along with its row, column, label, and URL. It does not assign roles.
A new document type is therefore preserved in an immutable snapshot;
the offline parser then fails rather than guessing what it means.

A red capture cron still means a structural or transport failure:
the table is missing or ambiguous, a row is malformed, a fetch was
exhausted, or an advertised PDF was not a PDF. A red parse means the
county published a document whose role rules need review. In either
case, diagnose deliberately; for parse drift, the source bytes are
already safe.

---

## 1. Diagnose (2 minutes)

```bash
gh run list --workflow registrar-pipeline --limit 5

gh run view <RUN_ID> --log 2>&1 \
  | grep -iE "registrar\.|FAILED|Traceback|raise |Error:" | head -20
```

The error message names the failure precisely. The three seen so far:

| Message | Meaning |
|---|---|
| `'<column>' cell has N links (row N); zero or one allowed` | The offline role rule expects a single-link cell |
| `unrecognized document column '<column>' (row N); labels=[...]` | Captured links came from a column with no role rule |
| `unknown <column> link label 'X' (row N)` | A recognized cell carries a document type with no role |

Others the contract can raise: `expected exactly 1 measures table`
(page restructured), `malformed row` (cell count changed),
`SbEnumerationError` (the election index changed shape or lost a
known election).

---

## 2. Inspect the live page

Never guess from the error alone — look at what the county actually
published. A short throwaway script beats reading raw HTML:

```python
import sys, requests
from bs4 import BeautifulSoup
sys.path.insert(0, "scraper")
from src.scrapers.registrar.sb import (
    EXPECTED_HEADERS, _direct_cells, _find_header_row,
    _norm_text, _owned_links, _owned_rows,
)

UA = ("cal-vgp-registrar-scraper/0.1 "
      "(+https://github.com/igorgeyn/cal_vgp; contact: igorgeyn@gmail.com)")
r = requests.get(URL, headers={"User-Agent": UA}, timeout=30)
soup = BeautifulSoup(r.content.decode("utf-8", "replace"), "lxml")
# ... find the table, walk rows, print each cell's link labels + hrefs
```

**Always use the polite User-Agent.** San Diego returns 403 without
it, and hammering a county site from a diagnostic script is exactly
the behavior the politeness defaults exist to prevent.

What you are trying to learn:
- What is the **link label**? (Labels are authoritative for roles.)
- What is the **URL filename prefix**? (Conventional, *not*
  authoritative — see §5.)
- **How many rows are affected**, and is it spreading week over week?

---

## 3. Classify the change

**A new document type** — the common case. The county started
publishing something real (a tax rate statement, a notice of
election). Add a role. Go to §4.

**A structural change** — the table gained a column, moved to
`<thead>`, changed a header string. The extractor's header contract
must be updated deliberately, and this is higher-risk: re-read
`docs/plans/registrar_phase1_sb.md` §3 before touching it.

**An enumeration change** — the election index changed shape or
dropped a known election. Check the anchor lifecycle first: an
anchor whose election date has passed retires automatically, so a
missing *past* election is not an error. A missing *active* anchor
is.

**A transient source error** — the page 500s or returns truncated
HTML. Re-run the workflow before changing any code:
`gh workflow run registrar-pipeline --ref main`.

---

## 4. Add a document role

Two shapes exist, and picking the right one matters:

**Role by column** — use when the link's label carries no role
information. The Jurisdiction cell's label is the jurisdiction name;
the Letter cell's label is just "Y". Add to `COLUMN_ROLES` in
`scraper/src/scrapers/registrar/sb_interpretation.py`. Cardinality is zero-or-one;
a second link raises rather than being dropped.

**Role by label** — use when one cell can carry several document
types distinguished by their link text. The Analysis cell carries
both "Impartial" and "Tax Rate Statement". Add to the relevant map
in `LABEL_ROLE_COLUMNS` in `sb_interpretation.py`. Unknown or
duplicated labels raise.

> **Do not** relax a rule to make a failure go away. The cardinality
> and unknown-label rules are what caught all three drift events. A
> rule that guesses would have silently misfiled documents instead.

---

## 5. Pin a fixture, then test

Fixtures are the contract. Capture the current page **before**
writing the fix, so the test proves behavior against real bytes:

```bash
# writes bytes + a .meta.json sidecar into
# scraper/tests/fixtures/registrar/sb/
python <capture script> "measures_2026_1103_<event>.html=<URL>"
```

Then add capture tests for exact row/column/label/link retention and
interpreter tests for the role census and — valuably — the per-role
URL-prefix distribution. Include a regression proving capture still
succeeds with the new role removed, while offline parsing fails with
the row, cell, label, and violated rule.

**Why the prefix census matters.** On 2026-08-24 that assertion
caught a county filing anomaly: San Bernardino City USD's
*"Impartial"* link points at `AIF_SBCUSD.pdf`, an argument-in-favor
filename. Roles come from the label, so it is correctly recorded as
an analysis — but had roles been keyed on URL prefixes, it would
have been silently misfiled. Record anomalies like this in the
fixture README and `docs/KNOWN_ISSUES.md`; never "fix" the county's
data silently.

```bash
cd scraper && python -m pytest tests/ -q -k "registrar or website"
```

---

## 6. Smoke, ship, restore

```bash
# 1. live smoke against the real site, local store
python scraper/scripts/run_registrar_pipeline.py --counties=sb --env=dev

# 2. commit + push (push triggers a dev CI run on registrar paths)

# 3. restore production — the failed cron left no snapshot, and the
#    page keeps changing, so do not wait for next Monday
gh workflow run registrar-pipeline --ref main
gh run watch <RUN_ID> --exit-status
```

Then verify the prod snapshot landed: list snapshots for the
election, read the manifest, and sha-verify one artifact through
`R2ArtifactStore` (`env="prod"`).

---

## 7. Close the loop

- Update `docs/WORKING_LIST.md` — the drift log lives in
  "Recently shipped" and the clean-run streak gates the backfill.
- Add a `LESSONS_LEARNED.md` entry **only if** the event taught
  something new. Three drift events have produced two lessons; the
  third was the same lesson repeating, which is itself informative.
- If the county's data was wrong (not just new), record it in
  `docs/KNOWN_ISSUES.md`.

---

## Appendix: what has actually happened

| Date | Trigger | Resolution |
|---|---|---|
| 2026-08-10 | Analysis cell carried two links | Analysis became label-keyed; `tax_rate_statement` role added. Caught a latent misattribution: 5 rows carried *only* a tax rate statement and would have been filed as impartial analyses. |
| 2026-08-24 | Letter cell carried a link | Letter joined `COLUMN_ROLES` with role `notice`. Nine roles now possible. |

Neither corrupted stored data. Both were fixed within a session,
including a pinned fixture and tests.
