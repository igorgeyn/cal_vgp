# Codex: San Mateo round two — three fixes + the shared contract

> **Follow-up to the San Mateo build.** The build is good and its
> review passed the critical gate; these are the findings from that
> review. Three are small and specific. One is a refactor that should
> land before county #3.
>
> Self-contained; assume no session memory. Verified against the
> working tree on 2026-08-31, after the San Mateo build landed.

---

## 0. What the review verified, so you don't redo it

Confirmed good — do not change these:

- **San Bernardino's measure IDs are byte-identical** under the new
  `_origin_key(row, role_priority)`. A/B tested across three fixture
  scenarios including the cross-snapshot drift pair. The per-county
  `origin_role_priority` design is correct; SB's empty tuple falling
  through to the global `_ROLE_PRIORITY` is what preserves it.
- **Composites as one PDF repeated per role** is the right model. 135
  captured links → 167 role records reconciles exactly.
- **Casing variant handled** — `argument_for` 26 = 25 + 1.
- **Label census matches an independent live count** of the page.
- **The `/archival-document?document=` wrapper is unwrapped** and the
  target validated as a same-origin HTTPS PDF, keeping identity off a
  URL carrying a mutable `title` param. Good call; keep it.
- 235 tests pass; no SB or parser test expectation was modified.

Two things are known and deliberately **out of scope** — do not
"improve" them: the hard-coded `SMC_FORWARD_ANCHORS` November anchor
(San Mateo does not list upcoming elections, so it cannot be derived),
and `EXPECTED_GROUPS` requiring exactly four groups.

---

## 1. Hoist the shared contract into `contracts.py`

**This is the substantial one. Read the whole section before starting
— there is a trap in it.**

### The problem

`parser.py` — the shared, cross-county module — imports its types from
San Bernardino's modules:

```python
from .sb import CapturedMeasuresPage
from .sb_interpretation import (
    ExpectedDocument, MeasureRow, MeasuresPage, SbInterpretationError,
)
```

`county_config.py` does the same, and types its registry against them.
So San Mateo's extractor must return **San Bernardino's dataclass**.
`smc_interpretation.py` imports four symbols from `sb_interpretation`,
while `smc.py` *duplicates* the three captured dataclasses. Half
shared, half duplicated — the worst of both, and county #3 has no
good option.

### The trap

`SmcInterpretationError` subclasses `SbInterpretationError`, which
looks like something to clean up. **It is load-bearing.**
[`parser.py:405`](../../scraper/src/scrapers/registrar/parser.py#L405)
catches `SbInterpretationError` and converts it into a clean
`SnapshotValidationError`. San Mateo's failures reach that handler
*only* through that inheritance.

If you make `SmcInterpretationError` a plain `ValueError`, San Mateo's
unknown-label failures stop being caught and escape as uncaught
exceptions instead of clean validation errors — silently breaking the
fail-loud path in the one place this project cannot afford it. Do not
let that happen.

### The fix

The three captured dataclasses in `smc.py` are **field-for-field
identical** to `sb.py`'s — same names, types and order. This is a
pure move, not a reconciliation.

1. Create `scraper/src/scrapers/registrar/contracts.py` holding
   `CapturedDocument`, `CapturedMeasureRow`, `CapturedMeasuresPage`,
   `ExpectedDocument`, `MeasureRow`, `MeasuresPage`, plus a new
   `RegistrarInterpretationError(ValueError)` base.
2. Make `SbInterpretationError` and `SmcInterpretationError`
   **siblings** of that base — both subclass
   `RegistrarInterpretationError` directly, neither subclasses the
   other.
3. `parser.py` catches `RegistrarInterpretationError` and imports its
   types from `contracts`.
4. `county_config.py` imports from `contracts`.
5. `sb.py`, `sb_interpretation.py`, `smc.py` and
   `smc_interpretation.py` import from `contracts`; delete the
   duplicated definitions. Re-export where an existing import path
   would otherwise break.

**Keep the field names exactly as they are** (`column`, `table_row`,
`headers`). They are misnomers for a div-panel county and both
implementations annotate them as such, but renaming them touches
`origin_table_row`, which is persisted in `registrar_identities` and
needs a migration. That is a separate task; do not start it here.

**No county module may import another county module when you are
done.** That is the acceptance test.

## 2. `url_owners` is computed over the wrong set

[`parser.py:513`](../../scraper/src/scrapers/registrar/parser.py#L513)
builds document-URL ownership from `unmatched_lineages` only, then
treats a URL owned by exactly one entry as measure-specific evidence.

Because the override stage runs first, a reviewed override can consume
one owner of a genuinely shared packet URL — and that URL then looks
uniquely owned by a remaining lineage. A row carrying only the shared
packet could bind to it. This is the identity-misassignment class
closed in `5f1cd26`, so it should not be reachable at all.

Build ownership over **all** lineages, then restrict candidates to
unmatched ones. Add a regression test: a shared packet URL plus a
lineage override on one of its owners must not produce a match on the
shared URL.

## 3. The regional measure's letter is invented

[`smc.py:223`](../../scraper/src/scrapers/registrar/smc.py#L223) sets
`letter = "Regional Transit"` when the panel heading carries no
designation. San Mateo publishes no letter for this measure; the
string is synthesized from prose and will render as a measure letter
on a public site. This project's whole discipline is refusing to guess
— so either carry the absence honestly, or mark the value as derived.

Prefer the honest option unless something downstream truly requires a
non-empty letter. **Check before you choose** — `measure_letter` flows
into the loader and the site generator, so confirm what an empty or
null letter does to both, and say what you found.

Do **not** substitute Alameda's designation for it. Alameda publishes
the same measure as `Measure RTM`, but that is Alameda's label, not
San Mateo's.

Also fix the adjacent comment: it says "This four-county measure". It
is **five** — Alameda, Contra Costa, San Mateo, Santa Clara, and the
City and County of San Francisco, per the measure's own notice of
election and its ballot question (0.5% in four counties, 1% in San
Francisco).

**Context you should know but not act on:** that same measure will
arrive independently from at least three county scrapers in this
workstream, each minting its own `REG_{COUNTY}_{DATE}_{digest}`
identity. A shared regional key is being designed separately. Do not
build it here — just don't make it harder.

## 4. Verification

- **Re-run the San Bernardino identity A/B and report the result.**
  This is the gate. Parse the SB fixtures before and after your
  changes and confirm the measure IDs are identical in all three
  scenarios: the single lettered snapshot (`20260814T035115Z` /
  `measures_2026_1103_lettered.html`), and the drift pair
  (`20260727T170014Z` / `measures_2026_1103_mixed.html`, then
  `20260814T034259Z` / `measures_2026_1103_lettered.html` at
  `schema_version=2`). `tests/test_registrar_parser.py::_put_snapshot`
  builds these against a `LocalArtifactStore`.
- Confirm San Mateo still yields **29 measures, 135 captured links,
  167 role records, 29 unique IDs**.
- A test asserting the parser catches a San Mateo interpretation
  failure through the shared base — the trap in §1, pinned.
- `python -m pytest tests/ -q -k "registrar or website"` from
  `scraper/`: **235 or more, zero failures.** The wider legacy suite's
  18 failures are pre-existing and not yours.

## 5. Constraints

- **Do not** add `smc` to `ENABLED_COUNTIES`. Enablement is a separate
  reviewed step.
- **Never** write to `scraper/data/ballot_measures.db`; never
  regenerate or commit deployed site artifacts.
- Never `git add .`; `pytest` runs from `scraper/`; Windows-compatible.

## 6. Report

The A/B identity result first. Then: what moved into `contracts.py`
and what re-exports remain, how the exception hierarchy ends up, what
you found about empty measure letters downstream and what you chose,
and anything you deferred.
