# P2 results-import design review

**Verdict: ready with changes.** Keep the separate observation ledger, reviewed mappings,
unofficial-only presentation and certified-only database projection. Revise the contracts
below before accepting importer or projection implementations. This is approval of the
direction, not approval to import results or release a site.

Reviewed November 13, 2026, on `phase0-election-status`, HEAD `698c8ca7`. The design reviewed
is `docs/plans/results_import_design_20261113.md` as on disk, SHA-256
`86e7729c5727a0ae419360eb8351042ddfc8a9f6f20e0611a402fe89e1518058`.
Below, **D** refers to that file; other paths are repository-relative. Existing uncommitted
Explore changes and `docs/codex/PENDING.md` were left alone.

## Findings, ranked

These are design contradictions or missing requirements demonstrated against the current
code and saved evidence, not claims that an unbuilt importer has already corrupted data.
P1 means resolve before implementing the affected contract; P2 means resolve before accepting
the affected chunk. Optional improvements are separated below.

### R1 — P1: the multi-county outcome rule conflicts with the proposed status precedence

**Evidence:** D:196 keeps county-portion `passed`; D:199 requires badges/statistics to use
`combined_passed` without falling back; D:227 defines the certified state using `passed`;
D:254 puts the new unofficial state after a recorded outcome. Today
`scraper/src/website/election_status.py:99` checks raw `passed` first. A read-only,
in-memory probe with `passed=0, multi_measure_id='REG:test', combined_passed=1` returns
**failed**. With no combined result it still returns **failed**. Both contradict §3.
`build_measure_pages.py:117` has the same precedence. Adding an unofficial branch after
those checks does not solve either case.

**Change:** specify a shared **effective whole-contest outcome** before status/rendering:
for a current-election grouped row, use only the selected certified combined observation; a certified
portion alone supplies neither a measure-wide outcome nor a historical outcome denominator.
Historical CEDA groups use their reviewed recorded combined outcome without acquiring a
new certification claim or requiring a current-election ledger observation.
Retain the county's own `passed` solely as the row/source fact. Apply this to Python, JS,
SQL statistics, filters, export semantics and all aggregate consumers, not only badges.
For grouped rows, portion vote fields must also not trigger the generic “Result unknown”
fallback. Test opposite county/combined outcomes and certified-portion-only cases.

The new columns also need an explicit export path: `scraper/scripts/generate_site.py:128`
filters fields into `BallotMeasure`, then `:235` reconstructs website dictionaries from
those models. Adding columns to SQLite alone will drop the new group/outcome/provenance
fields. Either extend the model/field contract or attach them by immutable integer ID at
the common build boundary. Preserve `id`.

### R2 — P1: the full-CSV fixture recommendation contradicts the privacy contract

**Evidence:** D:54 says the San Mateo raw CSV contains an unmasked two-voter split and
must stay private; D:329 recommends committing it whole if smaller than about 5 MB.
File size has no relationship to that disclosure. I did not find the CSV among the four
provided results artifacts, so I have not independently verified its small-cell contents.
The contradiction in the stated policy is sufficient to reject the recommendation.

**Change:** keep full precinct files in private immutable evidence storage regardless of
size. Commit a synthetic or reviewed sanitized fixture preserving the parsing structure,
with small-cell and subtotal edge cases represented synthetically. A trimmed real file is
not automatically safe, nor is primary suppression sufficient if totals reveal suppressed
cells. Record the full private artifact's hash and the derivation of the public fixture.
Review public fixtures separately from public contest-total observations.

### R3 — P1: capture ordering and observation identity cannot safely express corrections

**Evidence:** D:111 defines the observation ID from capture hash, contest key and scope;
D:131 selects the latest capture, with certified above unofficial. These rules leave two
concrete counterexamples:

- Re-download an older report today: its capture time is newer, its source report is older.
  “Latest capture” selects stale counts unless source order is checked separately.
- Correct a parser/mapping error, or attach certification evidence to unchanged result
  bytes: capture hash + contest + scope is unchanged. The revised observation collides
  with the earlier ID, although `supersedes` requires a new immutable observation.

**Change:** separate raw source-record identity from normalized observation identity.
Include election/source/scope/county and the normalized payload or interpretation revision
in the latter; include certification-evidence references when status changes. Exact reruns
of the same interpretation remain no-ops. Require correction reasons and a same-contest,
same-scope, acyclic supersession relationship.

Use source report sequence/as-of evidence to reject stale candidates; capture time is
provenance, not result chronology. Missing time, equal-time conflicts and incomparable
sources require review. The reviewed selection manifest must be the **actual build input**,
not just a receipt of an automatically recalculated “latest” choice. It must also support
explicit retraction of an erroneous certified selection without deleting history.

### R4 — P2: a predecessor hash alone does not detect every edit or deletion

**Evidence:** D:110 says any edit/deletion breaks the chain. Deleting its last line leaves
every remaining predecessor hash valid; changing the last payload also has no successor
to expose it. A three-line in-memory prefix check reproduced the truncation case.

**Change:** anchor both the expected line count and final digest in the reviewed release
manifest; compare the existing prefix with the approved Git parent for append-only changes.
Define canonical UTF-8 serialization, LF boundaries, exactly what bytes are hashed, schema
version and genesis value. Protect ledger files against newline conversion, not just raw
fixtures. Stage a complete validated batch and replace atomically under one writer; a failed
contest must not leave a partial append. Git review and an anchored manifest can provide
the required guarantee without treating a chain as a signature or proof of source truth.

### R5 — P2: mapping and certification need evidence tied to the exact report and contest

**Evidence:** D:158's identity example includes county/letter/jurisdiction but not election
date or canonical identity; D:167–170 checks the target row, while the source contest title
can be reused in a later election. D:161 cites a database cell as the approval-rule source.
D:290 accepts named certification evidence in a capture manifest without spelling out
how it certifies these particular counts. The saved San Mateo page still links a
`52_SOV%20placeholder.pdf` (HTML line 1314); a link labelled Statement of the Vote is
therefore insufficient evidence even in the provided corpus.

**Change:** require election date, immutable DB ID and canonical key, expected source
contest identity/aliases, county, jurisdiction, designation and scope. Check the artifact's
election/report identity too; do not infer it from the folder name. Resolve source-vs-DB
name differences in a reviewed crosswalk backed by ballot question/document evidence.
Keep the approval rule's authoritative document/hash/page and exact comparator, not just
`measures.vote_threshold = 50%`.

Certification must identify the certifying authority, election, report/revision or exact
result artifact, scope, statement/page, certification date when supplied, and reviewer.
A generic certification PDF must not certify an unrelated earlier unofficial report.
“Final unofficial,” 100% precinct reporting, a deadline and a download label never qualify.
The certification annotation itself should be immutable and included in the release pin.

### R6 — P2: “all counties certified” is necessary but insufficient for a derived total

**Evidence:** D:207 permits summation once every mapped member county has a certified
observation. It does not explicitly exclude a county's file repeating a whole-district
total, require non-overlapping electoral portions, or define invalidation when an input
is corrected. The earlier transition design explicitly warned about repeated regional
totals. D:185 also acknowledges the three-measure inventory still needs confirmation.

**Change:** pin a reviewed group membership and aggregation rule; prove each input is a
disjoint county portion of the same contest/election with the same voting rule and final
reporting coverage. Require exactly one selected certified portion per member, including
explicit zero portions when applicable. Reject duplicate portions, consolidated totals
masquerading as portions, absent members and inconsistent identities. Store every input
observation ID plus mapping/algorithm version. A revised input invalidates/recomputes its
derived observation and all projections in one reviewed release. Label the output
“CalBallot total from certified county results,” rather than implying an authority certified
the derived file itself. Prefer an authoritative consolidated result when available.

### R7 — P2: zero totals, unknown rules and percentage units need executable contracts

**Evidence:** D:240's inequalities produce `True` for both 55% and two-thirds when
yes=no=0. Whole-number validation at D:171 does not reject negative integers. The design
also rehearses unknown thresholds but supplies no current certified-counts/unknown-outcome
display state. Separately, `scraper/scripts/generate_site.py:267` multiplies any percentage
≤1 by 100: projecting **0.5%** or **1%** on the natural 0–100 scale would display **50%**
or **100%** through that existing path. I reproduced that transformation in memory.

**Change:** require nonnegative integer counts (not booleans), a positive yes+no denominator
before calculating a rate/outcome, and an explicit percentage unit. Never normalize new
results by magnitude. Keep null distinct from zero. With zero votes or an unreviewed rule,
display available counts and an explicit unresolved/held result, without a computed call.
A current observation can be incomplete; “Result unknown: historical rows only” must not
force it into an inaccurate pending or certified-passed state. Test zero, one vote,
majority ties, exactly 55%, exact two-thirds, adjacent integer outcomes, 0.5%, 1%, 99.5%,
and Python/JS parity. Compute thresholds and margins rationally; format afterward.

### R8 — P2: the capture convention permits replacement and omits an independent SMC total

**Evidence:** D:65 uses one folder per save day and fixed filenames. A second save that
day replaces the first unless prohibited. D:82's hash command includes an existing
`SHA256SUMS.txt`, then rewrites it; rerunning it can leave a self-entry for the old bytes.
The saved SMC page has a same-report **Results on PDF** link to
`52_ElectionSummaryReport_SF_11-06.pdf` (line 1300), but the seven-file list omits that file.
Summing a detailed CSV against a total produced by the same summation is not an independent
cross-check.

**Change:** use an immutable capture ID/time subfolder per save, including offset/UTC and
source report identity. Refuse replacement; exclude manifests/checksum outputs from their
own artifact enumeration. Hash exact raw bytes, record source/final URL where known,
capture method/person/time and report/as-of evidence, and freeze the manifest last. Add
SMC's summary PDF from the same report to reconcile CSV totals and detect subtotal/method
double-counting. The existing registrar store offers useful interfaces, but
`storage.py:288` writes artifact bytes without an exclusive-create check: unique snapshot
names and immutability enforcement still matter.

## Answers to the nine questions

### 1. Ledger versus database

**Use the committed observation file for this bounded rollout, with R3/R4 corrected.**
Hundreds or a few thousand contest observations are modest even after expansion to about
460 measures. Reviewable normalized diffs and no unofficial production-DB writes are useful.
A database does not by itself solve source identity, stale ordering or review; a separate
staging SQLite store would also preserve the production boundary, so that is not an argument
against tables in principle.

Give the release an immutable selection manifest containing the ledger head/count, mapping
and schema versions, selected IDs by contest/scope/county, certification evidence, build
date, and projected DB hash. Recover **raw files + manifests + ledger + mappings + selection
+ code**, not the JSONL alone. For certification, write the selected observation references
and corresponding row/combined columns in the same database transaction, then build from
that frozen DB/ledger pair. Missing or mismatched references must stop a strict build.
Importer workers should produce independent candidate batches; one validated append process
owns the ledger. Do not let parallel workers independently assign its sequence numbers.

### 2. Can unofficial numbers leak into history or other outcome consumers?

**Not merely by adding a nested `result` object.** `has_recorded_votes` inspects only
`percent_yes`, `percent_no`, `yes_votes`, `no_votes`, `total_votes`, `pass_fail`
(`election_status.py:66`, `:86`). None of the existing aggregate paths inspected reads the
proposed nested object. Keep all those top-level fields and `passed` unchanged for
unofficial observations; never use a convenience merge that copies nested votes upward.

The outcome-consumer inventory must extend beyond P0.1's visible badges:

| Consumer | Current behavior / required treatment |
|---|---|
| Status and static detail | `election_status.py:99`; `build_measure_pages.py:117`, `:245`: raw outcomes and vote fields. Use the shared scope-aware projection. |
| Browser cards/list/modal, filters, sort and statistics | `generator.py:10899`, `:10938`, `:11013`, `:11037`, `:14184`, `:14292`, `:14384`, `:14439`: raw `passed`/votes, plus default year exclusion. Add explicit unofficial/filter behavior and effective outcomes; do not just add a label. |
| Explore | `generator.py:11689` and modal at `:11998`: raw decided rows; keep unofficial nested and exclude grouped rows lacking a certified combined result. Deduplicate complete groups in cross-county cohorts. |
| County historical context | `local_measure_context.py:121` excludes registrar records, then `:125` excludes missing outcomes; `:161` aggregates raw `passed`. No current unofficial leak, but historical CEDA groups need the same effective-outcome rule when populated. `county_content.py:154` renders those results. |
| Build-time statistics/recommendations | `database/operations.py:481`, `generator.py:461`, `:480`, and `generate_site.py:348`, `:435`: DB/model raw outcomes. Update before projecting county `passed`; changing JS alone leaves conflicting totals. |
| Insights and other exports/research | `generate_insights.py:263`, `:315` and later cohorts; browser SQL materialization at `generator.py:9857`; `database/operations.py:360`; API/raw export models; `research/sources/historical.py:257`, `:366`: no ledger reads today. Preserve raw row fields as explicitly scoped facts and supply effective outcomes to claims about the whole measure. Hidden Insights is not permission to generate contaminated aggregates. |

`generate_site.py`'s model conversion needs R1's new-field transport. Existing export gates
also pin exact column schemas (`check_export_contract.py:11`); either leave those raw exports
unchanged and document their scope, or version/update their contract explicitly. The normal
registrar loader rejects legacy result fields at `loader.py:367` and updates a source-field
allowlist; extend ownership tests for the new result/group fields. Test both refresh after
projection and attempts to inject outcomes through document loading. Generic maintenance
or deduplication code is not a substitute for the dedicated results transaction.

### 3. Mapping and the Santa Cruz failure

**The proposed route is correct; fail-closed identity needs R5's stronger specification.**
Read-only query joining `statewide_ballot_entries.measure_id` to `measures.id` found exactly
14 qualified entries for 2026-11-03, numbered **1–5 and 37–45**, plus withdrawn id 1 with
no proposition number. The special mappings are correct: **3 → 10960 (`INIT_1993`),
4 → 10956 (`SB_42`), 5 → 2 (`SCA 1 …`)**. Enforce election-date-qualified uniqueness,
qualified status and exact one-to-one joins; do not infer these from canonical strings.
Id 1 belongs in the explicit no-contest exception set, not the expected returns count.

In the saved SB HTML, I extracted **20 `h2` MEASURE contests: A–R, Y, Z**, matching the DB's
20 letters and jurisdictions through the reviewed Measure I alias. There are separately
**14 PROPOSITION headings**, explicitly prefixed San Bernardino County. They must be
ignored with a reviewed reason or stored only as county portions, never mapped as statewide
totals. Measure Y starts at saved HTML line 15102; Measure I at 15477.

A target-row identity check would catch the Santa Cruz-style overwrite if the mapping pins
the independently reviewed original identity. It cannot catch an initially wrong mapping
that merely copied the current target row's attributes. Require source-to-ballot evidence,
not a self-consistent ID/title assertion. Validate the whole batch before any append/write;
reject missing/duplicate/unexpected contests and invalid aliases. Explicitly distinguish
judicial retention YES/NO contests from ballot measures rather than relying on YES/NO alone.

### 4. Multi-county model

**The row/combined distinction agrees with the CEDA revision's N1.** It becomes one usable
model only with shared field definitions, scope semantics, projection and cohort rules.
Keep individual row provenance and separate combined-observation provenance; a single
`result_observation_id` cannot ambiguously name both. `multi_measure_id` is a contest key,
not proof that every row in its group is a disjoint input. Statewide/general aggregates count
one contest, while county listings may show its membership once per relevant county.

“Only a whole-contest observation determines the outcome” is right. It must not suppress
the state/as-of label of an available portion, or turn a certified portion into an unofficial
one. Also, D:211's “no combined figure before certification” conflicts with D:206's possible
official consolidated result and D:226's unofficial whole-contest state. Clarify: **no
CalBallot sum of unofficial portions**; an authentic official consolidated unofficial total
can be shown as unofficial if policy permits. Otherwise explicitly defer that input.

I confirmed the three IDs and identities in the DB. **I cannot certify that they are the
only multi-county contests.** The supplied census calls its cross-county list incomplete,
and neither the DB nor the SB summary establishes all district boundaries. Review scope
for all 49 mappings, with evidence for every `contest` assertion, rather than defaulting
the other 46 to whole-contest. The exact other-county membership and non-overlap remain
acceptance gates. No new `measures` rows are needed merely to store other counties' portions.

### 5. Integer rules, rounding and statewide majority

For a reviewed yes/no rule and **N=yes+no > 0**, the proposed math is correct:

| Rule | Exact comparison | Minimum yes votes |
|---|---|---|
| Strict majority | yes > no | floor(N/2) + 1 |
| At least 55% | 100×yes ≥ 55×N | ceil(55×N/100) |
| At least two-thirds | 3×yes ≥ 2×N | ceil(2×N/3) |

Exclude undervotes/overvotes from that denominator; do not substitute ballots cast,
registration or “Times Cast.” Preserve those source quantities separately. This validates
the arithmetic for those rules, not the legal assignment of a rule to each contest.

The true-side rule is necessary but not a complete formatting specification. Apply it to
both sides of every exact threshold, including strict-majority ties and repeating two-thirds;
display “two-thirds,” not a decision cutoff of 66.67%. Define a maximum useful precision and
an explicit “just below/above” or exact-vote explanation when ordinary decimal formatting
would mislead. Preserve the source's printed percentage separately. Tolerance should be
derived from the source's documented printed precision. Both supplied SOS files pass 0.05
percentage-point checks; maximum discrepancies were approximately **0.042698** and **0.049168**.

**Recommend a reviewed majority rule for the 14 only after capturing the authorities.**
The legal references to verify are California Constitution **Article II §10(a)** for
initiatives/referenda, **Article XVIII §4** for constitutional amendments, and **Article XVI
§1** for applicable state debt authorization. Also review the particular enabling/referral
text, especially Proposition 4/SB 42; “legislative statute” is not itself an initiative-rule
citation. Pin each contest's authority, section and captured text, rather than importing a
blanket default from its name.

No network was used, as requested. The supplied results files do not contain those
constitutional provisions, and I have **not independently verified their authoritative text
in this review**. The local Prop 4/5 law PDFs did not establish a blanket adoption rule for
all 14; their recall-vote majority language is not evidence of Proposition 5's own adoption
threshold. The existing “Approval requirement not listed” fallback must remain until the
rule packet is reviewed. Database query: 49 local rules comprise 32 `50%`, 8 `55%`, 9
`66.67%`; the 14 statewide rules are null. Resolve the last local string to an exact rational
rule from its reviewed source, never the decimal string alone.

### 6. Status contract and browser checker

Adding `unofficial` is compatible **as an observation-driven state, outside
`DATE_DRIVEN_STATUSES`**. Preserve withdrawal precedence and all future Upcoming/Election day
behavior. Apply R1's effective-outcome rule before evaluating recorded outcomes; then handle
selected unofficial whole-contest evidence, portion-only availability, historical unknowns,
and the calendar fallback. Reject inconsistent current provenance in strict builds rather
than silently treating arbitrary raw `passed` as certified. Existing historical outcomes
remain “recorded,” not retroactively “Certified.”

The forward-only browser clock may advance calendar states only. It must never promote
unofficial to certified or replace an observation's source time with browser/build time.
Do not blindly put `unofficial` into the calendar rank array to make tests pass.

Concrete changes needed beyond `election_status()`:

- `attach_election_status` (`election_status.py:251` onward) removes status/link fields and
  attaches only calendar states. Define attachment and link behavior for unofficial and
  certified observations separately; keep validated official links available as specified.
- JS `getElectionStatus` rejects non-calendar built values today; labels, static
  `outcome()`/`election_status_html()`, `isPendingMeasure`, section notes, filters and local
  cards all need the new projection. A nested-only unofficial probe currently returns
  `results_pending`, demonstrating that storage separation alone is not status integration.
- `check_election_status_browser.py:58` classifies null-outcome/null-top-level-vote unofficial
  rows as calendar-dependent. It then rejects `unofficial` at `:73`. Resolved rows are
  forbidden any status/link at `:80`; fixed badge maps at `:46`–`:47` cannot represent the
  new states/certified labels; `LINKED` at `:44` covers only election day/pending.
- Update these independent classifications from validated observation/scope fixtures,
  including certified portion without combined, rather than trusting the rendered status
  under test. Keep current-row enumeration independent of attached status.
- The no-calendar-row transition fallback is already guarded (`:280` onward). Retain it,
  and add an open unofficial/portion modal that stays stable across midnight. Check local
  cards too, not just rendered statewide hero badges.

Keep the existing strict guards for current rows' canonical election dates and unexplained
historical “pending” rows. Add ledger/selection/mapping hash checks, scope and evidence
validation, and projection consistency. A new observation state must not bypass those guards.

### 7. Verification and certification evidence

The rehearsal list is good but needs explicit assertions for R1–R8 and these boundaries:

- Same bytes with a corrected parser, mapping or new certification; a stale report captured
  later; equal-time conflicts; certification withdrawal; missing/corrupt selection target;
  ledger tail truncation; failed batch append; concurrent append/retry.
- An older election reusing the same letter/number, a wrong-but-existing target ID, omitted
  and repeated portions, repeated consolidated totals, group membership correction, and a
  corrected input invalidating a derived total.
- CSV precinct/method/subtotal duplication, repeated headers, missing result choices,
  explicit zero versus blank cells, and rejection of malformed or formula-like count cells.
  Reconcile SMC against the same-report PDF, not merely the importer's own sum.
- All six post-election states plus future calendar states, current incomplete/held data,
  unsupported thresholds, field-unit edges, filters/“has votes”/sort/export behavior, and
  all three display widths. Long as-of/source strings must be escaped and links validated.
- Before/after unofficial projections, assert byte-identical top-level legacy votes/outcomes,
  and identical historical cohort membership, denominators and aggregate results. Test
  certified portions with missing/opposite combined outcomes on every aggregate path.
- Migration idempotency on both pre-P2 and future CEDA schemas; exact selected-ID/field
  allowlists; transaction rollback; selected observation references matching DB projections;
  refresh afterwards preserving all new result fields and still updating ordinary documents.

The unofficial preservation gate is appropriately narrow, but needs a **reproducible frozen
baseline**, not a blanket assertion against a differently timed build. Existing code has the
known null-`last_seen_at` regeneration path (`verify_official_documents_release.py:179`).
Freeze it or retain a reviewed, exact-ID timestamp exception; do not loosen the gate broadly.
Keep `official_results` stable for unofficial rows by design, or explicitly justify a changed
attachment rule instead of accidentally failing the two-field allowlist. For certification,
write a separate allowlist for projected row/combined/provenance fields and expected aggregate
changes. An unofficial allowlist cannot describe a certified release.

Certification evidence is **not strict enough as written**; use R5's binding to the exact
result/report and scope. Independently reviewed certification fixtures are required before
promotion. No live certification evidence was checked here.

### 8. Chunk order, parallel work, cutoff and Igor's eight questions

Use this order:

1. **(a0) Contract and evidence:** immutable registration, observation/selection schemas,
   mapping/scope/rule format, fixtures policy, shared outcome semantics. Resolve R1–R8.
2. **(a1) SOS and (b) county adapters:** parallel only after a0 interfaces and each source's
   fixture are pinned. Emit candidate batches; serialize ledger appends. Mapping/scope review
   is an acceptance dependency, not an assumption supplied by a parser.
3. **(c-core) Projection plus certification transaction rehearsals:** implement all states
   and database-copy behavior against synthetic fixtures now, including schema transport and
   whole-contest consumers. Do not first write the certification path on December 4.
4. **(c-release) Optional unofficial release**, after independent review and Igor's approval.
5. **(d) Evidence acquisition/reconciliation/promotion:** certify only when appropriate actual
   artifacts arrive; incomplete groups remain explicitly unavailable.

This removes a dependency contradiction: D:317 says skip the unofficial state if late, while
D:303 makes certification depend on (c). Skip the **unofficial release**, not the shared
projection implementation or its rehearsals. Also reconcile D:340's Explore-first wording
with the current checklist/Working List: **P2(c) precedes E2c**. They should not concurrently
edit `generator.py` in this checkout.

November 26 is a sensible product cutoff for an optional release, not an evidentiary deadline.
Continue capturing and validating afterward. Certification dates are planning checkpoints,
not automatic status switches; a source may publish qualifying evidence earlier or later
than the planned save day. The November 18/24 estimates remain provisional until county
fixtures are available; a blocked county importer should not block evidence preservation.

| Igor question | Recommendation |
|---|---|
| 1. File or DB | File, with anchored selection, correction semantics and atomic append; no need for a production observation table yet. |
| 2. Statewide majority | Yes after the source/rule review above; not a guessed default. |
| 3. Nov 26 cutoff | Yes for the optional unofficial release; retain common implementation/rehearsal work. |
| 4. Unofficial multi-county portions | Yes, clearly scoped. Distinguish unavailable combined results from unavailable county counts. |
| 5. Other counties' certified evidence | Yes, after membership/scope review; obtain supporting certification statements as well as vote totals. |
| 6. Wording | Prefer explicit “Unofficial” and “Certified” in text on cards as well as detail; label derived totals and portions. Final placement remains Igor's choice. |
| 7. Precinct results | Agree to defer public precinct results. Private ingestion may still require detailed files. |
| 8. Full CSV fixture below 5 MB | **Disagree.** Public fixture approval depends on privacy/content, not file size (R2). |

### 9. Hand-save list and evidence convention

Add **SMC's same-report summary PDF**, the approval-rule authority packet, and at certification
the **actual** official result/Statement of Vote documents and their certification statements,
not only SB's index page. Save the other counties' exact contest pages/tables plus certification
and scope evidence. Keep complete source files privately; page references in a transcription
must resolve to those files. A validated manual observation form needs the same count, identity,
scope, status and review gates as an importer.

The original four script saves are now in the dated repo-local raw folders; their checksum
files match all four artifacts. Keep their `script` acquisition labels and original capture
times when registering them; copying on November 13 is not a new result observation.
The SOS reader-page PDF is useful context/human link-check evidence but not automatically
certification, nor proof that its values match a separately saved API response. Record a
manual link-check receipt explicitly. Do not use any of these captures to authorize further
automated fetching.

The folder/checksum convention becomes adequate with R8's immutable per-capture directories,
manifest binding, raw private retention and recovery checks. Unknown source timezones stay
unknown until reviewed; keep `as_of_text` rather than silently assuming an offset. A filename
and hash alone do not establish election, scope, certification or chronology.

## Verification receipt and limits

- Read the design, transition design, layout answer 2, CEDA revision N1, checklist, current
  work index and relevant status/loader/storage/build/aggregate/checker code. No code or data
  was edited and no build, network fetch, importer, migration or test suite was run.
- Queried production only through `sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)`.
  Current election counts are **20 SB + 29 SMC + 14 statewide = 63**; all have null `passed`
  and `yes_votes`. Queried mapping/rule/identity fields and schema; new combined/provenance
  columns are not yet present. No backup or production write was needed.
- Read saved/untrusted files using `python -I`; parsed HTML inertly and JSON as data. Verified
  full hashes against both `SHA256SUMS.txt` files. SOS hashes:
  `3d4b05aff814…` and `647fb5d31206…`; SB `355379126d6a…`; SMC page `6b86b169cdba…`.
  SOS reporting times are November 5, 5:47 p.m. and November 6, 11:00 p.m.; both contain
  the expected 14 numbers. These are saved-source assertions, not live verification.
- SB HTML line 104 says **“Final Unofficial Election Night Results”** and line 134 identifies
  November 3, 2026, Summary Report #5. Verified its 20 measure/14 proposition headings.
  The SMC saved page links CSV media 9153 and a placeholder Statement of Vote. No SB XLSX
  or SMC CSV was present in the supplied dated result captures; their layouts, row counts,
  small cells and aggregate totals remain unverified here.
- Ran only in-memory probes for status precedence, zero-denominator rules, percentage scaling
  and hash-chain truncation. They demonstrate contract gaps; they are not results imports.
- Multi-county inventory completeness, source consolidation semantics, authoritative legal
  text for all rules and future certification artifacts remain explicit evidence gaps.

Production DB SHA-256 before and after review:
`ef1359e482db2c54fe41068771932aaac7c9fc1db372e2e1d8cbbed1f505d9da` — **unchanged**.
Only this response is committed. No push.
