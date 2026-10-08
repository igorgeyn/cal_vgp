# Statewide reconciliation ledger — September 13, 2026

Official evidence is as captured September 13; insertion keys and public withdrawal behavior were revised October 3. The current candidate is isolated and unpublished.
The [review input](../../scraper/tests/fixtures/statewide/20260913/review-corrections.json) pins all source bytes and the full preimage hashes.
The [current correction handoff](statewide_corrections_20261003.md) explains the implementation and verification.

## Numbered November 3 slate

| Proposition | Official title | Integer ID / canonical ID | Action / identity basis |
|---|---|---|---|
| 1 | [Authorizes Bonds for Housing Affordability Programs. Legislative Statute.](https://voterguide.sos.ca.gov/propositions/1/index.htm) | 12467 / `PROP_1_2026` | Add record after inactive/duplicate audit. Official qualified-list link and proposition page agree on number, title and election. |
| 2 | [Increases State’s Rainy Day Fund. Legislative Constitutional Amendment.](https://voterguide.sos.ca.gov/propositions/2/index.htm) | 12468 / `PROP_2_2026` | Add record after inactive/duplicate audit. Official qualified-list link and proposition page agree on number, title and election. |
| 3 | [Provides Permanent Funding for Schools and Health Care by Extending Existing Tax on High Incomes. Initiative Constitutional Amendment.](https://voterguide.sos.ca.gov/propositions/3/index.htm) | 10960 / `INIT_1993` | Preserve existing record. SOS 1993 → AG 25-0016 → formal Act and Article XIII Section 36 in Proposition 3 law. |
| 4 | [Repeals Prohibition Against Public Funding of Election Campaigns. Legislative Statute.](https://voterguide.sos.ca.gov/propositions/4/index.htm) | 10956 / `SB_42` | Preserve existing record. Proposition 4 law names SB 42, Chapter 245 (2025). |
| 5 | [Changes Recall Election Process for Statewide Officers. Legislative Constitutional Amendment.](https://voterguide.sos.ca.gov/propositions/5/index.htm) | 2 / `SCA 1 (Newman) Elections: recall of state officers` | Preserve existing record. Proposition 5 law names SCA 1, Resolution Chapter 204 (2024). |
| 37 | [Creates Loan Program for Middle-Income Buyers of Qualified New Homes. Initiative Statute.](https://voterguide.sos.ca.gov/propositions/37/index.htm) | 12469 / `PROP_37_2026` | Add record after inactive/duplicate audit. Official qualified-list link and proposition page agree on number, title and election. |
| 38 | [Authorizes Bonds for Immunology Medical Research. Initiative Statute.](https://voterguide.sos.ca.gov/propositions/38/index.htm) | 12470 / `PROP_38_2026` | Add record after inactive/duplicate audit. Official qualified-list link and proposition page agree on number, title and election. |
| 39 | [Prohibits Citizens from Voting Unless They Present Government-Issued Identification. Initiative Constitutional Amendment.](https://voterguide.sos.ca.gov/propositions/39/index.htm) | 12471 / `PROP_39_2026` | Add record after inactive/duplicate audit. Official qualified-list link and proposition page agree on number, title and election. |
| 40 | [Imposes One-Time Tax on Certain Taxpayers. Initiative Constitutional Amendment and Statute.](https://voterguide.sos.ca.gov/propositions/40/index.htm) | 12472 / `PROP_40_2026` | Add record after inactive/duplicate audit. Official qualified-list link and proposition page agree on number, title and election. |
| 41 | [Prohibits New State Taxes That Exclude Revenues from State Spending Limit. Requires Audits for New State Special Taxes. Initiative Constitutional Amendment.](https://voterguide.sos.ca.gov/propositions/41/index.htm) | 12473 / `PROP_41_2026` | Add record after inactive/duplicate audit. Official qualified-list link and proposition page agree on number, title and election. |
| 42 | [Prohibits New State Personal Property Taxes and Certain Retroactive State Taxes. Initiative Constitutional Amendment.](https://voterguide.sos.ca.gov/propositions/42/index.htm) | 12474 / `PROP_42_2026` | Add record after inactive/duplicate audit. Official qualified-list link and proposition page agree on number, title and election. |
| 43 | [Limits Voters’ Ability to Raise Revenues for Local Government Services. Legislative Constitutional Amendment.](https://voterguide.sos.ca.gov/propositions/43/index.htm) | 12475 / `PROP_43_2026` | Add record after inactive/duplicate audit. Official qualified-list link and proposition page agree on number, title and election. |
| 44 | [Requires Community Health Clinics Spend 90% Of Revenue on Program Services. Initiative Statute.](https://voterguide.sos.ca.gov/propositions/44/index.htm) | 12476 / `PROP_44_2026` | Add record after inactive/duplicate audit. Official qualified-list link and proposition page agree on number, title and election. |
| 45 | [Modifies Environmental Review for Certain Projects. Initiative Statute.](https://voterguide.sos.ca.gov/propositions/45/index.htm) | 12477 / `PROP_45_2026` | Add record after inactive/duplicate audit. Official qualified-list link and proposition page agree on number, title and election. |

All fourteen assignments use `2026-11-03`. New integer IDs reflect SQLite's existing sequence (12466 before loading), not the old table's row count.

## Withdrawal

ACA 13 remains integer **1**, with its original malformed canonical identifier and all editorial content retained.
It remains active in the curated public archive with an explicit `withdrawn` status for the removed November slate. It is excluded from the fourteen upcoming propositions, but both original public routes remain available.
Its legacy null election-date field remains null; no later election is invented.
The [SoS qualified page](https://www.sos.ca.gov/elections/ballot-measures/qualified-ballot-measures) identifies removal on June 25, 2026 under ACA 21.
The captured `aca-21.pdf` directs withdrawal from consideration. This changes ballot eligibility while preserving the existing public record and routes.

## All existing current/future CA_SOS records

Every one of the 22 pre-existing rows received a disposition. No inactive record is reactivated.

| Integer ID | Existing canonical ID | Disposition |
|---|---|---|
| 1 | `ACA 13 (Ward) Voting thresholds. (Res. Ch. 176, 20` | Withdraw from active slate; retain row and evidence. |
| 2 | `SCA 1 (Newman) Elections: recall of state officers` | Match Proposition 5; preserve integer ID and all canonical keys. |
| 3 | `Assembly Bill 440, Chapter 82, Statutes of 2024` | Leave inactive AB 440 (2024) untouched. No current official assignment to this bill; Proposition 2 is ACA 20 (2026), not AB 440. |
| 1365 | `ACA_13` | Leave inactive duplicate untouched; master_id=1. |
| 1366 | `SCA_1` | Leave inactive duplicate untouched; master_id=2. |
| 1367 | `None` | Leave inactive duplicate untouched; master_id=3. |
| 10918 | `None` | Leave inactive duplicate untouched; master_id=1365. |
| 10919 | `None` | Leave inactive duplicate untouched; master_id=1366. |
| 10920 | `None` | Leave inactive duplicate untouched; master_id=1367. |
| 10956 | `SB_42` | Match Proposition 4; preserve integer ID and all canonical keys. |
| 10957 | `AB_440` | Leave inactive AB 440 (2024) untouched. No current official assignment to this bill; Proposition 2 is ACA 20 (2026), not AB 440. |
| 10958 | `INIT_9034` | Leave inactive parser artifact untouched; no identity evidence for reactivation. |
| 10959 | `INIT_2026` | Leave inactive parser artifact untouched; no identity evidence for reactivation. |
| 10960 | `INIT_1993` | Match Proposition 3; preserve integer ID and all canonical keys. |
| 10961 | `INIT_6814` | Leave inactive parser artifact untouched; no identity evidence for reactivation. |
| 10962 | `INIT_1500` | Leave inactive parser artifact untouched; no identity evidence for reactivation. |
| 10963 | `INIT_2025` | Leave inactive parser artifact untouched; no identity evidence for reactivation. |
| 10964 | `INIT_1974` | Leave inactive duplicate untouched; master_id=10956. |
| 10965 | `INIT_2024` | Leave inactive parser artifact untouched; no identity evidence for reactivation. |
| 10966 | `INIT_1911` | Leave inactive failed-to-qualify initiative 25-0005A1 untouched. No evidence that it is a current numbered measure; do not match on tax-policy similarity. |
| 10967 | `INIT_0011` | Leave inactive parser artifact untouched; no identity evidence for reactivation. |
| 10968 | `INIT_0033` | Leave inactive parser artifact untouched; no identity evidence for reactivation. |

## Identity qualifications

- Initiative 1993's current canonical ID is `INIT_1993`, while both stored fingerprint strings still contain `INIT_2012`. The official initiative number, AG number, formal Act, and constitutional section support the Proposition 3 match. Neither fingerprint is regenerated.
- Policy resemblance does not support merging the failed-to-qualify 25-0005A1 fragment into a current tax proposition. That inactive record is left untouched.
- Inactive AB 440 rows have no current official assignment. Proposition 2's law expressly identifies ACA 20 (2026), so it is a new record.
- The source PDFs sometimes contain the end or beginning of neighboring propositions. Identity evidence is taken from the explicitly labeled proposition section, not merely the filename.

## Source custody

The fixture directory contains 23 complete official HTML/PDF artifacts, their source/final URLs, capture timestamps, byte sizes, and SHA-256 hashes in `review-corrections.json` (the original `review.json` remains historical evidence).
This includes the qualified list, voter-guide index, fourteen proposition pages, four law PDFs, the withdrawal law, the eligible-initiative crosswalk, and AG 25-0016.
No county crawl, all-source scraper, or campaign-site traversal was performed.
The normalized descriptions use the official neutral overview preceding "Fiscal Impact"; campaign arguments and endorsements are excluded.
Existing generated summaries and research fields have separate ownership and were preserved.
