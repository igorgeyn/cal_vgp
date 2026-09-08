# Independent disposition of Claude's release review

> Follow-up: the corrective pass below is now implemented and rehearsed. See
> [the updated release handoff](f1_post_review_release_20260908.md). This document
> preserves the reasoning at the time of review; production remains unpublished.

Claude completed the requested comprehensive review using the installed Claude
Code client and its configured model (`claude-opus-4-8`). The run had only
Read/Glob/Grep tools, no shell or mutation tools, and no permission denials.
It inspected source and textual evidence; it did not independently execute
tests, SQL, or browser checks. The full, unedited response is in
[the Claude review](f1_claude_release_review_20260908.md); the prompt is in
[the review brief](../codex/f1_release_comprehensive_review.md).

Claude's verdict is **READY WITH CONDITIONS**, with no identified identity,
document-mapping, or security blocker. It supports publishing the document
improvement before finishing refresh automation. I agree with that sequencing
and the core implementation assessment. I would make a small corrective pass
before signing off on the candidate, for the reasons below.

## One additional defect established by a separate SQL check

The local-context aggregation counts every historical row in its denominator,
but only `passed == 1` in its numerator. A null normalized outcome therefore
contributes exactly like a failure. This is pre-existing; preserving the old
payloads also preserved the error. Claude did not identify it.

Read-only queries of production found **nine null normalized outcomes across
five displayed county/category groups**:

| County/category | Rows included now | Null normalized outcomes | Confirmed passes |
|---|---:|---:|---:|
| SB GO Bond | 90 | 3 | 60 |
| SB Ordinance | 71 | 1 | 40 |
| SB Property Tax | 16 | 1 | 3 |
| SB Sales Tax | 31 | 1 | 17 |
| SMC GO Bond | 105 | 3 | 89 |

Other displayed groups checked have no null outcomes. These are missing
normalized outcome flags, not necessarily unknowable election results: raw
`pass_fail` strings remain on the nine rows. Notably, SB sales-tax row 10020
has `passed = NULL` and `pass_fail = 'PassT'`; the present aggregation counts
it in the denominator but not as a pass. Do not repair those source flags by
guessing from a percentage or by silently interpreting an unreviewed code.

**Required before my sign-off:** compute rates and minimum-sample eligibility
from recorded normalized outcomes only; make that sample definition clear.
Test unknown outcomes, an all-unknown cohort, and a cohort falling below the
minimum after exclusions. Rebuild and independently reconcile the corrected
rates. Previously preserved context values will legitimately change; document
the exact changes instead of retaining the old equality assertions.

Raw query results are saved in the ignored evidence directory at
`scraper/data/registrar_recon/f1_release_20260907/claude-review/independent-context-audit.json`.
My interim progress update incorrectly said six groups; the query establishes
five, as listed above.

## Disposition of Claude's findings

- **Measure I comparison group:** accept the need to explain the comparison's
  limits. Its actual two-thirds threshold already appears on the local card,
  so adding the threshold again would not fix the missing cohort qualification.
  All 31 historical SB sales-tax rows have null `vote_threshold` in production.
  We cannot establish Claude's proposed majority-versus-two-thirds composition
  from that column. Do not claim the mix was verified or infer that an even mix
  would establish comparability. A broad county/type historical statistic can
  be useful if explicitly described as not matched by voting rules or purpose;
  it is not an estimate of this measure's chances. Qualify that comparison in
  the corrective pass, without inventing historical thresholds.
- **Chino Hills override:** keep the exact immutable-snapshot correction. The
  reviewed continuity evidence is sufficient for this release. A future
  assertion/fixture policy for overrides is useful durability work, not an
  immediate reason to redesign lineage resolution.
- **Registrar delta verification:** accept the additional whitelist guard as
  inexpensive release hardening. The existing actual diffs contain no unexpected
  outcomes/editorial changes; a stricter guard should make that fail automatically.
- **129 `last_seen_at` fills:** retain the disclosed exception for the existing
  build-time behavior. It is not source freshness and should be a follow-up.
- **Global crosswalk aliases:** require per-county taxonomy review before
  expansion. No additional county is being enabled here.

## Correct Claude's publication instructions before use

Claude's instruction to simply re-run `E/verify.py` after the production load
and regeneration is wrong. That script reads the rehearsal database and site,
uses root artifacts as its pre-release comparison, and asserts that production
and root hashes still match the pre-load baseline. After a real load/build it
would either inspect the wrong objects or fail its unchanged-source gates.

The production check must instead receive an immutable pre-release baseline,
the actual post-load production database, and the actual newly generated root
pair. Compare stable identities, expected per-row changes, all document roles,
outcomes/editorial fields, unrelated enrichments, and paired outputs. Normalize
only the specifically justified load/build timestamps; do not accept arbitrary
timestamp divergence. Record hashes of the resulting production artifacts for
deployment verification. Rehearsal hashes identify the reviewed candidate;
they are not expected hashes of a later fresh build.

Explicit staging, both output pairs, avoiding `--deploy`, checking source/remote
drift before loading, backups, and post-deploy verification remain sound.
No production or publishing action was taken during this review.

## Next bounded pass

Correct the context calculation and explain its comparison limits; strengthen
the registrar delta gate and prepare a production-specific verifier. Rehearse
those changes on a fresh copy, review the deliberately changed context values,
then present the updated candidate for sign-off. Keep refresh handoff next and
reserve county expansion for the accepted gate.

The reviewed candidate, production inputs, and source code retain their
recorded hashes. This document assesses the September 7 candidate; it does not
claim the corrective pass above has already been implemented or tested.
