# Runbook: the registrar cron went red

> **When to use this:** the weekly `registrar-pipeline` GitHub
> Actions run failed. This has happened three times (2026-08-10,
> 2026-08-24, plus launch-week surprises) at a cadence of roughly
> once per two weeks per county, and each was resolved in about one
> session. This is a routine maintenance event, not an incident.
>
> **The reassuring part:** every failure so far was the pipeline
> refusing to guess about something new on a county website. No
> failure has ever corrupted stored data, because a snapshot without
> a manifest is invisible to everything downstream.

---

## 0. What a failure means

The scraper enforces a **complete-capture contract**: it stores
every document a county advertises, or it stores nothing and fails
loudly. When a county publishes a document type the extractor has no
role for, or restructures its table, the run aborts *before* writing
a manifest. Partial artifacts stay orphaned in the bucket and no
parser will ever see them.

So a red cron means: **the county changed something, and we have not
yet decided what it means.** The job is to decide deliberately.

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
| `'analysis' cell has 2 links (row N)` | A cell now carries two documents where the contract allowed one |
| `unexpected link in 'letter' cell (row N)` | A cell that had no document role now has a link |
| `unknown <column> link label 'X'` | A recognized cell carries a document type we have no role for |

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
`scraper/src/scrapers/registrar/sb.py`. Cardinality is zero-or-one;
a second link raises rather than being dropped.

**Role by label** — use when one cell can carry several document
types distinguished by their link text. The Analysis cell carries
both "Impartial" and "Tax Rate Statement". Add to the relevant map
in `LABEL_ROLE_COLUMNS`. Unknown or duplicated labels raise.

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

Then add tests that assert the *exact* contract: row count, role
census, and — valuably — the per-role URL-prefix distribution.

**Why the prefix census matters.** On 2026-08-24 that assertion
caught a county filing anomaly: San Bernardino City USD's
*"Impartial"* link points at `AIF_SBCUSD.pdf`, an argument-in-favor
filename. Roles come from the label, so it is correctly recorded as
an analysis — but had roles been keyed on URL prefixes, it would
have been silently misfiled. Record anomalies like this in the
fixture README and `docs/KNOWN_ISSUES.md`; never "fix" the county's
data silently.

```bash
cd scraper && python -m pytest tests/ -q -k "registrar or website_output"
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
