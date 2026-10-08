# Independent Claude release review ? October 8, 2026

Read-only CLI review requested by Igor. Code inspection and recorded-evidence review; Claude did not run the tests or perform network checks.

## Independent review: CalBallot statewide Part 1/Part 2 release + Oct 8 cutover addendum

I read the five starting documents, the Part 1/Part 2 evidence JSON, the pinned approval crosswalk, the prior Part 1 Claude review (F1–F10) and its corrections evidence, then traced the implementation: `statewide_ballot.py`, `generator.py` (search/modal/withdrawal logic), `build_measure_pages.py`, `generate_site.py` (strict-mode guards), `measure_documents.py`, `verify_statewide_candidate.py`, `check_statewide_browser.py`, `recovery_bundle.py`, `build_release_bundle.py`, `verify_release_bundle.py`, `materialize_recovery_sources.py`, and the Oct 8 addendum's `promote_statewide_release.py` + `test_statewide_promotion.py`, cross-checked against `rehearsal-promotion.json`/`rehearsal-preservation.json`.

### What I independently verified (not just trusted)

- **Local HEAD**: read `.git/HEAD` → `refs/heads/main` → `ec650a290992da7c7f903800419e59b523de8e9d`. Matches every claim. I have no network access, so I could **not** confirm GitHub's remote HEAD or the claimed Actions runner failure — that rests on the narrative alone.
- **F1 (legacy AI summary over official text)**: fixed. `generator.py:14792-14821` now prefers `status_reason`/`official_description` over `summary_text`, with a real attribution link and `Source captured …`. `build_measure_pages.py:225-236` does the same for static pages, and the search-text builder (`generator.py:10968-10969`) excludes `summary_text` when an official description/status_reason exists.
- **F2 (withdrawn record disappearing)**: fixed. ACA 13 stays `is_active`; `ballot_status='withdrawn'` is projected everywhere (badges, modal, list, filters, static page). `check_statewide_browser.py:118-142` asserts the search result, status filter, list view, and the stale `/measures/1.html` route redirecting correctly into `#m=1` with the withdrawal text — this is a real Playwright assertion, not a description of intended behavior.
- **F3 (substring search ranking bug)**: fixed. `parsePropositionQuery` (`generator.py:10852-10855`) is now a fully anchored `^...$` regex, and `check_statewide_browser.py:100-107` explicitly asserts "Prop 3" results exclude every other `by_number` id (i.e., 37/38/39 don't leak in) — this directly tests the exact failure mode the prior review reported.
- **Production cutover tool** (`promote_statewide_release.py`): traced the full control flow. Baseline/candidate hashes are pinned and checked read-only first; `BEGIN EXCLUSIVE` is acquired on the target, and *only after that* does it re-verify the target's hash and full `logical_state` against the pre-computed baseline — so there's no TOCTOU window between check and write. `timeout=0` means a concurrent writer causes an immediate `OperationalError` rather than a silent wait-then-clobber. The byte-for-byte backup is written and hashed before any mutation. The final `logical_state(dest) != expected` check (full schema + per-table row-multiset + `fts5vocab` token/doc/col/offset hash, deliberately excluding only the two layout-sensitive FTS shadow tables) runs before `commit()`, inside `finally: dest.rollback()`. This matches the Oct 8 addendum's description exactly.
- **8 promotion tests**: confirmed by reading `test_statewide_promotion.py` — 5 standalone tests + a 3-way parametrized sidecar test = 8. They genuinely exercise concurrency (`BEGIN` held open → `OperationalError('locked')`, no backup written), unrelated-production-edit rejection, a mutated-candidate rejection, mid-verification failure rollback (via `monkeypatch`), and WAL/SHM/journal refusal.
- **Rehearsal evidence**: `rehearsal-promotion.json`'s `baseline_sha256` (`7ff2ca55...`) matches the real `scraper/data/ballot_measures.db` hash recorded in both the Oct 3 and Oct 8 evidence files — i.e., the rehearsal ran against a real copy of the actual production file, not a synthetic fixture, and it reached `"logical_candidate_match": true`.
- **Apparent contradiction, resolved**: `rehearsal-preservation.json`'s `row_field_diff` (4 rows, only date/type/timestamp fields) looked inconsistent with `public_changed_fields` (14 fields including `official_title`, `source_url`, `ballot_status`, etc., across up to 4 records). I traced this through `statewide_ballot.py`'s `attach_statewide_ballot_fields` and confirmed those extra fields live in the new `statewide_ballot_entries` overlay table, not in `measures` — the two reports are describing different layers correctly, not disagreeing.
- **Document grouping/safety**: `measure_documents.py:documents_for_website` groups by `(source_url, sha256)` with multiple roles merged into one link (matches "composite packet" claim); `build_measure_pages.py:safe_http_url` and `validate_document` reject unsafe schemes/credentials in URLs; CSS confirms mobile wrap (`overflow-wrap: anywhere`) and visible keyboard focus (`:focus-visible { outline: 3px solid … }`), and `check_statewide_browser.py:165-169` has a real Playwright assertion for both (`scrollWidth <= innerWidth`, Tab-focus + `outlineStyle !== 'none'`).
- **Strict build**: `generate_site.py` and `generator.py` raise on missing/broken research, embeddings, recommendations, Insights, and finance only when the *source* is absent/broken (file missing, import error, exception) — never when a given measure simply has no finance/history, confirmed by reading every branch.
- **Recovery tooling**: `recovery_bundle.py` rejects symlinks, `.pem/.key/.pfx`, non-comment `.env` content, Windows trailing-dot/space path tricks, and case-colliding zip entries; `verify_release_bundle.py` independently re-derives the sitemap/page/document-link contract from the HTML itself (not from the generator's own report).

### Findings

**MEDIUM — the `measure_search` FTS5 sync mechanism is invisible in version control.**
`scraper/src/database/models.py:361` declares `measure_search` as an external-content FTS5 table, but there is no `CREATE TRIGGER` anywhere in `models.py`, `operations.py`, `statewide_ballot.py`, or any migration file, and no explicit `INSERT INTO measure_search` in `reconcile()`, `promote_statewide_release.py`, or even the ordinary `Database.insert_measure()` path used by every other loader. External-content FTS5 tables are not auto-synced by SQLite; something must explicitly feed the index. Concrete failure scenario: if the DB were ever rebuilt from scratch using only the versioned `SCHEMA` (e.g., a true disaster-recovery-from-zero instead of a binary copy), full-text search would silently stop returning new rows with no error. **Why this doesn't block this release:** the Oct 8 rehearsal ran `promote_statewide_release.py` against a real byte-copy of the actual production file, and its own `fts5vocab`-based comparison — which would catch exactly this failure — passed (`logical_candidate_match: true`). The recovery/restore path also only ever carries forward a full binary copy of the DB (never a from-scratch schema-only build), so whatever mechanism is baked into the physical file is preserved through this specific recovery. This is real, but it's an undocumented institutional-knowledge gap, not a live defect. **Remedy:** document the actual trigger/rebuild mechanism (likely already present in the live `.db` file outside version control) in `DATA_PIPELINE.md` or `models.py`, ~30 minutes.

**LOW — F9 (verifier shares code with the implementation it checks) is only partially addressed.**
`verify_statewide_candidate.py:18` still imports `read_review`, `digest`, `LEGISLATION_URLS` from the module under test. The prior review's specific sub-complaint ("new rows' links go unchecked") **is** now fixed — lines 148-154 explicitly check `Official Voter Guide`/`CA SOS Eligible Measures`/`CA Legislature (` links on new rows. The remaining shared-code concern was rated LOW by the prior review and I agree it doesn't block; it was explicitly deferred to Part 3+.

**LOW/informational — no recorded evidence file for the claimed Oct 5 GitHub Actions failure.**
I searched the repo for any stored workflow-run log and found none; the "runner not acquired" claim exists only in the plan text. R2 showing no new captures after Sept 28 is independently consistent with "no capture happened," which is the operationally relevant fact. I can't verify the specific GitHub error message myself (no network tool), so treat the *mechanism* of the Oct 5 miss as narrated, not evidenced, while the *consequence* (no new county data, no new statewide data) is independently corroborated.

**LOW/informational — the Oct 8 "prior model" self-review produced no output.**
`scraper/data/statewide_recon/20261008_release/run_claude_review.py` is a harness that shells out to `claude --print` with this exact prompt, but both `claude-result.json` and `claude-stderr.log` are empty (1 line / effectively blank). There is no actual recorded prior independent review of the Oct 8 addendum — my review is the first. Worth knowing so this isn't mistaken for a second opinion that already exists.

**Not a finding, but disagreement with a framing risk**: F6 (year-unscoped `measure_id` collisions across years) from the prior review is structurally avoided for *this* batch — the approval crosswalk assigns `PROP_<n>_2026` (year-suffixed) to all 11 new rows, distinct from bare historical keys like `PROP_1`/`PROP_2` used by the 2022/2024 sentinel rows I found in the test fixture. The pre-existing bare-key collision among older years is real but unrelated to this release and correctly out of scope.

### What remains untested by me / relies on recorded evidence only

- I cannot execute code, so all SHA-256 values (production inputs, candidate DB/HTML/JSON, archive) are **cross-checked for internal consistency across independently-dated files**, not recomputed by me.
- GitHub remote state, the live PDF link-health results, and the R2 upload/download receipt's "no ACL/public-access change" are accepted from recorded JSON, not independently reproduced (consistent with the task's constraint against touching the private bucket).
- Served-site behavior, the actual maintenance-window writer exclusion, and git staging have not happened yet — these are real remaining steps, not defects.

### Verdict: READY WITH CONDITIONS

The implementation is unusually rigorous — pinned hashes, read-before-write ordering, `BEGIN EXCLUSIVE` held across the entire baseline-verify-to-commit window, a real backup-before-mutate step, and a full-content (not just row-count) equivalence check before commit, all exercised by passing tests and a real rehearsal against the actual production file. I found no defect that should block proceeding with the cutover itself. Conditions, all small and execution-time rather than code fixes:

1. Immediately before running `promote_statewide_release.py --apply` for real, re-hash the live production inputs fresh (don't reuse the Oct 3/Oct 8 snapshot values) — the script already pins this, just confirm it's being invoked against current files, not stale paths.
2. Confirm GitHub `origin/main` actually matches local HEAD `ec650a2` before staging/pushing (a `git fetch` + compare; I couldn't do this without network access).
3. Document the `measure_search` FTS sync mechanism before treating binary-copy recovery as a permanent substitute for a documented schema.
4. Run the actual maintenance-window cutover (writer exclusion, `promote_statewide_release.py --apply`, scraper-mirror sync, Git staging of only the reviewed paths, one commit) and then the served-site checks from the Part 2 runbook (`#m=1`, a Prop detail page, a county document page, sitemap, Finance) — these are the real remaining gates, not yet exercised.
5. After publication, start Part 3's refresh/manifest work rather than new scope — county expansion and card redesign remain correctly deferred.

# Focused follow-up: Measure Z correction

No failures/errors found, and the suite confirms 97 tests including all four `test_document_role_review` cases, the escaping tests in `test_release_pages` and `test_website_documents`, and the Z-correction case.

Summary of what I inspected vs. trusted:

**Inspected directly:**
- `docs/plans/release_progress_20261008.md` — correction narrative, scope, and freshness claims
- `sb-z-evidence.json` and confirmed the archived PDF fixture exists alongside it
- `measure_documents.py`: `apply_document_role_review` is tightly bounded — it only fires for the exact pinned URL+SHA256, raises `ValueError` on any byte change, preserves raw `roles` into `source_roles`, and labels are recomputed from the corrected `roles` (not stale)
- `generator.py` modal JS: uses `textContent` for the note (XSS-safe by construction)
- `build_measure_pages.py` static render: uses `esc()` on the note
- `verify_statewide_candidate.py`: the preservation check allows exactly one document-group change, pins the exact pre-image (`roles == ['analysis','argument_for']`) and exact post-image (including `source_roles`, note, label), and requires all other document keys to be byte-identical
- `test_document_role_review.py`: all four cases (correction applied, reinspection-on-change guard, legitimate combined packet untouched, fixture PDF SHA matches pinned SHA)
- `test_release_pages.py` / `test_website_documents.py`: confirmed XSS-escaping tests exist for `role_review_note` in both static HTML and the Playwright-rendered JS modal
- `tests-final.xml`: confirms 97 tests, 0 failures/errors, and that all the above test modules/cases are present in that run

**Trusted, not independently re-verified:**
- `check_statewide_browser.py` added case (read only the grep hits around lines 176–194, not the full script) — sufficient to see it asserts the note text appears in both `.official-documents` and `#modalOfficialDocuments`, didn't re-run it
- `z-live-pdf-check.json`, `preservation-final.json`, `candidate-final/site` artifacts — not opened this pass; relying on prior review plus this code-level confirmation that the mechanism they'd validate is sound
- Did not re-fetch the live PDF or recompute hashes myself

No defect found in the bounded correction path itself: the URL/SHA pinning, raw-role preservation, label recomputation, dual-render escaping, and the preservation-checker's exact pre/post-image pinning are all consistent with the stated "argument_for + source_roles + note" correction, and the one-document-group delta is the only change the checker permits.

**READY** — the SB Measure Z correction is correctly and narrowly implemented; no blocker found in this review scope.