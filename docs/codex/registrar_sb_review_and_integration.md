# Codex: SB parser/loader review + opportunity analysis + integration plan

> **For Codex:** Three tasks in one engagement, in this order:
> **(A)** review the just-built parser/loader for defects, **(B)** an
> opportunity analysis — what this data makes possible that we have
> not yet considered — and **(C)** a phased, verifiable plan for
> putting it on the live website, of which you implement only
> Phase 0 (a local, non-deployed render).
>
> Part B is not a formality. The instruction from the project owner
> was explicit: catch mistakes, **and make sure we are not leaving
> anything on the table** — uses of the data, visualizations,
> connections to what is already on the site.
>
> **Self-contained.** Assume no prior-session context. Facts below
> were verified against the repo on 2026-08-14; verify anything
> load-bearing yourself — the repo is the truth.

---

## 1. Situation

**CalBallot** (`https://calballot.com`) — searchable database of
California ballot measures, 1911–present. Python pipeline → SQLite
(`scraper/data/ballot_measures.db`, 12,365 measures) → static site
generator (`scraper/src/website/generator.py`) → GitHub Pages. No
server, no framework. Read `/CLAUDE.md` first for rules of
engagement, then `docs/WORKING_LIST.md`.

A weekly cron scrapes San Bernardino County's registrar site into
immutable, checksummed R2 snapshots (live since 2026-07-27, six
external review rounds, 173 tests). A parser and loader now turn
those snapshots into database rows — built yesterday, verified, and
committed at `7861bb0`. **Nothing has been loaded into the live
database and nothing is on the website yet.** That is the decision
this engagement informs.

Read, in order:
1. `docs/plans/registrar_parser_loader.md` — the design doc
2. `scraper/src/scrapers/registrar/parser.py` and `loader.py`
3. `scraper/tests/test_registrar_parser.py`, `test_registrar_loader.py`
4. `scraper/src/scrapers/registrar/sb.py` — the extractor they reuse
5. `docs/plans/registrar_phase1_sb.md` — scraper design + history

---

## 2. What the data actually is

Per measure, the registrar publishes up to **eight document roles**:
`resolution`, `text` (full measure text/ordinance), `analysis`
(impartial analysis), `tax_rate_statement`, `argument_for`,
`rebuttal_for`, `argument_against`, `rebuttal_against`.

Current November 2026 snapshot: **20 measures across 20
jurisdictions** (cities, school districts, community college
districts, a hospital district, a park district), **56 documents**,
letters A–R plus Y and Z. Measure types include bond measures,
transactions-and-use taxes, charter amendments, a transient
occupancy tax, and a special parcel tax. Thresholds are
authoritative from the county: 55% for Prop-39 school bonds,
66.67% for municipal bonds, 50% for ordinary measures.

**This is a different kind of data than the existing corpus.** The
existing 12,365 measures are overwhelmingly historical vote
outcomes (mostly CEDA, 1998–2024) with no ballot text. Verified
field coverage across the whole database today:

| Field | Populated |
|---|---|
| `pro_arguments` | 7 / 12,365 |
| `con_arguments` | 7 |
| `fiscal_impact` | 7 |
| `proponents` / `opponents` | 7 each |
| `endorsements` | 0 |
| `briefing_text` | 7 |
| `pdf_url` | 35 |
| `summary_text` | 3,486 |
| `ballot_question` | 1,787 |

The schema has slots for argument, fiscal, and document data that
have essentially never been filled. The registrar pipeline is the
first source that supplies them at scale — as official primary
documents, for measures **before** people vote on them.

---

## 3. Part A — correctness review

Standard implementation review of the parser, loader, and their
tests. Verdicts with severity (blocker / should-fix / nit / agree).

Already verified independently, so do not re-litigate unless you
find them wrong: 173/173 registrar tests pass; the live DB is
byte-identical (SHA-256 `73EEFB23…C860F1`); all 22 pre-existing
2026 rows are `Statewide` so there is no cross-source collision
surface; the county string `SAN BERNARDINO` matches the existing
344 SB rows; loading into a copy inserts 20 rows with no duplicate
fingerprints anywhere; a second load skips all 20 with zero
`update_count` churn; lineage traces 8 measures back to the
2026-07-27 snapshot when every letter was still `TBD`.

Where to look hardest:

1. **Lineage matching under adversarial drift.** The matcher tries
   document-URL intersection, then letter, then
   jurisdiction/description/threshold, then jurisdiction/description,
   then a jurisdiction/threshold key. What happens when a county
   *re-uploads* a document at a new URL, *renames* a jurisdiction,
   *withdraws and re-adds* a measure, *swaps* two letters, or
   splits one measure into two? Which of these silently mislink,
   and which correctly raise `LineageConflictError`?
2. **Identity durability.** `measure_id` digests the origin
   observation's highest-priority document URL. Is there a
   realistic case where the origin key is unstable, or where two
   distinct measures could share one? What happens to identity if
   the *earliest* snapshot is ever deleted or a new earlier one
   appears?
3. **Scope reconciliation / deactivation.** A registrar row absent
   from a later complete snapshot is deactivated. Is that right for
   a county that publishes incrementally? Consider a snapshot that
   is complete but temporarily truncated by a CMS error.
4. **Loader transactionality**, backup behavior, dry-run
   read-only guarantees, and the cross-source match rule (county +
   election date + letter + compatible jurisdiction) — including
   what it would do against the 344 existing SB rows during a
   future historical backfill, which is the real test of that gate.
5. **Field mapping fidelity**: title construction, threshold
   normalization, `election_type`, and any place a null is being
   asserted rather than observed.
6. **Test coverage gaps** worth closing before this data goes live.

Known warts already identified — confirm, and say if they matter
more than we think: `DATA_SOURCE` is a single module constant
rather than per-county; the extractor is imported directly from
`sb` (though injected as a parameter, so a seam exists);
`ELECTION_TYPES` is a literal `(county, election_date)` lookup that
raises on anything unknown, so every new election needs a code
edit (note the model already carries an `election_type_imputed`
flag suggesting date-derivation was the intent); and with
`--commit` and nothing to do, the report prints `DRY-RUN/NO-WRITE`.

---

## 4. Part B — what are we leaving on the table?

**This is the part we most want fresh thinking on.** Explore the
existing site and database, then tell us what this data enables.
Ground every suggestion in what is actually there — no generic
product brainstorming.

Context you need to explore:

- **Existing insight panels** live in `scraper/scripts/generate_insights.py`:
  `build_trend_insights`, `build_topic_insights`, `build_type_insights`,
  `build_threshold_insights`, `build_geography_insights`,
  `build_close_call_insights`, `build_finance_insights`. Look at how
  each is rendered by `src/website/generator.py`.
- **Measure cards and the modal** — see the generator. Note the
  Finance modal as the most developed example of a per-measure
  data surface.
- **External links** — `src/utils/external_links.py` already
  synthesizes county registrar URLs per measure. We now hold real,
  checksummed document URLs.
- **Product philosophy** — free deterministic cards plus on-demand
  editorial briefings (BYO LLM or paid); the paradigm is the moat,
  so **no bulk pre-generation of briefings**. Respect this: do not
  propose mass LLM summarization as a headline idea.
- **Open backlog** in `docs/WORKING_LIST.md`, notably: the topic
  classification gap (~75% of measures bucket to "Other"), the
  pending-measures UX spec (`context/vgp-pending-measures-prompt.md`,
  which assumes a React stack this project does not use), thematic
  policy explorations, and `docs/plans/georgia_scaffold_integration.md`
  (a proposal to adopt the Comparative Agendas Project taxonomy).
- **`docs/KNOWN_ISSUES.md`** — issue #1 says CEDA's `pass_fail`
  encoding produces untrustworthy vote thresholds. The registrar is
  an authoritative source for thresholds. Consider what that makes
  possible.

Specific questions, plus anything we have not thought to ask:

1. Which near-empty schema fields (§2 table) can be populated from
   registrar data **deterministically**, without an LLM? Be precise
   about what is genuinely derivable from document presence and
   metadata versus what would require parsing PDF contents.
2. What can the *document set itself* support as a product surface —
   e.g. a per-measure official-documents panel — and what would
   that look like given the existing modal patterns?
3. Are there **cross-source validation** opportunities? Registrar
   data is authoritative where aggregators are not. What could it
   verify, correct, or flag in the existing corpus — now, and after
   historical backfill against those 344 SB rows?
4. Is there a coherent **"what's on the ballot this November"**
   surface? Consider that the corpus is otherwise historical, the
   election is roughly three months out, and four more counties are
   planned before launch.
5. What genuinely *new* analysis becomes possible — jurisdiction-type
   patterns (school vs city vs special district), threshold
   distributions from authoritative data, argument availability as a
   signal of contestedness, tax-rate-statement presence as a fiscal
   marker?
6. What should we deliberately **not** build, and why?

Deliver this as a ranked register: each item with what it enables,
what it depends on, rough effort, and the risk of getting it wrong.
Separate "possible with today's 20 measures" from "needs the other
four counties" from "needs PDF text extraction" (which remains
deliberately deferred — see §6).

---

## 5. Part C — integration plan, and implement Phase 0 only

Produce a phased plan to get this onto the live site, with an
explicit verification gate per phase and a stated rollback for
each. Assume phases will be executed one at a time with review
between them. Constraints that shape it:

- The site generator **dual-writes** both repo-root `index.html`
  and `scraper/index.html` — they must stay in sync (this has
  bitten the project before; see `docs/LESSONS_LEARNED.md`).
- 20 pending measures will sit among 12,365 mostly-historical ones.
  The site's visual language assumes results (percentages,
  pass/fail badges, margins). Only 57 existing measures lack an
  outcome, so this path is barely exercised.
- Any regression in existing panels, counts, or the finance modal
  is unacceptable.
- Static site: everything must work with generated HTML/JS and no
  backend.

**Implement Phase 0 now, and only Phase 0:** load the parsed SB
records into a *copy* of the database, run the site generator
against that copy into a scratch output location, and report
exactly what the result looks like — how a pending registrar
measure renders as a card and in the modal, what is missing or
broken, whether existing panels and totals are unaffected, and any
generator assumptions that break on null outcomes. **Do not modify
the live database, the committed `index.html` files, or deploy
anything.** Screenshots are unnecessary; precise description of
rendered structure and any breakage is what matters.

---

## 6. Constraints and out of scope

- **PDF text extraction stays deferred.** Full measure text and
  argument prose remain linked, not parsed. You may *propose* it in
  Part B with an effort estimate; do not implement it.
- No bulk LLM summarization or briefing pre-generation.
- Do not touch the finance subsystem, the scraper's live cron path,
  or other counties.
- Never `git add .` — the repo has many gitignored data artifacts.
- `pytest` runs from `scraper/`; imports use `from src.xxx`.
- Windows + PowerShell primary; write cross-platform code.
- The existing 173 registrar tests must still pass.

---

## 7. Calibration

Part A: rigorous, severity-tagged, of the standard the prior six
rounds set — the failure modes this project has caught were ones
that *reported success* (a silent fallback to ephemeral storage, a
parser that would publish empty snapshots, a rule that prevented
silent document misattribution). Identity and lineage is where that
risk now lives.

Part B: be genuinely imaginative but concrete, and rank honestly —
including telling us when an idea is not worth it. This is the
first time the project has had official primary-source documents
for measures that have not yet been voted on; if that unlocks
something we have not seen, say so plainly.

Part C: a plan someone can execute one gate at a time.

Close with what you verified, what you assumed, what you deferred,
and what needs Igor's decision.
