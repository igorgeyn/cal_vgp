# County content release — October 8, 2026

The candidate completes source-backed reader content for the existing **20 San
Bernardino and 29 San Mateo measures**. All 49 have a full official question,
a separate CalBallot explanation, approval requirement, source/page citations
and review date. Forty have links to real historical records underlying their
same-county/broad-type comparisons. All 239 official-document groups remain.

**Published and served verified:** release `61309719` via [PR #7](https://github.com/igorgeyn/cal_vgp/pull/7). [Pages deployment](https://github.com/igorgeyn/cal_vgp/actions/runs/37860249030) succeeded; all 56 sampled served artifacts match the tested bytes, including every changed county page. All 49 county modals passed live at 1440/390px, including finance fallback, page-to-explorer return, preserved statewide/historical Finance and the Measure Z correction. Private R2 recovery read-back passed.

The tested candidate is private scratch
`scraper/data/county_content/20261008/candidate-02/site/`. Publication and served
verification have passed; the final PR receipt and evidence JSON record them.
Baseline: `7a4bccb9`. Branch: `county-content-r1`.

## Reader examples

Review [Burlingame R](https://cal-vgp.igorgeyn.com/measures/12443.html)
for bond principal versus repayment; [regional transit](https://cal-vgp.igorgeyn.com/measures/12442.html)
for five-county scope; [Belmont Y](https://cal-vgp.igorgeyn.com/measures/12450.html)
for the square-foot tax base; and [Redwood City E](https://cal-vgp.igorgeyn.com/measures/12460.html)
for the rent-regulation explanation and qualifications. These links show the verified production update.

The same explanations appear in the local carousel, searchable catalog previews,
modal and individual pages. Modal explanations display in full. Official
questions retain their source wording, with layout/spacing normalized and
ballot-box labels or adjacent signatures omitted. Source pages remain one click
away. The county modal uses a county-attributed listing statement instead of the
inapplicable statewide “Filed” progression.

Local campaign-finance filings are **not imported or linked to individual
committees** in this batch. The Finance tab and individual page explain that
absence, show no invented zero totals, and link to official county lookup
resources with a city/regional filing caveat. Nine records have no eligible
historical comparison; there is no fabricated substitute. Coverage is county
scoped, not an address-specific ballot.

## Evidence and content ownership

- [49-record source ledger](county_content_ledger_20261008.md) and versioned
  `scraper/src/website/data/county_2026.json` bind identity, election, threshold,
  question, explanation, source URL/SHA-256, PDF pages and review dates.
- Fresh [registrar run 37856278296](https://github.com/igorgeyn/cal_vgp/actions/runs/37856278296)
  succeeded. Captures: SB `20261008T225445Z`, SMC `20261008T225908Z`. Replayed
  lineage preserves all 49 IDs. Comparison against September 28 found no added,
  removed or substantively changed measures and no changed document URL/role/hash
  sets. Every downloaded archive file was hashed before use.
- Production databases remain unchanged. Public document rows retain their
  earlier capture provenance; a separate October 8 source-check date records the
  fresh verification. Capture, content review and publication are distinct events.
- The projection owns new display fields, preserving database `ballot_question`,
  `summary_text`, all other imported/editorial fields and document evidence.
  Changed identity, threshold, source URL/role or dependent PDF bytes stop the
  build for re-review. Identical bytes in a later capture preserve accepted text.
- An actual isolated ordinary loader rehearsal advanced both fresh snapshots
  without changing any measure row, retained all 49 reviews, and made no writes
  on repeated input. Production DB SHA-256 stayed unchanged.

All 49 source questions and explanations were checked against rendered pages by
Codex and then independently by Claude. The review ledger distinguishes pages
actually used for explanations from other linked county documents. In
particular, extraction-readable county-labelled “analysis” does not certify
impartiality. Measure Z's known advocacy PDF remains visibly relabelled, excluded
from the explanation, and preserved as original evidence.

## Reviews and disposition

Read-only Claude CLI reviews used Read/Grep/Glob, with no shell, network access,
edits or credential access. The recorded review model was `claude-opus-4-8`.
Original JSON outputs are retained in the private recovery evidence, including
permission-denial and tool-scope records. API credentials were removed from the
subprocess environment; the reviews used the existing Claude CLI account.

| Review | Scope | Verdict | Codex disposition |
|---|---|---|---|
| Pilot | SB Y/Z/A; regional transit; scanned Burlingame bond packet | READY WITH CONDITIONS | Source accuracy accepted; all cited pages also checked by Codex. Conditions resolved below. |
| SB wave | Remaining 17 records / 18 cited images | READY | Accepted against source evidence, including Chino's disclosed $75,000 wording conflict and hospital refinancing. |
| SMC wave | Remaining 27 records / 33 cited images | READY | Accepted against source evidence, including shared charter packet ownership, square-foot tax, tax renewals, regional scope and rent rules. |
| Extra Claude integration pass | Began reading final code/evidence | Incomplete: account session limit (429), reset reported 18:30 Pacific | No independent integration verdict exists. Do not describe this attempt as a completed review. |
| Codex integration assessment | Final diff, all executed tests, full preservation gate, desktop/mobile checks and representative rendered pages | READY | No observed integration blocker. The three completed independent content reviews plus executed integration evidence support the release; the extra Claude pass remains an explicitly recorded limitation. |

Pilot changes: replace numeric CEDA jurisdiction codes in historical link labels
with a county fallback and a useful title preview; surface approval requirements;
distinguish source check from capture dates; replace the county's fabricated Filed
rail. The content was not rewritten merely because Claude reviewed it. Belmont's
unpunctuated question header is flattened without adding punctuation; both
reviews found that faithful to the source. No question/explanation remains an
unresolved fallback. Igor's personal reading of the examples remains available
as product feedback; no unasked policy or legal tradeoff was inferred.

## Validation

- **141 focused tests pass** across content, source/identity failures, historical
  cohorts, statewide preservation, documents, output contracts, pages and loader.
  An initial invocation hit Windows temp-directory access errors; rerunning in
  a fresh workspace-local temp directory passed. No application failure was hidden.
- Every county modal and individual page passed at **1440, 390 and 320px**:
  full explanation/question, correct page citations, finance fallback, valid
  historical IDs, no horizontal overflow and no JavaScript errors. Keyboard
  activation and clearing county content when another record opens were checked.
- Grid/List navigation passes at **1440, 768, 640, 390 and 320px**, including
  focus, sticky-header offsets, filters, county selection, pagination, history
  and reload. All 14 statewide guides and their finance/research panels also pass
  at desktop and mobile sizes.
- Strict real generation produced **12,372 pages / 12,374 sitemap URLs**.
  Exactly 49 measure pages change; **12,323 other pages are byte-identical**.
  Finance, Insights, recommendations, topic and quiz payloads are unchanged.
  The existing 129 legacy null `last_seen_at` values regenerate display timestamps;
  no database row changes. No unrelated record content changes.
- Recovery uses a fresh frozen workspace and the real archived model/data. The
  existing recovery base and prior updates remain immutable; this release adds
  county content, code, source-page evidence, review records and exact public
  artifacts. Restore/rebuild and R2 read-back receipts are release prerequisites.

Private evidence root: `scraper/data/county_content/20261008/`. Durable evidence
summary: [county_content_evidence_20261008.json](county_content_evidence_20261008.json).

## Remaining work

This completes the county content implementation, not the entire election-readiness
plan. Next: R2 routine refresh/diffs and accepted-publication manifest, R3 calendar
status consistency, R4 honest results fallback and R5 operating rehearsal. Alameda
follows those essential gates; San Francisco and Contra Costa require fresh source
assessment. Statewide card aesthetics remain deferred as Igor requested.

Recovery update SHA-256: `838170fde15a9379fa6eabd451cf447d5af4ed423dc3361bd8e6a5286ffe7ade`. The private restore checked 277 workspace inputs and all 12,382 public files. The tested build and live response hashes are in the evidence JSON.
