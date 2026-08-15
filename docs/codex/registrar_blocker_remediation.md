# Codex: blocker remediation design + implementation

> **For Codex:** You reviewed the registrar parser/loader and
> correctly failed the Phase 0 gate with four blockers plus a
> site-generation release blocker. This engagement is the
> remediation: **design the fixes, then implement the ones covered
> by tests.** The site-output fix touches deployed artifacts and is
> handled differently — see §4.
>
> Your report is committed at `docs/plans/registrar_sb_review_and_integration.md`.
> Re-read it; you are building on your own findings. Self-contained
> otherwise — assume no session memory.

---

## 1. Independent verification of your findings

Before designing, know what was confirmed here by a second party:

- **Backward roll: reproduced exactly.** Parsing the oldest
  snapshot (`20260727T170014Z`, 8 rows) and dry-running it against
  a database copy already holding all 20 measures produced
  `inserted=0 updated=8 deactivated=12 skipped=0`. Your blocker is
  real and demonstrable on demand.
- **Site-generation blocker: confirmed, and larger than reported.**
  See §3 — the facts changed the shape of the fix.
- Live DB unchanged (SHA-256 `73EEFB23…C860F1`); committed
  `index.html`, `scraper/index.html`, and `measures-data.json`
  untouched; 173/173 registrar tests pass.
- The explicit `measure_id` construction does correctly avoid the
  title-regex trap. That part stands.

Blockers 1, 3, and 4 (transient incompleteness → deactivation; URL
re-upload plus letter reuse/swap → identity misassignment; identity
drift when snapshot availability changes) were **not** independently
reproduced. Part of your job is to make each one concretely
demonstrable as a failing test before fixing it.

---

## 2. Remediate the four data-integrity blockers

For each: a short design rationale, a **failing test that
demonstrates it**, the fix, and the test passing. Consider these
design questions explicitly rather than implicitly:

1. **Monotonicity / backward roll.** Should the loader refuse a
   snapshot older than the one already applied to a given
   `(county, election_date)` scope? That implies the database must
   record which snapshot a scope was last loaded from — where does
   that live, given there is no registrar-specific table today?
   What is the escape hatch for a deliberate, reviewed replay of an
   older snapshot, and how is it made hard to do by accident?
2. **Transient incompleteness vs genuine withdrawal.** A complete
   snapshot that is truncated by a source-side CMS error currently
   deactivates valid measures. What evidence distinguishes "the
   county removed this measure" from "this observation is
   suspect"? Consider a magnitude guard, a confirm-across-N-runs
   rule, quarantine-instead-of-deactivate, or requiring human
   review above a threshold — and say which you recommend and why.
   Note the pipeline's established preference: **fail loudly rather
   than act on ambiguous evidence.**
3. **Identity under URL re-upload + letter reuse/swap.** The
   `measure_id` digest keys on the origin observation's
   highest-priority document URL. Show the concrete sequence that
   misassigns identity, then fix it. Consider whether lineage needs
   corroborating evidence before accepting a URL match, and whether
   any single-signal match should ever be sufficient.
4. **Identity stability under changing snapshot availability.**
   Identity derives from the *earliest* observation, so identity can
   change if an earlier snapshot appears or an old one is lost. Does
   this call for a persisted identity registry (assign once, never
   recompute), and if so where does it live and how is it
   audited/rebuilt? Weigh that against the current
   recompute-from-archive property, which is genuinely valuable —
   the loader independently recomputing the digest is a defense
   against hand-edited keys.

Also apply, if you still agree they matter: `DATA_SOURCE` as a
single module constant, the direct `sb` extractor import,
`ELECTION_TYPES` as a literal `(county, election_date)` lookup that
requires a code edit per election (the model's
`election_type_imputed` flag suggests date-derivation was intended),
and the `DRY-RUN/NO-WRITE` label printed under `--commit` when there
is nothing to do.

---

## 3. The site-output contract — worse than your report stated

Verified facts, all current:

- `scraper/scripts/generate_site.py` calls the **private**
  `generator._generate_html(...)` and writes HTML itself. It writes
  `index.html` to `args.output` **and** to the repo root. It writes
  `measures-data.json` **nowhere**.
- `WebsiteGenerator.generate()` — the only code that writes
  `measures-data.json` (next to the output copy, and next to the
  scraper-local copy when they differ) — is **dead code**. Nothing
  calls it. `make website` runs `generate_site.py --force`.
- `WEBSITE_OUTPUT_PATH = BASE_DIR / 'index.html'` where `BASE_DIR`
  is `scraper/`, so the default `--output` is **`scraper/index.html`**,
  not the deployed root copy.
- **Therefore your scratch patch is insufficient for production.**
  Writing `output_path.parent / 'measures-data.json'` lands the JSON
  in `scraper/`, leaving the deployed root `measures-data.json`
  stale. It fixed the diagnostic render only.
- Current artifacts on disk:

  | Artifact | Size | Nature |
  |---|---|---|
  | `index.html` (root, deployed) | 6.0 MB | split build; fetches the JSON at startup |
  | `measures-data.json` (root, deployed, tracked) | 34.9 MB | last written **2026-07-02** |
  | `scraper/index.html` | **40.9 MB** | legacy **embedded-data** build |
  | `scraper/measures-data.json` | absent | — |

  The two `index.html` files are not merely out of sync; they are in
  **different formats**. `docs/LESSONS_LEARNED.md` records a
  hard-won rule that this generator dual-writes two locations that
  must stay in sync. That rule is currently violated in production.

**Design the correct output contract** and say plainly what the
deployed site actually requires. Questions to answer: should the
script call `generate()` (and does the extra work it does — briefing
attachment, recommendations, custom stats — map onto that method's
signature)? Should the write logic be extracted into one shared
helper used by both paths? Should `scraper/index.html` remain a
second full copy at all, or become a thin local-preview artifact, or
be dropped in favor of a documented local-serve command? What
prevents this class of drift from recurring — a post-generation
consistency assertion?

**Implement the code change. Do NOT regenerate or commit the
deployed artifacts** (`index.html`, `measures-data.json`,
`scraper/index.html`). Artifact regeneration is a separate reviewed
step, because the root JSON being six weeks stale means the first
correct regeneration may produce a large, surprising diff that
deserves its own inspection. Prove the fix by generating into a
scratch directory and asserting the output contract there.

---

## 4. Sequencing question we want answered

Igor's plan is to build scrapers for the remaining four recon'd
counties (LA, Orange, San Diego, Riverside) **before** launching any
of this publicly, on the reasoning that scraping is time-sensitive —
county sites purge, and the November 2026 election is roughly three
months out — while loading is not, because the archive is permanent
and re-parseable.

Given your findings, tell us: which of these fixes **must** land
before the next county is built (because the shared loader/identity
layer would otherwise be replicated four times), which must land
before any live database load, and which can safely wait. If you
think the sequencing itself is wrong, say so.

---

## 5. Constraints

- 173 existing registrar tests must still pass; add tests for every
  fix.
- Never write to `scraper/data/ballot_measures.db`. Verify against
  copies.
- Do not regenerate or commit deployed site artifacts (§3).
- PDF text extraction remains deferred; no bulk LLM generation.
- Never `git add .`; `pytest` runs from `scraper/`; imports use
  `from src.xxx`; Windows-compatible code.
- Do not touch the finance subsystem or the live cron path.

---

## 6. Calibration

You wrote the report; do not simply agree with yourself. State
explicitly where your own findings were **overstated** now that you
are designing the fix — a blocker that turns out to be a nit is a
useful result, and so is one that turns out to be worse.

Prefer the smallest fix that closes the failure mode over a general
mechanism, unless the general mechanism prevents a class of future
bugs across four more counties — in which case say so and build it.

Close with: what you verified, what you assumed, what you deferred,
what needs Igor's decision, and your recommended sequencing per §4.
