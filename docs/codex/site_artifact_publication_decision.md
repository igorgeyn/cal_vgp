# Codex: how should generated site artifacts be published?

> **For Codex:** A focused decision memo, not a build. Recommend
> one option with rationale, then implement **only if** your
> recommendation is low-risk (see §5). Self-contained; assume no
> session memory.

---

## 1. The immediate question

`scraper/src/website/generator.py` writes the static site to two
locations:

- **`index.html` + `measures-data.json` at the repo root** — served
  by GitHub Pages. This is the live site.
- **`scraper/index.html`** — a second copy, described in the
  `scraper/Makefile` as "for local testing." Call it the mirror.

A generator fix just landed (commit `5f1cd26`): publishing now goes
through one public API, `generate_prepared(..., output_paths=[...])`,
which writes a paired HTML + JSON bundle to **every** output
location. `scraper/tests/test_website_output_contract.py` asserts
that all HTML copies and all JSON copies are byte-identical.

Consequence: the next regeneration rewrites the mirror in the
current split format and creates a **new `scraper/measures-data.json`
(~35 MB)**. Nothing is gitignored, so it would be committed.

Current on-disk state:

| Artifact | Size | Format | Tracked |
|---|---|---|---|
| `index.html` (root) | 6.0 MB | split shell, fetches the JSON | yes |
| `measures-data.json` (root) | 34.9 MB | data, last written 2026-07-02 | yes |
| `scraper/index.html` | 40.9 MB | **legacy embedded-data build** | yes |
| `scraper/measures-data.json` | absent | — | would be |

**`.git` is currently 1.6 GB.** Generated artifacts have been
committed repeatedly over the project's life; every data refresh
adds a fresh ~35 MB blob to history. Committing the mirror would
roughly double that rate.

Nothing depends on the mirror programmatically — verified references
are a `Makefile` echo line, a comment in `generate_site.py`, a hard
rule in `/CLAUDE.md`, and an entry in `docs/LESSONS_LEARNED.md`
(the 2026-05-04 trap where only one of the two locations was being
written, producing stale local previews).

---

## 2. Options to evaluate

1. **Commit the mirror.** Status quo behavior; no work; doubles
   artifact churn in history permanently.
2. **Gitignore the mirror** (`scraper/index.html` +
   `scraper/measures-data.json`); `git rm --cached` the tracked one
   so it stays on disk but leaves the index. Local preview keeps
   working as documented; history stops growing from the mirror.
3. **Drop the mirror entirely.** Generator writes only the deployed
   pair; document a local-serve command (e.g. `python -m http.server`
   from the repo root) for preview. Requires updating the CLAUDE.md
   hard rule and the LESSONS_LEARNED entry.
4. **Stop committing generated artifacts at all.** Build and deploy
   the site from CI to GitHub Pages (Actions → Pages artifact, or a
   `gh-pages` branch) so `main` carries source and data but not the
   rendered 41 MB of output. This addresses the 1.6 GB root cause
   rather than the mirror symptom, but it changes the deployment
   path, and the project's constraints are **zero-cost, no server,
   public repo, GitHub Pages**.

Claude's lean is option 2 — smallest change that stops the bleeding
while preserving the documented workflow. **Say so if that is wrong**,
especially if option 4 is worth the disruption now rather than later;
this project's review history has repeatedly been most useful when it
contradicted the in-house preference.

---

## 3. What the recommendation should address

- Whether the dual-write **hard rule** in `/CLAUDE.md` and the
  LESSONS_LEARNED entry survive your recommendation intact, need
  rewording, or are superseded by the new contract test. Be explicit —
  those docs are load-bearing for future sessions.
- Whether the new byte-identical contract test still means anything
  if a mirror is untracked or removed, and whether it should change.
- What the *first* regeneration will look like as a reviewable diff.
  The root JSON is six weeks stale, so the first correct run may
  produce a large and surprising change; the current plan is to treat
  artifact regeneration as its own reviewed step.
- Whether GitHub has practical limits worth respecting here (per-file
  warnings/blocks, repo-size guidance, Pages build constraints), and
  whether 1.6 GB is already a problem for clone/CI time.
- If you recommend anything other than option 1, the exact steps,
  the rollback, and what breaks for someone with an existing clone.
- Whether history cleanup (rewriting to purge old artifact blobs) is
  worth proposing as separate future work, or is a trap.

---

## 4. Context you may want

- `/CLAUDE.md` — rules of engagement, including the dual-write rule.
- `docs/LESSONS_LEARNED.md` — the dual-write trap entry.
- `scraper/Makefile` — the `website` target.
- `scraper/scripts/generate_site.py` and
  `scraper/src/website/generator.py` — the publishing path as of
  `5f1cd26`.
- `.github/workflows/` — existing workflows, including the
  currently-manual `weekly-pipeline.yml`, which commits `index.html`
  and the database but **not** `measures-data.json` (relevant to
  option 4 and arguably a latent bug of its own — flag it if so).
- The registrar pipeline is mid-arc: San Bernardino is live and
  scraping weekly, and four more counties are planned before any
  public launch. A deployment-path change now competes for attention
  with that work; factor that into timing, not just correctness.

---

## 5. Deliverable

A short decision memo — recommendation, rationale, rejected
alternatives and why, exact steps, risks, rollback.

**Implement only if you recommend option 1 or 2** (low-risk, local,
reversible). For options 3 or 4, deliver the plan only and stop;
those touch documented workflow or the deployment path and need
Igor's sign-off first.

Do **not** regenerate or commit site artifacts (`index.html`,
`measures-data.json`, `scraper/index.html`) under any option — that
remains a separate reviewed step. Never `git add .`. Existing tests
must still pass (182 registrar + site-contract tests green as of
`5f1cd26`).
