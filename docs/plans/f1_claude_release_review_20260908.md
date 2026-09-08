I have now traced the full call chain — parser lineage/override → loader identity resolution/persistence → `documents_for_website` grouping → generator guard/attach → CLI build → verify/browser evidence — and cross-checked the claims against the actual JSONL, load/verification reports, and diffs. Here is my independent judgment.

---

# Verdict: READY WITH CONDITIONS

This is a genuinely careful release. The data-integrity machinery (atomic backed-up load, re-plan under `BEGIN IMMEDIATE`, canonical-ID resolution, fail-loud document/id guard, per-role reconciliation) is sound, and the evidence pipeline (`prepare → build → verify → browser`) exercises the *real* CLI against a faithful production copy rather than a cached preview. I found **no data-corruption, misattribution, or security blocker.** The conditions below are release-execution prerequisites plus two low/medium voter-facing follow-ups — none require code changes to be safe, but several must be honored during the actual load/publish.

I did **not** execute pytest, query the binary SQLite files, run Chromium, or touch R2/production. Where a claim rests on a report I read but did not reproduce, I say so.

---

## Blockers

None that stop publication on data-integrity or security grounds.

## Conditions (must be honored at load/publish time)

**C1 — The recorded `candidate_sha256` will not reproduce on a real production load; re-run structural verification, don't match hashes.**
- Evidence: `verify.py:120` records `index.html`/`measures-data.json` SHA-256; `_update()` (loader.py:870) stamps `updated_at`/`last_seen_at` with `datetime.now()`, and `BallotMeasure.__post_init__` (models.py:119-120) fills 129 null `last_seen_at` at build time. All are embedded in `measures-data.json`.
- Impact: A real load/build produces different timestamps → different file hashes than `verification.json` claims. Treating the recorded SHA as a gate would fail spuriously (or worse, tempt reuse of the rehearsed artifacts).
- Correction: After the real load, re-run `verify.py`; require the **structural** invariants (below) to pass and accept timestamp/hash divergence.
- Confidence: high; directly verified in code.

**C2 — The F1 code is uncommitted working tree; publishing must commit it and rebuild, not push rehearsed artifacts.**
- Evidence: `git-state.txt` shows `measure_documents.py`, `generator.py`, `loader.py`, `county_config.py`, `local_measure_context.py`, `generate_site.py` as `M`/`??`. The candidate `E/site/` was built from `E/measures.db` (a copy), not from a production load+build.
- Impact: Pushing the committed root pair as-is (at `481d364`) publishes the 29 SMC measures **without** the document panels/SB refresh, because that pair predates F1.
- Correction: commit code + load production + regenerate root **and** mirror + commit root pair only. See checklist.
- Confidence: high; directly verified.

**C3 — Rehearsal used `--output site/…` (single file); production build dual-writes root + `scraper/` mirror.** The byte-identical mirror must never be staged, and `--deploy` must not be used (it stages the mirror). Evidence: `build.py:22-24` passes `--output`; `generate_site.py:website_output_paths`; CLAUDE.md hard rule; release doc §"Publication scope". Confirm root/mirror byte-identical post-build; stage only the root pair.

---

## Findings (follow-up work, not blockers)

**F1 — Measure I's new "Sales Tax" historical context pools incompatible vote thresholds. [MED, voter-facing]**
- Evidence I directly verified: `sb.jsonl` line 6 (Measure I, SBCTA) has `"vote_threshold":"66.67%"` (a 2/3 special transportation tax). `artifact-diff.json:900-910` shows its new panel: `{category_type: "Sales Tax", total: 31, passed: 17, pass_rate: 55, since: 2000}`. `local_measure_context.py` aggregates by `(county, category_type)` only — it does **not** filter by threshold or general-vs-special.
- Trigger: description rename "Local Transportation Improvement Program" (unmapped, no context) → "Transactions and Use Tax" (→ "Sales Tax" alias) makes Measure I newly join a pooled county cohort that includes 50%-threshold general city taxes.
- Impact: A voter sees "55% of SB sales-tax measures passed" beside a countywide 2/3 special tax — technically true but omits the distinction that most materially governs its odds and purpose. This is the **one new analytical classification** in the release (the 13 preserved bond/sales-tax panels are continuity; this one is net-new), so it deserves the most scrutiny.
- Correction (cheap): either render the current measure's own threshold in the panel, or suppress `local_historical_context` when the measure's `vote_threshold` is atypical for its cohort; at minimum record it as a known limitation. Byte-identical documents prove *continuity of the measure*, not *soundness of the cohort comparison* — the release doc itself raises exactly this question and consciously shipped it.
- Confidence: threshold and context values — high (verified). Degree of misleadingness — medium; depends on the 31-row cohort's threshold mix, which I could not query (see "further check").
- Note on soundness "in the first place": the same threshold-pooling imprecision already affects the 27 pre-existing panels (GO Bond mixes 55% school bonds with 2/3 bonds). Pre-existing, but F1 propagates it and adds its sharpest instance.

**F2 — The Chino Hills J override is an unconditioned, hard-coded lineage assertion with no code-level byte check. [LOW, durability]**
- Evidence: `county_config.py:49` `("20260831T185331Z", 12): ("20260727T171800Z", 4)`. `parser._link_snapshot` applies overrides *first and unconditionally* (parser.py:491-511), before URL/letter/semantic matching, and `lineage.observe()` then adopts the Aug 31 row's content/URLs regardless of what they are. The 4 byte-identical SHA-256s cited in the release are corroborated in the data (`artifact-diff.json:1040-1136`: resolution `4b158…`, text `3a520…`, analysis `d9a86…`, argument_against `bcd96…`; argument_for is the new `caceef…`), but nothing in code enforces them.
- Why safe now: the target snapshot is immutable, the override is keyed to that exact snapshot+row (Sept 7 and future snapshots are unaffected and re-establish continuity via unique-URL matching — verified by `test_registrar_parser.py::test_reviewed_chino_hills_rename_preserves_origin_without_weakening_guard`), and `retrieval.json:65` honestly retains the pre-override `LineageConflictError`.
- Risk: this is the 3rd accumulating override; a future mis-entered `(snapshot,row)→(origin,row)` pair would silently misattach an identity/documents with no guard, because the override bypasses the very ambiguity check that protects everything else.
- Correction: have the override optionally assert the set of shared document SHA-256s it relies on (fail loud if the immutable bytes ever fail to match the reviewed fact), or add a fixture test pinning those 4 hashes. Not required for this release.
- Confidence: high (verified code + data).

**F3 — `verify.py` constrains non-registrar rows to a field whitelist but not registrar rows. [LOW, verification strictness]**
- Evidence: `verify.py:59-60` asserts non-registrar deltas `<= {'last_seen_at'}`; registrar rows only get *specific* fields checked against the DB (`verify.py:61-67`), with no catch-all forbidding an unexpected extra field.
- Impact: A hypothetical stray change to a registrar row's non-whitelisted field (e.g. an outcome or editorial field) would not hard-fail `verify.py` — it would only surface in the `changed_fields` Counter. Empirically clean here: the Counter (`verification.json:10-24`) shows only expected fields (no `passed`/`yes_votes`/`summary_text`), and the loader only writes `_SOURCE_OWNED_FIELDS`. `prepare.py:47` does independently forbid outcome/editorial changes on the copy. So this is a strictness gap, not an active defect.
- Correction: mirror the non-registrar whitelist assertion for registrar rows (allow only source-owned + bookkeeping fields). Optional.

**F4 — 129 build-time `last_seen_at` fills create perpetual diff churn. [LOW, pre-existing, not this release]**
- Confirmed pre-existing in `models.py:119-120`. `verify.py:62-65` handles it correctly (DB value stays null; asserts it's a fill, not a fresh capture). Non-blocking; do not fix in this release. Worth a hygiene ticket because it noises every future artifact diff.

**F5 — Crosswalk aliases were reviewed only against SB but are applied globally. [INFO]**
- `local_measure_context.py:20` "Reviewed 2026-08-27 against San Bernardino CEDA history." The dict is global; `generator.py:COMPACT_LOCAL_MEASURE_TYPES` likewise. Because the historical aggregate is always county-scoped and (per `verification.json`) only SB contexts changed here (`local_context 27→28`), the blast radius is SB-only today. Re-review per county before expansion (e.g., a county using "Municipal Bonds" for a non-GO instrument would misclassify).

---

## 1. Release-priority answer

**Publishing this bounded improvement now is the right next step, and the refresh/publication handoff should follow it — not precede it.** Reasoning tied to the objective (two useful counties by Oct 5, ~10 Igor-hrs/wk):

- It delivers real voter value ~4 weeks before ballots: 49 measures gain grouped official-document links, 15 SB rows get corrected descriptions/jurisdiction/full-text, and the 29 SMC measures (already local, never pushed) reach the public. The documents are current as of the Sept 7 captures.
- No true prerequisite blocks it. Election-status rendering is not needed now: every Nov-2026 measure *is* genuinely pending (no results exist), so the current "pending" treatment is correct until Nov 3. The results contract is correctly deferred.
- The handoff is not a safety gate for a one-time publish; it's what converts this from "useful once" to "reliable updates." Holding the improvement hostage to the handoff wastes the runway.

**But be honest about what this release is not:** it is a single snapshot publication. The "reliable updates" half of the accepted objective is **not** delivered here — scheduled CI still neither parses nor publishes (forward_plan §"Why this ordering"). So publishing now buys a static, correct-as-of-Sept-7 view. **One concrete condition on the priority call:** because the SB/SMC pages are still actively filling (arguments/rebuttals were arriving biweekly), commit to at least one manual refresh (retrieve→parse→load→build→publish) before ballots drop, and treat the handoff as the genuine next work item, not a nice-to-have. Do not let "reliable updates" be checked off by this release.

## 2. Evidence matrix

| Area | Inspected evidence | Supported conclusion | Remaining gap |
|---|---|---|---|
| Identity / DB integrity | `loader.py` (re-plan under `BEGIN IMMEDIATE`, canonical-ID digest audit, exact-fingerprint + same-id + cross-source guards, `_plan_documents` batch-match raise); `load-verification.json` (15 upd/5 skip SB, 29 skip SMC, 0 ins/deact, integrity ok, 0 FK); `prepare.py` (RO source, hash-unchanged pre/post) | Loads are atomic, backed up, idempotent on replay, and touch only source fields + bookkeeping; production untouched | Did not run SQL on the binary DBs; relied on JSON reports + code |
| Document mapping | `measure_documents.documents_for_website` ((url,sha256) grouping, active/non-dup filter, re-validate); `verify.py:28-45` per-role reconciliation JSONL→DB→export; `test_registrar_loader.py`/`test_website_documents.py` | 272 roles → 239 grouped links → 49 measures reconcile exactly; snapshot_id/filename excluded from public JSON; distinct bytes at shared URL not collapsed; shared packets appear per measure | Reconciliation iterates JSONL side; extra orphan DB rows would be caught only by the 272 total match (which holds) |
| Context / type labels | `local_measure_context.py`, `generator.get_local_measure_type`; `verification.json` (27→28, only Measure I new); `initial-artifact-diff.json` (the rejected 13-panel-loss build) | Renames preserve existing panels via reviewed aliases; only Measure I newly gains context | Cohort threshold composition unverified → F1 severity uncertain |
| Enrichment independence | `build.py` (real `generate_site.py`, `HF_HUB_OFFLINE=1`, returncode 0, only title-provider warning, enrichment hashes unchanged); `verify.py:78-81` payload equality vs local root **and** remote | Real offline CLI build; finance/insights/recs/topics byte-identical; embeddings path executed (5 semantic contexts preserved) | Did not run the build; `full_production_cli_build=True` is a literal in the report, but backed by `build.py` assertions |
| UI / security | `generator.py` `renderOfficialDocuments`, guard; `browser.py` + `browser-verification.json` (5 cases × 2 viewports, external requests blocked); `test_website_documents.py` (XSS-in-labels, `javascript:` URL, keyboard, dedup) | Sanitized href, `_blank`+`noopener`, textContent (no injection), "Last captured … not its filing date", stale panel cleared on finance measure, panel fits, keyboard Tab order, no `REG_` in title | Did not run Chromium; read report + script |
| Publication scope | `verify.py:17-22,89-98`; `git-state.txt`; `source-hashes.json` | Candidate id-set == local root (12,361); +29 SMC vs remote (12,332), all SMC; every remote row preserved | Remote main ≠ proof of Pages deploy; hashes/timestamps won't reproduce (C1) |

## 3. The two new fixes and the prior seven dispositions

**Chino Hills J (fix A):** Justified. The parser genuinely rejected the letter-only rename (`retrieval.json` + regression test both show the `LineageConflictError`), the 4 byte-identical hashes are corroborated in the actual data, and the canonical ID is preserved (derived from the July-27 origin, so `REG_SB_…0FCA137…` is stable; `load-verification.json:400-431` shows only description/title/pdf_url/bookkeeping changed). Continuity through Sept 7 is re-established by unique-URL matching, not the override. Sound; my only reservation is durability (F2).

**Type-label crosswalk (fix B):** Justified for continuity. School/Municipal/District Bonds → GO Bond and Transactions and Use Tax → Sales Tax are defensible taxonomically, and byte-identical full text confirms the 14 measures are the same measures. The one place where byte-continuity does **not** carry the classification is Measure I's sales-tax context (F1).

**Prior seven dispositions:** I independently agree with all seven and confirmed each is implemented, not hand-waved:
1. content-vs-provenance split — `_DocumentChange` + `documents_provenance_refreshed`, tested. ✓
2. "Last captured" relabel + "not its filing date" note — in JS + browser-asserted. ✓
3. fail-loud id guard, partial-failure aware, subset-safe — `generator.py:144-153` + 3 targeted tests. ✓
4. real CLI `main()` verification — `build.py` + `test_actual_cli_field_filter…`. ✓
5. canonical-identity pairing, reorder-safe — `test_reordered_measure_actions_do_not_swap_document_ownership`. ✓
6. sanitized href — `link.href = sanitizeUrl(...)` + `/^https?/` filter. ✓
7. snapshot_id/filename out of public JSON — `PUBLIC_FIELDS` + `verify.py:45` assertion. ✓

## 4. Must-pass release checklist (proportionate)

1. Immediately before load, re-hash live production (`ballot_measures.db`, root `index.html`, `measures-data.json`) and confirm they still equal `source-hashes.json`; re-observe `git ls-remote origin main`. If any drifted, re-rehearse.
2. Commit the F1 code + task docs (name files explicitly; **not** `git add .`, **not** databases/backups/`registrar_recon/`/mirror).
3. Run `load_jsonl` **dry-run** on production for `sb.jsonl` then `smc.jsonl`; confirm 15 upd / 5 skip / 0 ins / 0 deact (SB) and 29 skip (SMC), 105 + 167 doc inserts, zero conflicts — matching `load-verification.json`.
4. Load with `--commit` (backup created per county); confirm `PRAGMA integrity_check = ok`, 0 FK violations, and that a same-snapshot replay writes nothing.
5. Regenerate with the real offline CLI (default dual output). Confirm build returncode 0 with **only** the AI-title-provider warning; confirm root and `scraper/` mirror are byte-identical.
6. Re-run `verify.py` and require these **exact** invariants (accept timestamp/hash divergence): id-set == local root and == remote+29 SMC (all `SMC_County_Registrar`); no field removed; non-registrar rows differ only in `last_seen_at`; financeData(181)/insightsData(24)/recommendations(10942)/topics(20) byte-identical to local root and remote; all 27 pre-existing `local_historical_context` preserved + Measure I; 5 semantic contexts preserved; full 272→239→49 role reconciliation; snapshot_id/filename absent from public JSON.
7. (Recommended, addresses F1) Decide the Measure I context: display its threshold, suppress, or record as a known limitation.
8. Stage **only** the root pair + committed code/docs; push within Igor's explicit approval; do **not** use `--deploy`.
9. Post-deploy: fetch the live `calballot.com` `measures-data.json`, confirm 12,361 measures, spot-check SB Measure J (7 links) / I (5 links) and SMC Measure R (6 links) modals in a browser.

## 5. Strongest argument against my verdict — and what would change it

**The strongest case for NOT READY:** Publishing a static snapshot whose whole selling point is "reliable, current official documents" *without* the refresh handoff risks the opposite outcome — the site will confidently show "Last captured 2026-09-07" links that silently rot as the county files arguments/rebuttals and renames URLs over the next four weeks (exactly the drift cadence the project has measured biweekly). A voter in late October could open a measure and get a stale or 404-ing county link with a reassuring capture date, which is arguably worse than no link. Under that framing, the handoff *is* the safety-relevant prerequisite, and shipping F1 first inverts the risk.

**What would change my verdict to NOT READY:**
- Evidence that the current SB/SMC live pages have already drifted materially since Sept 7 (new roles, changed URLs) with no committed plan/owner for a pre-ballot manual refresh — turning "useful once" into "misleading soon."
- A query of the SB "Sales Tax" cohort showing it is dominated by 50%-threshold general taxes (making Measure I's 55% panel a genuine 2/3-vs-majority miscomparison) **and** a decision to ship the panel unqualified — I'd then escalate F1 to a blocker.
- Any independent confirmation that a real production load diverges structurally from the rehearsal (e.g., production drifted from hash `f2867d0…`), which would invalidate the load-verification.

**Precise further check worth running (does not block, sharpens F1):** query the 31 SB CEDA "Sales Tax" rows behind Measure I's context (`vote_threshold`, `percent_yes`, `passed`, `year`). If most are majority-threshold general taxes, honor checklist item 7 before publishing; if the cohort is threshold-mixed roughly evenly, the panel is defensible as-is. This requires SQL on the binary DB, which I could not run.