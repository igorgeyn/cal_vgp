# San Bernardino registrar parser/loader review and integration plan

> Review date: 2026-08-14  
> Reviewed implementation: `7861bb0`  
> Phase 0 only was executed. No live database, deployable site artifact, cron path,
> finance code, or PDF content was changed.

## Executive decision

**Do not load this data into the live database yet.** The current 20-record batch is
internally clean, deterministic, and idempotent when the same latest snapshot is
repeated. The explicit `measure_id` defense also handles the project's fingerprint
trap correctly. However, recurrent use is not safe yet:

1. a valid but older snapshot can be loaded after the latest one, rolling eight
   records backward and deactivating twelve with no conflict;
2. a transiently truncated registrar page is considered a complete artifact capture
   and can deactivate every omitted measure;
3. the lineage matcher can silently exchange identities after a document re-upload
   plus letter swap/reuse; and
4. identities are recomputed from the available historical prefix rather than read
   from a durable lineage registry.

Phase 0 also fails its site-release gate. The production CLI writes new HTML but not
the `measures-data.json` that HTML fetches. In a fresh output directory the site
renders its database-load error; in the real repo it would more dangerously pair new
HTML/insights with the old 12,312-record JSON and silently omit all 20 registrar
measures. A scratch-only two-line diagnostic patch exposed additional pending UX
problems, especially lost vote thresholds and an incorrect `Filed` lifecycle stage.

The recommended path is to fix the identity/snapshot contract first, preserve
cross-source provenance, then repair the static-site artifact contract and pending
display before any live load.

---

## A. Correctness review

### A1. Findings by severity

#### BLOCKER — a complete artifact capture is not proof of a complete ballot scope

`sb.py` deliberately treats a link-free or zero-document publication as a valid
observation, and the manifest's row/PDF counts correctly prove that everything on
that page was captured. The loader makes a stronger, unjustified inference: every
registrar-owned record absent from that selected snapshot is deactivated.

Those are different claims. A CMS partial render, caching problem, temporary table
truncation, or incremental publication can be faithfully captured and checksummed
while still being an incomplete statement of the election. The current loader would
report success while hiding valid measures. The loader test named
`test_complete_snapshot_deactivates_and_reactivates_same_lineage` confirms this
behavior; it does not protect against the source-side failure.

Required change before live use:

- make ordinary loads additive/update-only;
- make reconciliation an explicit, separately authorized operation;
- persist a scope watermark and prior cardinality;
- require either an explicit withdrawal list or confirmation in two later snapshots
  before deactivation; and
- emit a loud review gate for any row-count decrease, not merely a structurally valid
  manifest.

The two-snapshot rule is a safety fallback, not a claim that two identical failures
are authoritative. A human-approved withdrawal/change report remains the safest
initial policy.

#### BLOCKER — the loader permits chronological rollback

The parser defaults to the latest complete snapshot but intentionally allows an
explicit earlier `snapshot_id`. The JSONL carries a snapshot ID; the database does
not store which snapshot was last applied for a county/election scope. Therefore the
loader cannot reject an out-of-order batch.

This is not hypothetical. The local store contains the three real observations:

| Snapshot | Rows | Documents |
|---|---:|---:|
| `20260727T170014Z` | 8 | 16 |
| `20260728T003041Z` | 9 | 18 |
| `20260814T034259Z` | 20 | 56 |

After loading the latest 20 into the database copy, I parsed the oldest valid
snapshot and dry-ran it against that copy. The loader reported:

```text
DRY-RUN/NO-WRITE inserted=0 updated=8 deactivated=12 skipped=0 conflicts=0
```

The eight surviving rows would also regress from assigned letters/current metadata
to their July observation. Repeating one batch is idempotent; applying valid batches
out of order is not.

Required change: store a `(county, election_date, last_snapshot_id,
page_sha256, loaded_at)` scope watermark in the database. Reject an older snapshot;
allow the same snapshot only when its checksum agrees; require explicit recovery
authorization for any rollback.

#### BLOCKER — lineage rules can silently swap or reuse identity

Document URL intersection is appropriately strongest. Once URLs change, however,
an assigned letter is accepted before any semantic compatibility check. The final
`jurisdiction + threshold` rule is weaker still: it deliberately links description
drift, but it can also link an entirely different proposal in the same jurisdiction.

The matcher considers all earlier lineages, including withdrawn ones. A later,
different proposal that reuses a letter can therefore inherit the withdrawn
proposal's origin and ID. This is a false continuity, not a detectable SHA-256
collision.

Observed behavior by drift scenario:

| Scenario | Current behavior | Verdict |
|---|---|---|
| Same URLs, letters assigned or swapped | URL evidence wins; identity follows the documents | Correct |
| URLs re-uploaded, same letter, compatible semantics | Letter links the row | Usually correct, but under-validated |
| URLs re-uploaded and two letters swap | Each row silently follows its new letter, exchanging identities | Unsafe |
| Withdraw then re-add the same proposal with a shared URL | Old lineage reactivates | Desirable |
| Withdraw, then a different proposal reuses its letter with new URLs | Different proposal silently inherits old lineage | Unsafe |
| Jurisdiction renamed, URL stable | URL preserves identity | Correct |
| Jurisdiction renamed and URL changes while letter is `TBD` | New lineage is created; old one disappears | Silent identity churn |
| One measure splits into two | Can become one continuation plus one new lineage, or conflict when weak keys are ambiguous | Review required |
| Two measures merge into one | Shared URLs from both raise; a row retaining only one old URL silently chooses that lineage | Partially safe |

Required change:

- compare new rows primarily to the immediately previous snapshot's active set;
- let old withdrawn lineages reactivate automatically only on strong URL evidence;
- require semantic compatibility for letter-only matches;
- treat letter/URL/semantic contradictions as conflicts;
- demote `jurisdiction + threshold` to a proposed match requiring an override; and
- maintain a checked-in lineage override/registry file so reviewed decisions are
  deterministic and auditable.

#### BLOCKER — IDs are not durable if the replay history changes

The digest construction is cryptographically sound. The unstable part is its input:
the origin is whichever observation becomes earliest in the currently available
snapshot prefix, using that row's highest-priority document URL (or semantic tuple
when no document exists).

If an earlier snapshot is restored/backfilled, or the former earliest snapshot is
lost, a lineage can acquire a different origin URL. The same real measure then gets
a different `REG_...` ID. On load, that can appear as a new insert plus deactivation
of the old identity. If the origin URL happens to be unchanged, the ID survives; the
system currently has no invariant that guarantees that.

Immutable snapshots reduce this risk but do not eliminate retention mistakes,
disaster recovery, or historical restoration. Once IDs are published, replay should
verify identity, not invent it again. Persist the reviewed identity registry before
the first live load and reject changes to an election's historical prefix unless a
migration map is supplied.

#### SHOULD-FIX before historical backfill — cross-source adoption erases provenance

The match gate itself is conservative: county + year + exact election date + letter,
with jurisdiction equality when both sides have jurisdiction. The current November
batch has zero candidates, so Phase 0 inserts 20 clean rows.

The 344 existing San Bernardino CEDA rows show what a historical backfill would do:

- 332 have election dates and are unique by election date + letter;
- 278 of those also have jurisdiction;
- 54 dated rows have no jurisdiction, so date + letter alone decides adoption; and
- 12 rows have no election date and therefore cannot be adopted by this gate. They
  would be inserted alongside the CEDA record unless another reconciliation step
  intervened.

Adoption updates the CEDA row in place and changes its `measure_id`, fingerprints,
`data_source`, official fields, and duplicate state while retaining CEDA vote totals,
summaries, and other rich values. Preserving the integer row ID is useful for finance
joins, but the resulting row falsely presents mixed-origin fields as one registrar
record. The old source identity is not preserved in `merged_from`, an observation
table, or an audit log.

Before historical backfill, add source observations/provenance and an explicit
master/source link. Prefer retaining both source records and selecting a canonical
presentation record over changing `data_source` in place. At minimum, write a
machine-readable adoption ledger with old and new values and field-level origin.

#### SHOULD-FIX — backup creation is not fully race- or overwrite-safe

Commit mode has a good shape: validate and plan through a read-only URI, back up,
take `BEGIN IMMEDIATE`, re-plan under the lock, and commit all actions atomically.
Conflicts do not write. Dry-run never constructs `Database`, avoiding schema repair.

Two residual issues remain:

- SQLite's backup API opens an explicitly supplied backup path without create-only
  semantics, so an existing backup can be overwritten.
- The backup occurs before the write lock. A concurrent writer can commit between
  backup and `BEGIN IMMEDIATE`; the re-plan sees that write, but restoring the backup
  would lose it.

Use create-only backup targets and coordinate the backup with the same writer lock
or otherwise enforce a single-writer operational lock around backup + transaction.

#### SHOULD-FIX — unchanged new snapshots do not advance source freshness

Exact replays become `skip` actions and deliberately avoid `update_count` churn. That
is correct for content idempotency, but it also leaves `last_seen_at` unchanged. A
weekly unchanged snapshot is valuable evidence that the source was checked. Store
that evidence in the scope/observation table rather than mutating every measure.

#### SHOULD-FIX — per-county and per-election configuration is not extensible yet

- `DATA_SOURCE` is a module singleton. It is correct for SB now, but a multi-county
  parser/loader can stamp the wrong source unless source identity is county config.
- The SB extractor is imported directly. Parameter injection is a real seam and
  makes this lower risk, but an extractor registry would make county ownership
  explicit.
- `ELECTION_TYPES` is a literal `(county, date)` table. Every election requires a
  code change. The schema's `election_type_imputed` field indicates the intended
  split: authoritative configuration when known, deterministic date-derived value
  otherwise, with the imputation flag set.

These do not block this one SB election; they do block scaling the same loader to the
other counties without avoidable copy/paste risk.

#### SHOULD-FIX — field semantics lose useful distinctions

- `title = "{jurisdiction} — {description}"` is faithful and deterministic, but the
  UI later repeats the letter and uses the short description again as summary text.
- Threshold normalization is correct for the current rows: 11 at 50%, five at 55%,
  and four at 66.67%.
- `election_type=general` and `election_type_imputed=0` are correct for 2026-11-03.
- Null vote fields are correct: this pre-election source does not report an outcome.
- Null `ballot_question`, analysis, and argument prose mean **not extracted**, not
  observed absent. The schema cannot currently express that distinction.
- `measure_type="Measure"` is too generic, while `category_type` and
  `category_topic` are null. Exact registrar descriptions could deterministically
  populate most display types after a reviewed mapping.

Add extraction/availability metadata rather than letting null carry both “not
published” and “published but not parsed.”

#### NIT — no-op commit reporting is misleading

`--commit` with 20 skips reports `DRY-RUN/NO-WRITE`. No write is the right result,
but the label implies commit was not requested. Report `NO-OP (commit requested)`.

#### AGREE — the fingerprint trap is handled correctly

This part is strong and should remain non-negotiable:

- normalized rows carry an explicit, full-digest `REG_...` `measure_id`;
- the loader recomputes the digest from lineage origin and rejects tampering;
- `BallotMeasure` is constructed with that explicit ID, so title regexes never get a
  chance to guess `Measure X` from `title`;
- the loader asserts the exact expected fingerprint
  `year|measure_id|county|SB_County_Registrar`; and
- duplicate explicit IDs/fingerprints are conflicts, not tie-breaks.

This correctly closes the historically expensive class where human-looking titles
produce accidental identity collisions. The remaining identity defects are lineage
continuity and replay-history defects upstream of fingerprint generation.

#### AGREE — artifact validation and same-batch transaction behavior are strong

The parser re-reads checksummed artifacts, re-extracts the stored HTML, and compares
headers, row counts, document audit tuples, filenames, and PDF counts against the
manifest. Unexpected/missing artifacts fail. The selected snapshot emits a complete,
contiguous JSONL scope, and the loader validates scope, roles, checksums, explicit
identity, outcome nulls, and text-PDF mapping before planning.

Within one accepted batch, inserts/updates/deactivations are atomic and a locked
re-plan protects against state changes between the dry plan and transaction.

### A2. Test gaps to close before the live gate

The four parser tests and eight loader tests cover the happy lineage, checksums,
manifest mismatch, explicit-ID tampering, one adoption, multi-candidate conflict,
deactivation/reactivation, and repeated-batch idempotency. Add tests for:

1. out-of-order load rejection across the real 8 → 9 → 20 snapshot sequence;
2. zero-row and large row-count-decrease reconciliation refusal;
3. same-snapshot ID with a different page checksum;
4. URL re-upload + letter swap;
5. withdrawn-letter reuse by a different proposal;
6. jurisdiction rename with and without strong document evidence;
7. one-to-two split and two-to-one merge;
8. adding/removing an earlier snapshot after IDs have been registered;
9. two rows sharing the same highest-priority origin URL;
10. historical SB adoption with populated jurisdiction, null jurisdiction, and the 12
    undated CEDA rows;
11. adoption provenance retention;
12. create-only backup behavior and concurrent-writer backup consistency;
13. county-specific source/extractor/election-type configuration; and
14. exact generator contract tests that assert HTML and both `measures-data.json`
    files describe the same record set.

---

## B. Ranked opportunity register

### What can be populated deterministically now

The current metadata can safely populate core identity, county/jurisdiction, election
date/type, letter, source page, authoritative threshold, one full-text URL when
present (19/20), and a structured collection of all 56 document observations.

It **cannot** safely populate `ballot_question`, `summary_text`, `fiscal_impact`,
`pro_arguments`, `con_arguments`, `proponents`, `opponents`, or `endorsements` from
link presence. Those fields hold content, not availability. An `argument_for` PDF
proves that a document with that official role was published; it does not expose its
argument or signers until content extraction occurs. Tax-rate-statement presence is
a fiscal-document marker, not a fiscal-impact value.

The right deterministic addition is a `measure_documents`/source-observation shape,
not URLs stuffed into prose fields. Suggested fields: measure identity, role, source
URL, archive artifact key, SHA-256, size, source snapshot, first seen, last seen, and
active/superseded status.

### Possible with today's 20 measures

| Rank | Opportunity | What it enables | Dependency / effort | Risk if wrong |
|---:|---|---|---|---|
| 1 | **Official documents panel in the existing modal** | A first-class “Official documents” tab modeled on Finance: grouped rows for resolution, full text, analysis, tax-rate statement, arguments, and rebuttals; role, publication/freshness, and official-source link. It replaces two generic external links with the actual primary-source set. | Persist/emit all 56 document records; medium. No PDF text extraction. | Low if labels remain the registrar's roles. High if presence is presented as content or endorsement. |
| 2 | **Election change feed and document revision alerts** | “What changed since last week”: eight to nine to 20 measures, TBD → assigned letters, newly published roles, withdrawn rows, and same-URL byte changes. This uses the three immutable snapshots as a product asset rather than merely parser input. | Emit per-lineage observations and SHA transitions; medium. | Medium. A source omission must be labeled “not observed,” not “withdrawn,” until confirmed. |
| 3 | **San Bernardino November ballot desk** | A clearly scoped county page: 20 measures grouped by jurisdiction type and jurisdiction, including a Needles three-measure bundle, exact election date, document completeness, and nine higher-threshold measures. This is useful now without pretending to be every Californian's ballot. | Static page/filter preset plus jurisdiction-type rules; medium. | Medium. Coverage language must say “San Bernardino records currently captured,” not “your complete ballot.” |
| 4 | **Passage-rule explainer on every pending card** | Show 50%, 55%, or two-thirds prominently and explain that a majority may not be enough; link into the existing Rules insight panel. This connects official current data to an existing site strength. | Preserve `vote_threshold` through generation; small. | Low. Avoid predictions; state the legal rule only. |
| 5 | **Verified-primary-source provenance** | “Checked Aug. 14 from SB County; 56 files checksummed,” plus a visible distinction between registrar facts and aggregator/derived fields. This is a trust feature the historical corpus cannot currently offer. | Scope/observation table and public archive policy; small–medium. | Medium if “verified” implies the county page was substantively complete rather than faithfully captured. |
| 6 | **Deterministic local-measure classification** | Populate display type for most/all current rows from the seven exact descriptions: Bond, Sales Tax, Charter Amendment, Ordinance, Transient Occupancy Tax, Property/Misc. Tax, and a reviewed transportation type. Derive jurisdiction type from explicit suffixes (city, school, college, hospital, park, county). This immediately prevents 20 new “Other” records. | Small reviewed mapping + unknown/fail-loud path; small. | Medium. Do not infer broad policy topic from a generic “Bond Measure” alone; a city bond is not necessarily Education. |
| 7 | **Official-document availability matrix** | A compact 20×role matrix: 20 resolutions, 19 texts, eight analyses, six tax statements, and three arguments for. It shows what voters can actually inspect and where official material is still missing. | Document records; small. | Medium if called “contestedness.” Today there are three pro documents and no opposing/rebuttal documents; publication timing/process is a major confounder. |
| 8 | **Current-source validation report** | Automatically assert 20 unique letters/IDs, threshold vocabulary, document-role uniqueness, exact page scope, and no current CEDA collision. Publish internally as a release artifact. | Most checks already exist; small. | Low. It is a validation report, not a public feature. |

The change feed is the most underused new capability. Static election pages are
common; a checksummed, source-attributed account of what an election office added,
removed, relabeled, or replaced over time is materially different and directly
supported by the architecture already built.

### Needs the other four planned counties (or substantially more observations)

| Rank | Opportunity | What it enables | Dependency / effort | Risk if wrong |
|---:|---|---|---|---|
| 1 | **Five-county November 2026 hub with explicit coverage** | One current-election surface separating statewide propositions from captured local measures, grouped by county and jurisdiction type, with last-checked/document coverage per county. | Four parsers/loaders plus shared site contract; medium after ingestion stabilizes. | High if marketed as a statewide or address-complete ballot. Five counties are not California-wide coverage. |
| 2 | **Cross-county publication/transparency comparison** | Compare how early counties publish full text, analyses, tax statements, and argument/rebuttal sets, and how frequently documents change. | Comparable role taxonomies and snapshot cadence; medium. | Medium–high. County procedures and deadlines differ; present process metrics, not quality rankings, until normalized. |
| 3 | **Authoritative threshold and jurisdiction-type distributions** | Current ballot mix by simple majority/55%/two-thirds and city/school/special-district type; eventually link those types to post-election outcomes. | Deterministic classification and multiple counties; medium. | Medium. Small-N and selected-county coverage need visible denominators. |
| 4 | **Argument-availability as a research signal** | Study whether publication of both sides/rebuttals correlates with margin, turnout, or measure type after results arrive. | Multi-county document histories + later outcomes; medium–large. | High if framed causally or as “controversy.” Availability reflects rules, timing, and filing behavior. |
| 5 | **Cross-source discrepancy ledger for historical backfill** | For each overlapping registrar/CEDA observation, show matches and disagreements in date, jurisdiction, letter, threshold, outcome, and totals; correct the canonical view only through reviewed assertions. | Historical county pages; provenance schema; medium–large. | High if records are silently overwritten. The 332/12 SB split makes this an audit workflow, not a blind merge. |
| 6 | **Post-election qualification-to-result panel** | Preserve the same stable measure identity from publication through official outcome, so pending cards become result cards without losing their source history. | Results ingestion and durable identity registry; medium. | High until the `year >= 2026` pending heuristic is fixed. |

Historical registrar backfill is particularly valuable for the existing Rules panel.
It can validate or correct CEDA's derived thresholds and recompute whether `passed`
is consistent with official threshold + yes share. It should produce assertions and
flags first. The five known threshold anomalies are not San Bernardino rows, so SB
will test the method rather than directly close those five cases.

### Needs PDF text extraction (deliberately deferred)

| Rank | Opportunity | What it enables | Dependency / effort | Risk if wrong |
|---:|---|---|---|---|
| 1 | **Cited ballot-question/full-text search** | Search exact official language across measures and expose page/role citations; populate `ballot_question` only where the document structure supports it. | PDF text/OCR pipeline, page citations, quality scores; large. | High for OCR errors and section-boundary mistakes. Keep source PDF beside every excerpt. |
| 2 | **On-demand briefing grounded in the official packet** | The free card remains deterministic; a user-triggered BYO/paid briefing receives the current official text, analysis, fiscal statement, and both sides, with role-level citations. No bulk pre-generation. | Extraction + briefing source manifest; medium–large after extraction. | High if stale documents or uncited model prose are mixed with official facts. |
| 3 | **Structured argument/fiscal fields** | Populate argument prose, named proponents/opponents, and fiscal impacts from the corresponding official roles. | Role-specific parsers, signature handling, validation samples; large. | High. Argument signers are not endorsements; tax statements are not neutral fiscal analyses. |
| 4 | **Semantic document redlines** | Explain how full text/analysis changed between checks, beyond the byte-level checksum alert already possible now. | Extraction, document alignment, page-aware diffs; large. | High where scans/OCR create false changes. |
| 5 | **Better historical analogs and CAP classification inputs** | Use actual measure language rather than generic labels such as “Bond Measure” for deterministic/assisted classification and similarity. | Extraction, CAP taxonomy implementation, evaluation set; medium–large. | High if similarity is presented as prediction or policy equivalence. |

### What not to build

- **No bulk LLM briefings.** They conflict with the deterministic-card/on-demand
  product model and would turn thin/generic inputs into confident-looking prose.
- **No outcome prediction from the current 20.** They have no outcomes, incomplete
  policy text, and one selected county.
- **No address-based “your ballot” finder yet.** County/jurisdiction names are not
  precinct/district boundary data; a wrong personalized ballot is worse than a
  clearly scoped county list.
- **No statewide-complete November branding from five counties.** Show a coverage
  map and denominators.
- **Do not populate argument/fiscal/proponent fields with URLs or presence flags.**
  Add document metadata instead.
- **Do not call argument presence “contestedness” yet.** Treat it as an observable
  publication event and test the interpretation later.
- **Do not ship the current semantic historical context for registrar rows.** With
  generic text, the diagnostic render classified Needles Measure L (“Bond Measure”)
  as mostly Education and offered visibly unrelated 2002 examples. Suppress it until
  sufficient official text or a defensible deterministic type/topic exists.

---

## C. Gated live-site integration plan

No phase advances automatically. Each phase ends with a reviewable artifact and an
explicit go/no-go decision.

### Phase 0 — isolated load and render — **implemented; gate failed**

**Actions executed**

1. Copied `scraper/data/ballot_measures.db` into the ignored scratch tree.
2. Loaded `sb_2026-11-03.jsonl` into that copy with `--commit`.
3. Repeated the load to test idempotency.
4. Regenerated insights against the copy.
5. Copied the generator/source tree and gave it read-only access to the existing
   finance databases.
6. Ran the production site CLI into a fresh scratch output.
7. Applied a two-line asset-write patch **only to the scratch CLI copy** and reran it
   to inspect the intended card/modal data.
8. Reparsed the oldest real snapshot and dry-ran it against the latest-loaded copy
   to test chronological safety.

**Load result**

```text
COMMITTED inserted=20 updated=0 deactivated=0 skipped=0 conflicts=0
second run: inserted=0 updated=0 deactivated=0 skipped=20 conflicts=0
```

- copied DB: 12,385 physical rows; 12,332 active nonduplicates;
- 20 active `SB_County_Registrar` rows; total `update_count=0`;
- zero duplicate fingerprints after load;
- live DB SHA-256 before and after:
  `73EEFB23F174C6FA31370CB5384C8C1AB318906BAE6C8E5871E3C1ABC2C860F1`.

**Exact production render result**

Generation exits successfully and reports 12,332 measures, 3,472 summaries, and
11,029 measures with vote data. It writes HTML to the requested location and a
second scratch-root HTML copy. It does **not** write `measures-data.json`.

The generated page calls `fetch('measures-data.json')` before initialization. The
scratch HTTP run returned 404 for that asset, so `resultsContainer` becomes:

> Could not load the measures database. Please refresh the page to try again.

The production repo already has an older `measures-data.json` with 12,312 records.
Generating in place would therefore be a silent stale-data failure rather than an
obvious 404: the 20 new rows would not render even though HTML/insights report the
new count.

**Intended registrar card after the scratch-only diagnostic patch**

For Needles Measure L, the card structure is:

- `2026` and `Upcoming` badge;
- title `Measure L: City of Needles — Bond Measure`;
- summary `Bond Measure`;
- no vote bar;
- metadata source `SB_County_Registrar`, with no topic/type label.

All 20 registrar measures join the four active statewide records in a 24-card 2026
hero carousel. Only three are visible at once. The intended “statewide first” sort
does not work because county normalization turns statewide nulls into the truthy
string `Statewide`; sorting falls through to `measure_id`. Registrar IDs contain
hashes, so their ballot order is effectively random (`Z, J, R, C, B, Y, ...`), not
`A–R, Y, Z`. The default results grid still excludes these pending 2026 rows, so the
hero/pending filter is their discovery path.

**Intended modal structure**

- Header: `Measure L`, `2026`, `City of Needles — Bond Measure`.
- Jurisdiction: `City of Needles • San Bernardino County`.
- Badge: `Upcoming Election`; results and ballot-question sections are hidden.
- Timeline: visible but incorrectly marks **Filed**. The registrar election-page URL
  does not match the statewide lifecycle URL heuristics, despite inclusion in the
  official election measures table proving an on-ballot state.
- Summary: only `Bond Measure`.
- Type/topic badges: absent because `category_type/topic` are null.
- Research/related/finance: no briefing, no precomputed related measures, and no
  local finance, all of which correctly use empty states/hidden sections.
- Historical context: generated for all 20, but unreliable on generic source text;
  Measure L is labeled mostly Education with unrelated analogs. This should be
  suppressed for launch.
- Links: generic Ballotpedia county page, generic county elections homepage, exact
  registrar election page (“Raw Data”), full-text PDF, and pending disclaimer.
  The analysis, resolution, tax statement, and argument documents do not reach the
  database/site. Nineteen rows have full-text PDFs; county Measure I has only its
  resolution and therefore no `pdf_url`.

**Null-outcome and panel behavior**

- No Python generation crash occurs on the 20 null outcomes.
- Card/modal vote sections correctly hide for pending records.
- `isPendingMeasure` is wrong for the future: `year >= 2026` remains pending even
  after official results are loaded.
- The site CLI's allowlist omits `vote_threshold`. All 20 authoritative values are
  present in SQLite but absent from site JSON; client exploration therefore defaults
  every one to `Simple majority`, including the five 55% and four two-thirds rows.
- Rebuilt Insights overview changes active 12,312 → 12,332, local 10,997 → 11,017,
  San Bernardino-normalized total 349 → 369, and 2026 total 4 → 24. Decided counts,
  vote-data counts, pass rate, and summary count do not change.
- The 20 null classifications increase aggregate “Other” topic/type totals by 20 in
  Insights. The per-measure JSON itself carries blank display labels.
- Threshold-insight and finance payloads are byte-equivalent as parsed JSON before
  and after; both operate on decided/matched historical scopes. Generation still
  loads finance for the same 181 measures/195 campaigns.

**Gate:** FAIL. Do not proceed to a live database load.

**Rollback:** none needed. All mutable outputs are under
`scraper/data/registrar_recon/phase0_review_20260814_1430/`, an ignored scratch
location. The live database and committed site artifacts retain their original
hashes/content.

### Phase 1 — identity, snapshot, and provenance hardening

**Work**

- Add scope snapshot watermarks and reject out-of-order/checksum-changed replay.
- Separate observation from explicit reconciliation/deactivation.
- Add row-decrease and withdrawal review gates.
- Implement the reviewed lineage registry/override ledger and contradiction rules.
- Add source-observation/provenance storage; prevent destructive source adoption.
- Make backups create-only and single-writer consistent.
- Add the adversarial tests listed in A2.

**Verification gate**

- all registrar tests green;
- 8 → 9 → 20 applies forward; repeating 20 is a no-op; 20 → 8 is rejected;
- URL/letter swap and withdrawn-letter reuse raise conflicts;
- truncation cannot deactivate without explicit authorization;
- adding/removing an earlier fixture cannot silently change a registered ID; and
- historical adoption fixtures preserve both source observations.

**Rollback:** revert code/schema migration in the branch; restore only the test DB
from its phase backup. No live data is touched in this phase.

### Phase 2 — site/data contract and pending UX on a copy

**Work**

- Make one generation API atomically write both HTML copies and both corresponding
  JSON assets; remove the divergent CLI/manual `_generate_html` path.
- Add generation assertions: same active count and content digest in both JSON files,
  HTML references an existing data asset, and root/scraper artifacts agree.
- Preserve `vote_threshold` and `election_type_imputed` through the allowlist.
- Add deterministic display category/jurisdiction type mappings with tests.
- Emit all official document records and add the modal document panel.
- Mark registrar rows `On Ballot`; sort by county/jurisdiction/letter, statewide first.
- Define pending from missing outcome + election state/date, not year alone.
- Suppress low-information semantic contexts.
- Decide whether Insights totals explicitly include pending measures or present a
  separate current-ballot scope; keep historical outcome denominators unchanged.

**Verification gate**

- scratch HTTP smoke fetches both HTML and JSON with 200s;
- 20 registrar cards are discoverable, letter-sorted, and show correct thresholds;
- all 56 documents appear exactly once with correct roles/URLs;
- results remain hidden and stage reads On Ballot;
- historical finance spot checks and all seven Insights panels match approved
  baselines except documented pending-count deltas; and
- generated root/scraper hashes pair correctly without modifying committed outputs.

**Rollback:** discard scratch outputs and revert Phase 2 code. Database copy remains
available for diagnosis.

### Phase 3 — controlled live database load

**Work**

- Select and record the exact approved latest snapshot ID/checksum.
- Dry-run against the live database; require 20 inserts, zero updates/adoptions,
  zero deactivations, zero conflicts.
- Take a uniquely named create-only backup and record its SHA-256.
- Commit once with explicit approval; immediately repeat as a no-op check.

**Verification gate**

- 20 active registrar records, 20 distinct registered identities, zero duplicate
  fingerprints, no changed pre-existing rows, no outcome values, and 20-skip replay;
- backup opens and passes `PRAGMA integrity_check`;
- provenance/scope watermark rows match the approved snapshot.

**Rollback:** restore the uniquely named pre-load backup, verify its hash and row
counts, and retain the failed database copy for audit.

### Phase 4 — generate and review deployable artifacts, no deployment

**Work**

- Regenerate Insights, both HTML copies, and both measure JSON assets from the live
  DB using the single fixed generator path.
- Review file diffs and serve locally over HTTP.

**Verification gate**

- expected count deltas only;
- card/modal/document/threshold/stage checks pass for representative city, school,
  county, and special-district rows;
- existing statewide Finance modal sentinels and all Insights panels pass;
- no stale/missing assets, console errors, or hash disagreement;
- review approves generated diffs before commit.

**Rollback:** restore the previous generated artifacts and database backup; do not
commit the failed generation.

### Phase 5 — reviewed deployment

**Work**

- Commit only approved database-dependent/site artifacts and code through a PR.
- Deploy through the normal GitHub Pages path after review.

**Verification gate**

- production `measures-data.json` returns 200 and contains the approved registrar
  IDs/count;
- a registrar deep link opens the correct modal;
- current-election hero, filters, documents, threshold, and pending state work;
- finance and Insights sentinels match Phase 4.

**Rollback:** revert the deployment commit to the last known-good HTML/JSON assets;
if needed restore the DB backup and regenerate, then redeploy the prior pair.

### Phase 6 — recurrent publication workflow

**Work**

- Each new snapshot produces a change report and copy-based render first.
- No-change snapshots record observation freshness without row churn.
- Additions/metadata changes may advance after automated gates; removals, identity
  proposals, source conflicts, and document replacements require review initially.
- Consider PR-based generated artifacts rather than direct write-back.

**Verification gate**

- two or more clean unattended cycles with forward-only watermarks;
- injected truncation, out-of-order snapshot, URL/letter contradiction, and stale
  JSON tests all fail loudly;
- run artifact names the snapshot, DB input hash, output hashes, and action counts.

**Rollback:** revert the generated-site commit and restore the immediately prior
database backup; keep immutable source snapshots and the failed run report.

---

## Verified, assumed, deferred, and decisions needed

### Verified

- Reviewed the committed parser, loader, their tests, SB extractor, both design docs,
  database model/operations, generator, external links, Insights builders, product
  backlog, lessons, known issues, pending prompt, and CAP/Georgia integration plan.
- Ran all 173 registrar tests from `scraper/` with a workspace-local pytest temp
  base: 173 passed (76 warnings).
- Live database SHA-256 remained exactly
  `73EEFB23F174C6FA31370CB5384C8C1AB318906BAE6C8E5871E3C1ABC2C860F1`.
- Copy load: 20 inserts; repeated load: 20 skips; zero fingerprint duplicates.
- Current collision surface: zero November 2026 cross-source candidates.
- Historical SB surface: 344 CEDA rows, 332 dated, 278 dated with jurisdiction, 54
  dated without jurisdiction, 12 undated.
- Exact site generation omitted the required data asset; scratch HTTP request
  returned 404.
- Diagnostic generation loaded 12,332 measures, the regenerated Insights payload,
  and unchanged finance coverage for 181 measures/195 campaigns.
- Out-of-order real-snapshot dry run planned eight regressions and twelve
  deactivations with no conflict.

### Assumed

- The existing normalized JSONL and local immutable snapshots are the approved bytes
  for this review; Phase 0 did not re-fetch R2 or county network content.
- The county's presence in the official November measures table means “On Ballot”
  for site lifecycle display, subject to the same source-completeness caveat.
- Static structure and generated payload inspection are sufficient for this phase;
  no visual-design signoff or screenshots were requested.

### Deferred by scope

- PDF text/OCR extraction and every content-derived field.
- Product fixes described above, live database mutation, committed generated-site
  changes, deployment, cron changes, finance work, and other-county work.
- External-link availability checking; URLs were inspected, not crawled.

### Decisions needed from Igor

1. Approve the recommendation to block live load until the four BLOCKER findings and
   static-asset defect are fixed.
2. Choose the stable identity authority. Recommendation: checked-in lineage registry
   + override ledger, with the DB storing the applied scope watermark.
3. Choose withdrawal policy. Recommendation: no automatic deactivation initially;
   explicit reviewed reconciliation with a two-snapshot confirmation fallback.
4. Choose cross-source model for historical backfill. Recommendation: preserve
   source observations and a canonical link; do not overwrite CEDA provenance.
5. Approve a normalized official-document table/payload and decide whether archived
   artifact URLs may be public or only source URLs/checksums are exposed.
6. Choose launch framing: SB-only ballot desk now, or wait for the five-county hub.
   Recommendation: SB-only is honest and useful after Phase 2; never imply statewide
   completeness.
7. Approve suppressing semantic historical context for low-information registrar
   rows until deterministic classification or extracted official text is available.
