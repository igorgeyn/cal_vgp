# Codex: fresh read of the project, and a plan for the next four weeks

> **This is a thinking task, not a build task.** No code, no
> publishing, no database writes. The deliverable is a written plan
> with reasoning, and an honest account of where you disagree with
> the current one.
>
> You are the first fresh pair of eyes on this in a while. The plan
> you'll read was written by someone deep in the work, which is
> exactly the condition under which people stop questioning their own
> framing. **Treat §6 as the real assignment.**
>
> Facts below verified 2026-09-07.

---

## 1. What this project is

CalBallot — a searchable database of California ballot measures,
statewide 1998–present plus ~12,000 local measures from CEDA. Python
pipeline → SQLite → static site generator → GitHub Pages, zero
hosting cost. Live at `cal-vgp.igorgeyn.com`.

The newer, differentiating half is a **county registrar pipeline**:
scraping county elections sites for measures on the *upcoming* ballot,
with their official documents attached — impartial analyses,
resolutions, full text, tax rate statements, arguments and rebuttals
for and against. Nothing else aggregates that across counties before
an election.

Start with [`CLAUDE.md`](../../CLAUDE.md), then
[`docs/WORKING_LIST.md`](../WORKING_LIST.md) and
[`docs/LESSONS_LEARNED.md`](../LESSONS_LEARNED.md). The latter is a
catalog of traps this project has already sprung; several would
otherwise re-spring.

## 2. Where it actually stands

**Verified today, not recalled:**

- **San Bernardino** live on the site: 20 measures, 105 documents,
  **7** production snapshots since 2026-07-27.
- **San Mateo** built, reviewed, enabled, captured, loaded — **2**
  production snapshots, 29 measures, 135 documents, 167 role records.
- **The weekly cron runs unattended and passes.** 2026-09-07 ran
  `--counties=enabled` and reported `2/2 counties succeeded`.
- **239 registrar/website tests green.** 18 pre-existing legacy
  failures elsewhere, unrelated and logged.
- **Filing has plateaued.** Both counties are byte-identical between
  Aug 31 and Sept 7. San Bernardino grew 16 → 105 documents across
  July–August, then stopped. The November record looks near-final.

**The one thing that is not done: none of San Mateo is public.**
Four commits sit unpushed. The live site shows 12,332 measures and
one county; the local build has 12,361 and two. Everything was
verified before the push stalled — dry-run was 29 inserts / 0 updates
/ 0 deactivations, San Bernardino's rows came through byte-identical,
and the artifact diff showed no field losses.

## 3. The constraints that actually bind

**The clock.** Vote-by-mail ballots go out ~29 days before Election
Day — about **October 5**, four weeks out. Election Day is
**November 3**. A county that lands after ballots are in hands still
builds the archive but misses the point of the product.

**Maintenance, not construction.** This is the argument the plan
rests on, and it is worth checking. Drift ran ~1 event per county per
two weeks. Shipping `edb2978` split drift in two: a new *document
label* now fails an offline parse (fixable on your schedule, from
stored bytes) while only *structural* change reds the cron. Two of
San Bernardino's three drift events were the former. The estimate is
therefore ~0.8 red crons/week at five counties rather than ~2.5.
**That ratio comes from three events on one county.** It is the
thinnest load-bearing number in the plan.

**Coverage arithmetic.** San Bernardino is 3.3% of local measure
volume, San Mateo 4.2%, Alameda 5.4%. Six counties reach 24.6%; ten
reach 50%; the 48-county tail is 27.1% and almost certainly the wrong
shape for per-county adapters.

## 4. What is already decided, and why

Don't re-litigate these without new evidence — but **do** say so if
you think one is wrong.

- **Los Angeles is deferred**, despite being the largest single gain
  at 12.6%. Its results portal publishes only at or after Election
  Day; the highest election ID is the June 2026 primary and the next
  ones return HTTP 500. It is an archive project, not a November one.
- **Santa Clara is blocked on a decision, not engineering.** Every
  host — including `robots.txt` — returns HTTP 403 "Attention
  Required!". That is a firewall block, not the 503 JavaScript
  challenge a headless browser can solve, so the Playwright work does
  not unblock it. The proposed move is to email the Registrar for an
  allowlist. Spoofing a browser User-Agent is off the table.
- **Alameda needs no OCR.** Its packets are scanned — measured at 569
  pages with 11 carrying extractable text (2%), and 22 of 28 packets
  with none. But the structured data (letter, jurisdiction, title,
  threshold, full ballot question) is served as clean HTML from a
  second host, so the packet is captured whole as `role="packet"` and
  OCR is skipped entirely. This took the estimate from 5–8 days to
  3–4.
- **Politeness is non-negotiable.** Identifying User-Agent, per-domain
  rate limit, per-hop robots checks on redirects. These are county
  government sites this project intends to scrape weekly for years.

## 5. The open work

Read [`docs/plans/open_threads.md`](../plans/open_threads.md) for the
full checklist,
[`bay_area_county_workstream.md`](../plans/bay_area_county_workstream.md)
for the sequence and the architectural debts, and
[`county_status.md`](../plans/county_status.md) for per-county state.
[`scout_alameda_santa_clara.md`](../plans/scout_alameda_santa_clara.md)
has the measurements behind the Alameda and Santa Clara calls.

The current plan, compressed: push the San Mateo publish; land the
`table_row`/`column`/`headers` rename (a naming debt, since those
fields now hold values their names deny) and a cross-county
`regional_measure_key`; then build Alameda; keep San Francisco and
Contra Costa as parallel gated tracks with a ~Sept 20 cutoff.

Two items sit outside that sequence and deserve your attention:

**`measure_documents` (F1).** San Bernardino has 105 captured
documents and San Mateo 167 role records. **The database stores one
`pdf_url` per measure.** Everything else is captured, checksummed,
stored — and shown to nobody. Each new county multiplies it.

**Post-election results ingestion (F3).** On November 4 every measure
flips from pending to decided, and **no design exists** for that
transition while preserving measure identity — which is the entire
purpose of the registrar identity system. Eight weeks out. It is the
only item with a deadline nobody can move.

## 6. The actual assignment

Produce a prioritized plan for the next four weeks — through ballots
mailing on ~Oct 5 — and a sketch through November 3.

**Argue with the premise first.** The current plan assumes county
expansion is the right use of the remaining time. A fresh reading
might reasonably conclude otherwise: that adding a third county
multiplies data nobody can see (F1), or that an undesigned
post-election transition (F3) is a larger risk than one more county,
or that the maintenance estimate is too thin to justify scaling at
all. **If you think the priority is wrong, say so plainly and make
the case.** That is more valuable than a well-ordered version of the
existing plan.

Then, whatever ordering you land on:

1. **Sequence it against the Oct 5 and Nov 3 dates**, with rough
   effort and explicit dependencies.
2. **Name what you would cut.** Four weeks will not fit everything.
3. **Flag anything in the existing docs you believe is wrong,
   stale, or overconfident** — including the maintenance ratio in §3
   and anything in §4.
4. **Identify risks nobody has written down.** The most valuable
   findings on this project have consistently been the ones nobody
   went looking for.
5. **Separate what needs Igor's judgment** from what is yours to
   decide. Open decisions are collected in §G of `open_threads.md`.

## 7. Constraints

Read-only. Do not write code, run the loader, regenerate site
artifacts, touch `scraper/data/ballot_measures.db`, push, or scrape
anything live. If you want to verify a claim, prefer the repo, the
database (read-only), and the existing recon artifacts under
`scraper/data/registrar_recon/` over new network requests.

Write the plan to `docs/plans/forward_plan_20260907.md` and summarize
it in your reply.
