# Official documents: production release review, September 7, 2026

> Superseded candidate: [September 8 review corrections and release handoff](f1_post_review_release_20260908.md)
> replace this document's context values and post-load verification procedure.

**Prepared, not published.** Production SQLite, root HTML/JSON, and finance and
enrichment inputs remain unchanged by SHA-256. No county scraping, production
load, commit, or push was performed. Existing production R2 objects were read
into an isolated review directory.

## Proposed release

Use the exact September 7 production captures:

| County | Snapshot | Measures | Document roles | Displayed links |
|---|---|---:|---:|---:|
| San Bernardino | `20260907T172437Z` | 20 | 105 | 104 |
| San Mateo | `20260907T172914Z` | 29 | 167 | 135 |

The difference between roles and links is intentional: one county PDF can
serve several roles. Links shared between different measures remain on each
measure. All 272 role associations reconcile from normalized input through
SQLite into 239 public links on 49 measures.

Production load, rehearsed on a SQLite backup:

- **SB:** 15 existing measure updates, 5 unchanged; 105 document-role inserts.
- **SMC:** 29 unchanged measures; 167 document-role inserts.
- **Both:** zero inserted/deactivated measures, zero conflicts. Scope watermarks
  advance. Every integer ID and canonical identity is preserved.
- Both loads create backups on the copy; identical-snapshot replay writes
  nothing. SQLite integrity and foreign-key checks pass.
- All 12,414 underlying measure rows retain their identities; 12,361 are active.
  Every non-registrar row and every SMC measure row is unchanged. SB changes
  are source fields and ordinary loader bookkeeping, not outcomes or research.

The SB updates reflect 14 changed county descriptions (and derived titles),
three full-text URL changes, and Measure I's more precise jurisdiction,
San Bernardino County Transportation Authority. Measure I gains a full-text
link; J and R use renamed URLs. These are actual differences from the earlier
local snapshot, so the old document-only migration expectation does not apply.

## Two issues found and resolved during release preparation

**Chino Hills J identity continuity.** Replay initially stopped at August 31:
the county removed “Measure” from the description and renamed all document
URLs. The safe ambiguity guard correctly rejected a letter-only match.
Comparison of verified archived bytes established continuity:

| Document | Identical SHA-256 in Aug 28 and Aug 31 captures |
|---|---|
| Resolution | `4b15853f6c2e195e46333a9faa452817f13ed2496e67a8a21e92ab4b785f7877` |
| Full text | `3a5207dfd6e03d080423de2c8ae7d14aaaaae07bed44ee5b699bbd7c4f25a7ef` |
| Impartial analysis | `d9a86dae6448d33af9611b354224a5acab300e939c0eed861cb1c527e25a0a92` |
| Argument against | `bcd9636872696c6599d52cfb45f48cbe33e022e8eb0aa09b190eb930156a90c5` |

The argument for changed bytes and is treated as the new captured version.
A county-config override connects August 31 row 12 to July 27 row 4. The
general identity rule remains strict. A regression test verifies rejection
without the override and continuity through September 7 with it. All seven
complete SB snapshots and both SMC snapshots replay successfully.

**County vocabulary broke context matching.** The first full build dropped
13 local context panels because “Bond Measure” became “School Bonds,”
“Municipal Bonds,” or “District Bonds,” and “Transactions and Use Tax Measure”
became “Transactions and Use Tax.” The affected measures retain byte-identical
full-text documents. Reviewed crosswalk aliases and compact card labels now
preserve their existing context and short labels.

Measure I's newly available full text explicitly describes a transactions and
use tax (sales tax). Its new source description now supports the sales-tax
cohort; this adds one context panel and changes its short label from
“Transportation” to “Sales tax.” The old ambiguous description remains
explicitly unmapped. No broader fuzzy classification was introduced.

## Full build and artifact review

The actual `generate_site.py` CLI ran against the loaded copy with explicit
scratch output and real finance, Insights, recommendations, and embedding
inputs. The sentence-transformers model loaded from the local cache with
`HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. No enrichment providers were
mocked and no previous prepared measure payload was reused.

- Zero measures or fields removed relative to the root pair.
- Five semantic-context payloads preserved exactly; 27 existing local-context
  payloads preserved exactly, plus Measure I for a total of 28.
- Finance for 181 measures, 24-key Insights payload, recommendations for 10,942
  measures, and 20 topic entries match both local root and remote main exactly.
- Existing generated titles and summaries are unchanged.
- One expected warning: no optional AI title providers are configured. This
  path uses existing titles; artifact comparison verifies they were preserved.
  No semantic-context or finance degradation warning occurred.
- Known pre-existing artifact churn: `BallotMeasure.__post_init__` fills null
  `last_seen_at` values at build time for 129 historical rows. Their database
  values remain null and all their other exported fields are unchanged. Those
  timestamps are not evidence of a fresh source capture. This release does not
  fix that separate model behavior.
- HTML diff contains the document panel, its scoped styles/rendering, duplicate
  full-text-link suppression, and the build date. Large enrichment payloads
  were compared structurally before being collapsed in the review diff.

**268 registrar/site/context tests pass**, including the new lineage and
vocabulary regressions. The actual candidate is additionally checked in
Chromium at desktop and mobile widths; see the browser report below.

## Publication scope and next action

Read-only `git ls-remote` observed remote main at
`04db0dc1ed6298d7e784e191fb9eb9f904098ac1`; local HEAD is `481d364`, five commits
ahead. The remote pair has 12,332 measures. Publishing this branch would also
deliver the already-local San Mateo publication: **29 SMC measures added, none
removed**, plus the current 49-measure official-document feature and SB refresh.
Remote branch contents were checked; a new Pages deployment was not requested.

After Igor approves production loading and publication: recheck the reviewed
source hashes and remote revision, run backed-up production loads from the
pinned JSONLs, regenerate both normal output pairs with the verified offline
model configuration, and repeat the artifact gates before explicitly staging
the task files and root pair. Do not stage scratch evidence, databases,
backups, ignored mirrors, or unrelated untracked work. Push only within that
approval, then verify deployment. The existing `--deploy` helper is unsuitable
because it attempts to stage the ignored mirror.

F1 is not complete until that release succeeds. Reliable refresh handoff and
election-status rendering remain the next work, ahead of county expansion.

## Evidence

All paths below are relative to
`scraper/data/registrar_recon/f1_release_20260907/` (ignored, local evidence):

- `raw/prod/`: all nine archived snapshots, artifacts hash-verified on retrieval
  and parser replay; `retrieval.json` retains the initial SB conflict finding.
- `sb.jsonl`, `smc.jsonl`: successful final normalized release inputs.
- `measures.db`, `load-verification.json`: rehearsed load and exact field changes.
- `site/index.html`, `site/measures-data.json`: actual candidate release pair.
- `build.log`, `verification.json`, `artifact-diff.json`, `html-diff.txt`:
  full build, enrichment preservation, source hashes, and release artifact hashes.
- `browser-verification.json`, `desktop-documents.png`, `mobile-documents.png`:
  actual candidate modal checks with external requests blocked.
- `source-hashes.json`, `enrichment-source-hashes.json`: unchanged production
  and enrichment inputs. The earlier controlled preview is not release proof.
