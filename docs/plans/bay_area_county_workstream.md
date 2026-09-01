# Bay Area county workstream

> **The plan for counties 2–6.** San Mateo, Alameda, Santa Clara, San
> Francisco, Contra Costa — the five counties the 2026-08-31 recon
> sweep examined. Board state lives in
> [`county_status.md`](county_status.md); recon detail in
> [`registrar_manifest.md`](registrar_manifest.md); build procedure in
> [`../setup/registrar_developer_guide.md`](../setup/registrar_developer_guide.md).
> This file is the *sequence, the debts, and the gates*.
>
> **Written 2026-08-31.** San Mateo build is in flight with Codex.

---

## 1. The goal, and the clock

Take the registrar pipeline from **one live county to six**, covering
**24.6% of California local ballot measure volume** (up from 3.3%),
with **current-election coverage for November 3, 2026** wherever the
county publishes ahead.

| Cumulative | Counties | Share of local measures |
|---|---|---:|
| Today | San Bernardino | 3.3% |
| + San Mateo | 2 | 7.5% |
| + Alameda | 3 | 12.9% |
| + Santa Clara | 4 | 17.7% |
| + San Francisco | 5 | 21.2% |
| + Contra Costa | 6 | 24.6% |

**The clock is the point.** Vote-by-mail ballots go out roughly 29
days before Election Day — about **October 5**. A county scraper that
lands after ballots are in voters' hands still builds the archive, but
misses the thing the product is actually for. That leaves roughly
**five weeks** of useful build runway from 2026-08-31.

Ordered by that constraint, not by volume:

| | County | Useful by Oct 5? | Read |
|---|---|---|---|
| 1 | San Mateo | ✅ | comfortable |
| 2 | Alameda | ⚠️ | tight — OCR is the risk |
| 3 | Santa Clara | ⚠️ | gated on Cloudflare + finding the page |
| 4 | San Francisco | ⚠️ | gated on the guide coming back |
| 5 | Contra Costa | ❌ | archive value only this cycle |

**Honest read: two counties are safe for November, two are coin flips,
one is not happening this cycle.** Everything past San Mateo competes
for the same five weeks, so the sequence below front-loads the cheap
unblocking work and treats the gated counties as parallel tracks that
either clear or get deferred to 2028 without stalling the rest.

## 2. Where we actually stand

**Verified 2026-08-31.**

- **San Bernardino live** — 6 production snapshots since 2026-07-27,
  currently 20 measures / 105 documents, all 20 published on the site.
  Documents grew 16 → 56 → 88 → 105 across the run history; rebuttals
  first appeared in the Aug 31 run.
- **196 registrar/website tests green** (`pytest -k registrar` from
  `scraper/`). The wider legacy suite has 18 known pre-existing
  failures, unrelated.
- **Capture/interpretation decoupling shipped** (`edb2978`). The
  scraper captures every advertised link without classifying it
  (`CapturedDocument`); role assignment happens offline in
  `sb_interpretation.py`, dispatched through `county_config.py`.
- **County name strings confirmed against the database** —
  `SAN MATEO` (458), `ALAMEDA` (598), `SANTA CLARA` (531),
  `SAN FRANCISCO` (386), `CONTRA COSTA` (370). New rows will group
  with the historical ones.

## 3. Three architectural debts this workstream will hit

The decoupling refactor made the pipeline *two-county-capable in
principle*. Reading the code against San Mateo's actual page shape
surfaces three places where it is still shaped like exactly one
county. None of these were visible before there was a second county to
check against.

### D1 — The cross-county contract lives inside `sb.py`

`county_config.py` types its registry as:

```python
extractor: Callable[[bytes, str], CapturedMeasuresPage]
interpreter: Callable[[CapturedMeasuresPage], MeasuresPage]
```

…and imports `CapturedMeasuresPage` from `.sb`, `MeasuresPage` from
`.sb_interpretation`. So San Mateo's extractor must return **San
Bernardino's dataclass, imported from San Bernardino's module.** The
alternatives are both bad: `smc.py` importing `sb.py`, or duplicating
six dataclasses that then drift.

**Fix:** hoist `CapturedDocument`, `CapturedMeasureRow`,
`CapturedMeasuresPage`, `ExpectedDocument`, `MeasureRow`,
`MeasuresPage` into `registrar/contracts.py`; re-export from `sb.py`
for compatibility. Pure move, no behavior change.
**~0.5 day. Should land before or with San Mateo.**

### D2 — The captured contract is table-shaped

Every positional field assumes a table:

| Field | Declared meaning | San Mateo reality |
|---|---|---|
| `CapturedDocument.column` | normalized table header | no columns exist |
| `CapturedDocument.table_row` | 1-based data-row index | no rows exist |
| `CapturedMeasuresPage.headers` | normalized, table order | no headers exist |
| manifest `table_row_count` | `len(page.rows)` | panel count |
| manifest `table_headers` | header tuple | absent |
| lineage `origin_table_row` | required by the loader | panel ordinal |

**This does not block San Mateo.** The parser's checks pass on an
empty-header county: `tuple(manifest.get("table_headers") or ()) !=
captured_page.headers` is `() != ()`, which is false, and
`table_row_count` only needs to equal the row count, whatever a "row"
is. A div-panel county threads through today.

What it costs is **truthfulness**: after San Mateo, `column`,
`table_row` and `headers` hold values that are not what their names
say — in a codebase whose entire safety argument rests on failing loud
when something is not what it claims to be.

**Recommendation: let San Mateo land first carrying the misnomers,
then rename in one pass** — `column` → `group`, `table_row` →
`row_index`, `headers` → `columns` (optional). Renaming before there
are two real shapes means guessing at the abstraction; renaming after
means fitting it to two known cases. `origin_table_row` is persisted
in `registrar_identities`, so that one needs a migration or dual read
— but see D3 for why it is safe to touch.
**~1 day, after San Mateo, before Alameda.**

### D3 — Measure identity is anchored to one document's URL

This is the one that can silently corrupt data, and it deserves the
most care.

`parser._origin_key()` picks a measure's identity anchor as:

```python
min(row.documents, key=lambda d: (_ROLE_PRIORITY.get(d.role, 999),
                                  canonicalize_document_url(d.url)))
```

`_ROLE_PRIORITY` ranks eight roles — `resolution`, `text`, `analysis`,
`tax_rate_statement`, `argument_for`, `argument_against`,
`rebuttal_for`, `rebuttal_against`. **Anything else sorts to 999.**
(`notice` is already unranked; it never wins on San Bernardino because
higher-priority documents are always present.)

The good news, verified: the identity digest is over
`[county_slug, election_date, origin_key_kind, origin_key_value]` —
**not** `origin_table_row`. Existing San Bernardino measure IDs are
therefore unaffected by the D2 rename.

The risk for San Mateo is specific. If Codex resolves the composite
document question by **inventing a new role name** — say
`resolution_text` for "Resolution and Full Text" — that role sorts to
999, and every San Mateo measure's identity anchors on `analysis`
instead. Identity then becomes sensitive to which documents happen to
exist at capture time, which is exactly the identity-drift failure
class closed once already in `5f1cd26`.

**Hard requirement on the San Mateo build:** any new role name must be
added to `_ROLE_PRIORITY` deliberately, with its rank chosen for
stability under progressive filing. Modeling the composite as *two
`ExpectedDocument`s sharing one URL* (roles `resolution` + `text`)
avoids the problem entirely and is the preferred answer — it keeps the
anchor on a document 28 of 29 measures have, and it lets the parser
answer "does this measure have a tax rate statement?" correctly.

**Expect reviewed `lineage_overrides` anyway.** San Bernardino needed
two, for a genuine re-titling mid-filing. San Mateo's filing looks
largely complete (33 rebuttals already present, versus San
Bernardino's 4), so the exposure is smaller — but any measure whose
anchor document appears *after* first capture needs either an identity
alias or a reviewed override. Budget for one or two.

## 4. Sequence

### Track A — San Mateo (in flight)

- [ ] **A1 · Build.** Codex, per
      [`../codex/san_mateo_scraper_build.md`](../codex/san_mateo_scraper_build.md).
      3–5 days. Fixtures first; the composite-document decision
      settled against real bytes.
- [ ] **A2 · Review round.** Check §7 of the report against D3 above
      — the role-priority question is the one that matters. Also
      verify the label census: 29 impartial analyses, the
      `in Favor`/`In Favor` casing variant handled, non-measure PDFs
      (Roster of Candidates, Alphabet Drawing) excluded. 0.5–1 day.
- [ ] **A3 · Hoist shared contracts (D1).** 0.5 day, same arc.
- [ ] **A4 · Dev smoke, then enable.** `--counties=smc --env=dev`,
      inspect the snapshot, then add to `ENABLED_COUNTIES` as a
      separate reviewed commit — the same discipline San Bernardino
      got.
- [ ] **A5 · Load and publish.** Parser → loader → site. 29 measures
      onto the local-measures band, which then has two counties and a
      real reason for the county toggle.

**Gate to Track B: one clean unattended cron run with two counties
enabled.** Do not start a third county on an unproven two-county
pipeline.

### Track B — Alameda

- [ ] **B1 · Rename the table-shaped contract (D2).** 1 day. Do it
      here, with two known page shapes in hand.
- [ ] **B2 · OCR spike — timeboxed to 1 day, and a real go/no-go.**
      Alameda ships one scanned 15-page PDF per measure containing
      submittal, resolution, full text and tax-rate material with
      **no text layer**. Question: can roles be segmented reliably
      from OCR'd page text, or can the packet only be captured whole?
      Note the recon inspected **one** packet of 28 — do not assume
      the rest match.
- [ ] **B3 · Build**, 5–8 days, contingent on B2. Enumeration is
      clean: opaque election IDs read from the server-rendered
      landing page (never scan integer ranges — `262` is August 2026,
      `260` is November, `259` is June), plus a server-rendered HTML
      fragment at `/rov_app/measures/election/{id}` carrying all 28
      titles, jurisdictions, ballot questions and thresholds inline.
      No anti-bot barrier; Playwright not needed.

**If B2 says segmentation is unreliable, capture the packet as a
single document with an honest `role="packet"` and ship the inline
ballot questions from the fragment.** That is still a genuinely useful
card — jurisdiction, question, threshold, and a link to the official
record — and far better than slipping past October 5 chasing per-role
OCR.

### Track C — the gated counties, in parallel

These do not block each other, and none should block Alameda.

- [ ] **C1 · Santa Clara: find the November measure list.** The June
      2026 page (`/list-local-measures-3`) proves the county publishes
      ahead with rich per-role documents. The November equivalent was
      not discoverable on Aug 31 — but the argument/rebuttal filing
      forms are live, so measures likely exist. CMS slugs are opaque
      and must be discovered from `/elections`, never guessed.
      **Blocked by C3.**
- [ ] **C2 · San Francisco: re-probe when the guide returns.** The
      Department's calendar confirms the source material exists —
      ballot questions and Controller analyses were due Aug 10,
      arguments Aug 13, rebuttals Aug 17, public examination closed
      Aug 28. The voter-guide host returns HTTP 503 "Site under
      maintenance". That is a publication-state barrier, not a bot
      challenge. **Do not build against the maintenance shell.**
      Re-probe weekly; build only once the structure is verifiable.
      4–7 days once live.
- [ ] **C3 · Resolve the Playwright politeness prerequisite.**
      Gates Santa Clara, Contra Costa and Riverside — three counties
      on one ~1–2 day fix, which makes it the highest-leverage item
      in Track C. See §5.
- [ ] **C4 · Contra Costa: browser recon.** After C3. The live site
      returns HTTP 202 with `x-amzn-waf-action: challenge`. Its
      forward-publication behavior is **unknown, not absent** — do not
      record it as archive-only on current evidence. The separate
      `pastresults.contracostavote.gov` ElectionStats app (1997–2025,
      CSV export) is a different integration entirely, and is not
      evidence that a forward source exists.

### Track D — deferred, deliberately

- **Los Angeles** (12.6%, the largest single gain) publishes only
  at/after Election Day. Nothing it offers helps November. It is a
  large archive project worth doing on its own schedule, and it drags
  in the untested cross-source reconciliation problem
  ([`../KNOWN_ISSUES.md`](../KNOWN_ISSUES.md) #12), since it overlaps
  existing CEDA rows.
- **The 48-county tail** (27.1%). Per-county adapters are the wrong
  tool at that scale. Different technique, or not worth it.

## 5. The Playwright prerequisite (C3), specifically

`base.fetch()` checks robots and rate-limits the **navigation URL**,
then hands off to `_fetch_playwright()`, where Chromium follows
redirects and loads subresources on its own. Concretely, versus the
`requests` path:

| Guarantee | `requests` | `playwright` |
|---|---|---|
| robots check on initial URL | ✅ | ✅ |
| rate limit on initial URL | ✅ | ✅ |
| robots check per redirect hop | ✅ | ❌ browser-internal |
| rate limit per hop / subresource | ✅ | ❌ |
| retries, backoff, `Retry-After` | ✅ | ❌ single attempt |
| `ETag` / `Last-Modified` captured | ✅ | ❌ not populated |
| real `Content-Type` | ✅ | ❌ hard-coded `text/html` |

The code says as much — *"browser-level retry semantics get designed
when Riverside lands in Phase 1."* Riverside never landed, so the
design was never done, and three counties now sit behind it.

Minimum bar before enabling any WAF-protected county: route
navigations through a request interceptor applying the same robots and
rate-limit checks per request, populate the real content type, and
reach retry/backoff parity. **~1–2 days.** Do not enable Santa Clara
or Contra Costa on the current implementation.

## 6. The maintenance budget

**This remains the real ceiling — and the arithmetic just changed in
our favor.**

The pre-decoupling estimate — ~1 drift event per county per two weeks,
every one reddening the cron — projected roughly 2.5 red crons per
week at five counties. That table is now stale.

After `edb2978`, drift splits in two:

- **Structural drift** (the page shape changes) still reds the *cron*
  and costs that week's capture.
- **Vocabulary drift** (a new document label appears) now reds an
  *offline parse* instead. Fixable on your schedule, from stored
  bytes, no re-scrape, nothing lost.

**Two of San Bernardino's three drift events were vocabulary.** If
that ratio holds, five counties produce ~2.5 events/week of which
**~0.8/week red the cron** — roughly one interrupt a week rather than
one every other day. That is the difference between sustainable and
not.

Two caveats worth holding honestly. The ratio comes from three events
on one county, which is a thin basis. And every new county is a new
vocabulary — San Mateo already ships a casing variant and composite
labels San Bernardino never had, so early weeks will run hotter than
steady state.

**Worth doing after Alameda:** automated drift triage (expansion
workplan §5b, ~3 days). The failure already names the row, the cell
and the rule; it could classify itself and open a PR with the proposed
role addition and a pinned fixture. That reduces cost per event rather
than event count — the right lever once event count is what is
scaling.

## 7. Cross-cutting

- [ ] **`measure_documents` table (open threads F1).** San Bernardino
      captures 105 documents; the database stores **one `pdf_url` per
      measure**. San Mateo will add ~135 more, Alameda 28 packets. The
      nine-slot document display has nowhere to read from. This gap
      widens with every county and is the largest piece of
      captured-but-unused value in the project.
- [ ] **County toggle in the local-measures band.** Currently
      single-county by default. Two counties makes it necessary; three
      makes it load-bearing. Revisit the carousel-vs-scroll question
      at 3+ counties, with real volume, per expansion workplan §7.5.
- [ ] **Per-county recon artifacts are gitignored**
      (`scraper/data/registrar_recon/`). Fine for now, but if a
      finding gets disputed the evidence is local-only and
      machine-specific.
- [ ] **Update [`county_status.md`](county_status.md) as each county
      moves.** That is the board; this is the plan.

## 8. Decisions needed

1. **Alameda's OCR go/no-go rule.** If B2 shows unreliable role
   segmentation, is a whole-packet `role="packet"` card acceptable for
   November, with per-role extraction deferred? *Recommendation: yes.*
2. **Santa Clara and San Francisco if they stay gated past ~Sept 20.**
   Cut them for this cycle and build the archive later, or keep
   spending probe time? *Recommendation: hard cutoff at Sept 20 —
   past that, a build cannot land before ballots mail.*
3. **Contra Costa browser recon** — worth ~1 day to convert an unknown
   into a fact, or defer the county entirely? *Recommendation: do it,
   but only after C3, since it needs the same fetch path.*
4. **Maintenance appetite** (open threads G2). At what weekly
   red-cron rate do we stop adding counties? That number decides
   whether six counties is the destination or a waypoint.

## 9. Done looks like

- **Six county configs**, or a written decision for each one not built.
- **`contracts.py`** holding the cross-county types, with no county
  module importing another county module.
- **Positional fields named for what they hold**, across two real page
  shapes.
- **A Playwright fetch path** with politeness parity, or three
  counties explicitly deferred.
- **Two-plus counties live on the site before ballots mail (~Oct 5)**,
  with a working county toggle.
- **County status board current**, so the next session resumes from
  the board rather than from this plan.
