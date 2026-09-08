# F1 review response — September 7, 2026

The review found a real operator-reporting weakness and useful missing guards.
No demonstrated data-corruption or exploitable security defect was found. All
seven items were assessed independently; their proposed fixes and severities
were not accepted wholesale. Changes remain local, with no production load,
live scraping, root artifact regeneration, commit or publication.

## Disposition

1. **Accept the reporting defect; narrow the severity and backup claim.** A
   fresh snapshot is a real new observation, but should not make every document
   look substantively changed. Reports now distinguish content/link/type changes
   from `documents_provenance_refreshed`. Internal snapshot filenames also belong
   to provenance, not document content. Persistence upserts changed rows and
   deletes only removed roles, rather than deleting/reinserting every association.
   Weekly backups still occur: the pre-existing scope watermark must advance
   and that requires a backed-up write even without F1. No automated document
   load currently exists in the weekly capture workflow, so a Monday automated
   load is not an established deadline.

2. **Reject the dishonesty claim; clarify the label.** `captured_at` has always
   meant when this snapshot retrieved the document. Repeated captures correctly
   advance it. Keeping an old date beside a new snapshot ID would mix different
   observations; claiming first-observed would require separate historical
   semantics. The UI now says **Last captured** and explicitly distinguishes that
   from filing date. The database retains coherent latest-observation metadata.

3. **Accept the missing boundary guard, with a stronger fix.** Production's
   whitelist currently includes `id`; the review reproduced malformed prepared
   input, not a current production omission. Nevertheless, fail loudly before
   output if even one document-bearing record lacks or mismatches its integer
   database ID/canonical measure ID. A zero-matches-only check misses partial
   failures and wrongly rejects legitimate subsets without document records.
   Tests cover missing, mistyped, wrong, and partially missing IDs and subsets.

4. **Accept the verification scope gap.** The existing copy preview was a useful
   check that attaching documents preserves prepared fields, not proof of the
   entire production generator. The verifier now also calls the actual CLI
   `main()` with `--db` and `--output` directed at a copy/scratch directory. Those
   existing flags make this possible without writing deployed artifacts. The
   real active-view query, whitelist, model construction and export execute.
   Controlled finance/insights/recommendation inputs and absent embedding inputs
   are disclosed. Report names distinguish prepared-input preservation from
   CLI ID/document coverage and same-snapshot replay. Full production rebuilding,
   including E5 enrichment failures, remains explicitly unverified.

5. **Accept as preventive hardening, not a reproduced bug.** Pairing now uses
   canonical identities recorded during resolution. Directly joining proposed
   parser IDs to action IDs would break legitimate alias cases; the review's
   suggested simplification overlooked that distinction. Reordering actions is
   tested, as is the existing canonical-ID preservation scenario. Multiple input
   records resolving to one canonical identity are rejected.

6. **Accept consistency cleanup, not a security finding.** Assign the sanitized
   URL to `href`. The review found no bypass of the existing HTTP(S) and metadata
   checks; this is not described as fixing an exploit.

7. **Trim the public contract; reject a sensitive-disclosure characterization.**
   Snapshot IDs and storage filenames are not secrets, but need not be in public
   JSON. They remain in SQLite. Public JSON retains URL, captured checksum,
   source listing, size/type, last capture time, roles and labels. The checksum
   describes captured bytes, not a guarantee about the live URL's current bytes.

## Evidence

- **261 registrar/site tests passed**, including Chromium and a test calling
  the actual CLI field-filtering path. The known legacy suite failures remain
  outside this test selection.
- Updated evidence directory:
  `scraper/data/registrar_recon/documents_review_response_20260907_final/`.
- `verification.json`: all 12,361 database measure rows unchanged; all prepared
  input fields preserved; all active database IDs and official documents reach
  the CLI export; source database/root artifact/input hashes unchanged.
- `site/` is the prepared-input preview; `cli-site/` comes through the real CLI
  with controlled enrichment inputs. Neither is a production publication.
- `synthetic-weekly-replay/verification.json`: actual local SB/SMC record sets
  with synthetic later capture metadata, not a newly fetched production snapshot.
  Zero material document changes, 88 SB + 167 SMC provenance refreshes, unchanged
  measure rows, and no writes on identical-snapshot replay. Scope advances and
  backups remain intentional.

The accepted order still holds: finish reliable refresh/publication handoff and
election-status correction before Alameda. No further Igor decision is needed
for the fixes above. F1 remains subject to selecting the intended production
snapshots and the ordinary reviewed release checks; this review response does
not authorize or perform publication.
