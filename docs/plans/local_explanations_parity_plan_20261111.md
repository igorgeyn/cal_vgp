# Plan: CalBallot explanations for the remaining 2026 local measures

**Status: deferred.** On November 11, 2026, Igor chose to ship the official questions and
results first (decision 2 in the [completion plan](local_measures_completion_plan_20261105.md#8-decisions-for-igor)).
This plan describes the full alternative so a later session can run it without
re-deriving anything. Start it only when Igor says so.

**Who this is for:** a Claude or Codex session picking this up cold. Read
[`CLAUDE.md`](../../CLAUDE.md), [`LESSONS_LEARNED.md`](../LESSONS_LEARNED.md) and the
[checklist](local_measures_checklist_20261107.md) first. The prompt to start is at the
end of this file.

## 1. Goal

Give every remaining November 3, 2026 local measure (about 413 records, in up to 53
counties) the same reviewed reader content the existing 49 San Bernardino and San Mateo
measures have:

- the official ballot question, verbatim;
- a separate CalBallot explanation;
- the approval requirement, only when the county publishes it;
- a citation for every source: URL, SHA-256 of the exact bytes, PDF pages and verified
  document role;
- notes on caveats, such as assessed versus market value;
- a review date and the extraction method.

**Done means** an entry in `scraper/src/website/data/county_2026.json` for each record. That
file's validator stops the build when it finds a malformed entry. Each record also gets a
row in the ledger, an independent review and a passing release.

## 2. Preconditions

This plan adds explanations on top of the questions-and-results release. It does not
replace it. Before starting, all of these must be true:

| Needed | Provided by |
|---|---|
| Each county's measure documents captured as immutable R2 snapshots, with hashes | Phase 1 (P1.1–P1.3) |
| Records loaded with identity, jurisdiction, letter, type, official question and result | Phases 2 and 4 |
| Direction A layout, with a result state and the results tab | Phase 3 |
| Measures' history labels and place names repaired, so explanations don't repeat CEDA errors | Phase 1b |

If the questions-and-results release has not shipped, stop. This work would block it.

## 3. The pattern to copy (the October release of 49)

Everything here already exists. Reuse it; don't redesign it.

- **Data file:** `scraper/src/website/data/county_2026.json`, schema version 1. Each entry
  has:
  - identity: `id`, `measure_id`, `county`, `county_slug`, `jurisdiction`,
    `election_date`, `measure_letter`;
  - content: `question`, `explanation`, `notes`, `vote_threshold`;
  - sources: `question_source` and `explanation_sources` are indexes into `sources`. Each
    source records `url`, `sha256`, `snapshot`, `snapshot_id`, `pages`, `role`,
    `verified_role` and `label`;
  - provenance: `reviewed_at`, `source_checked_at`, `extraction_method`.
- **Validator:** `validate_package()` in `scraper/src/website/county_content.py`. Source URLs
  must be https on the county's allowed host. Hashes must be 64 hex characters, and PDF
  pages must be cited. Advocacy documents are rejected. The question must cite a source
  whose verified role is `ballot_question`.
- **Binding:** content attaches only when the public document bytes and identity still
  match. A changed identity, threshold, source URL, role or cited PDF bytes stops the build
  and sends the record back for review.
- **Rendering:** both the explorer and the static pages go through `render_sections()` and
  the projection in `county_content.py`. The label reads "CalBallot explanation:
  AI-assisted, checked against the cited official documents."
- **Evidence:** everything is kept under `scraper/data/county_content/20261008/` (private,
  gitignored):
  - `ledger.json` and the rendered page images;
  - review prompts and raw outputs, and the candidate builds;
  - browser reports and `preservation.json`;
  - `deployment-verification.json`.
- **Scripts in that folder:** `extract_candidates.py` finds question pages and never
  approves content. `prepare.py`, `build_candidate.py`, `finalize_packet.py` and
  `promote_public.py` cover the rest.
- **Public record:** [`county_content_20261008.md`](county_content_20261008.md) and the
  [ledger](county_content_ledger_20261008.md).
- **Review prompts:** [pilot](../codex/county_content_pilot_review_20261008.md) and
  [integration](../codex/county_content_integration_review_20261008.md).

**The style of the 49 explanations:**
- **Length:** 13–64 words, median 47.
- **Voice:** neutral, describing what a yes vote does ("Authorize $898 million in bonds
  for…").
- **Content:** amounts, rates, duration, scope and oversight. Each explanation states
  whose revenue an estimate covers.
- **Notes:** 17 of the 49 have notes, for caveats such as "assessed value is not market
  value" and "rates are estimates".
- **Sources:** about 1.1 per entry.

## 4. What has to change in code

1. **Allowed hosts by county.** `SOURCE_HOSTS` and `LISTING_URLS` cover only `sb` and
   `smc`.
   - Move them into data generated from the Phase 1 census: county slug, allowed document
     hosts and listing URL.
   - Some counties leave documents to city clerks; San Diego says so. Those need a list of
     reviewed hosts per entry, not a wildcard.
   - Every host on that list needs a recorded reason, such as "city clerk publishes the
     resolution".
2. **County slugs** for all 53 counties, stable and short. Store them with the census
   data.
3. **Document role words.** `role` covers text, resolution, analysis and
   tax_rate_statement. `verified_role` covers ballot_question, measure_text,
   impartial_analysis and tax_rate_statement.
   - New counties may use other names, such as "full text" or "county counsel analysis".
     Map them onto these values. Don't add new public roles without a reason.
   - Arguments for and against, and rebuttals, must stay refused.
4. **Scanned packets.** Some counties publish image-only PDFs. Use the
   `extraction_method` value "Manual transcription checked against rendered PDF", which
   already exists. Keep page images for every cited page.
5. **Measures in more than one county.** A measure that spans counties, like the 12442
   regional transit district, gets one explanation that names the full scope. Each county's
   record carries the same text, and any revenue estimate states whose revenue it covers.
   - Decide whether such records share an explanation key or repeat the text.
   - Repeating the text is simpler, but it needs a check that the copies are identical.
6. **Scale.** About 460 entries in one file is fine. If review is easier per county, split
   the file into one per county with the same schema, loaded and validated together. Decide
   this in E0.
7. **Tests.** Extend the content and validator tests to every new county slug and host.
   Add any new role mapping. Cover a multi-county record, and an entry with no listed
   threshold, which must render "Not listed".

## 5. Work in chunks

Do one chunk at a time and get a Codex review after each, as in the
[checklist](local_measures_checklist_20261107.md). Keep that checklist updated with an
item per chunk and its evidence.

### E0. Sizing and tooling (no content)

- **Count the work.** List the records per county. For each, record which source documents
  exist (question, analysis, full text, tax rate statement), whether they are scanned, and
  how many pages a reviewer must read. Put the real estimate in the checklist.
- **Generalize the code** per §4, with tests. No content changes.
- **Write the drafting prompt and the review prompt** (§6, §7), each with a fixed output
  JSON schema.
- **Decide** whether to split the file by county, and how measures in more than one county
  are stored.
- Get a Codex review of E0.

### E1. Pilot of 6–8 hard cases

Pick records that stress the format:
- at least one from Los Angeles, which has a 14-page measure PDF;
- a scanned packet;
- a measure in more than one county;
- a city charter amendment;
- a special-district parcel tax;
- a county whose documents live on city clerk sites;
- one record whose "analysis" file turns out to be advocacy, if one exists. San
  Bernardino's Measure Z was that case.

Draft the pilot, verify it, then get both an independent Claude review and a Codex review.
Change the format only if the pilot shows it's wrong.

### E2 onward. Waves by county

- Los Angeles takes two or three waves of 20–30 records.
- Group smaller counties into waves of about 30 records.
- Each wave does §6 through §8, then builds a candidate and passes the release gates in §9.
- Release after each wave or each few waves, as Igor prefers. Every publish needs his go.

## 6. Drafting

**Inputs per record:**
- the captured source PDFs, already hashed, from the R2 snapshot;
- the record's identity from the database;
- rendered images of the candidate pages.

Run `extract_candidates.py`-style detection first. It finds question pages; it never
approves anything.

**Order of preference for sources:**
1. Ballot question: the resolution or ordinance text that contains the question.
2. Impartial analysis by the county counsel, city attorney or district counsel.
3. Tax rate statement, for bonds.
4. Full measure text.

**Never** use an argument for or against, a rebuttal, campaign material or news coverage. A
file labelled "analysis" is not trusted until a person or reviewer confirms the role from
the page itself.

**Draft each record as JSON with these fields:**
- `question`: verbatim; only whitespace and layout may be normalized.
- `question_source`, `explanation`, `explanation_sources` and `notes`.
- `vote_threshold`, only if the county publishes it.
- `extraction_method`.
- `open_issues`: anything uncertain, such as conflicting amounts in two documents. These
  are shown to reviewers, not readers.

**Rules for the explanation:**
- 30–65 words, neutral, and saying what the measure does.
- No recommendation, no prediction, and no adjectives that take a side.
- Use exact figures from the cited pages: amount, rate, base, duration, who pays,
  exemptions, oversight.
- Keep each of these pairs distinct:
  - bond principal versus total repayment;
  - assessed value versus market value;
  - annual versus total revenue;
  - revenue for the whole district versus revenue in one county;
  - authorization versus a requirement to spend.
- If a figure is an estimate, say so, or put the caveat in `notes`.
- **Tense:** these explanations are written after the election, but they describe what the
  measure proposes, in the same voice as the 49. The result appears separately; don't
  mention passing or failing in the explanation.
- When two documents conflict, cite the ballot question and note the conflict. Chino's
  $75,000 case is the precedent.

The drafter is an LLM, so every record is labelled "AI-assisted". The drafter sees only the
cited pages; no web search is allowed while drafting.

## 7. Verification and review

Three independent passes, all recorded in the ledger:

1. **Drafter self-check.**
   - Each figure in the explanation appears on a cited page; record the page.
   - The question matches the page character for character, after whitespace.
2. **Codex verification against rendered page images.** This is not optional. Text
   extraction can miss tables, scans and footnotes. Check:
   - the question wording;
   - every figure and qualification in the explanation;
   - that each source's role is what it claims to be;
   - when a packet holds several measures or several pages, that the right one is used.
3. **Independent Claude review**, read-only (Read, Grep and Glob only).
   - **No:** shell, network, edits or credentials; API keys are stripped from the
     environment.
   - **Unit:** one wave, using the same checks as the
     [pilot prompt](../codex/county_content_pilot_review_20261008.md).
   - **Kept:** the raw output, in the private evidence.
   - If the review stops early, for example at a session limit, record it as incomplete.
     Never describe it as a pass.

**Dispositions:**
- Each finding is fixed or explicitly accepted, with a reason, in the ledger.
- Content is not rewritten just because a review happened.
- Any record that is still unresolved stays at questions and results only. It does not ship
  with a weaker explanation.

## 8. Ledger and evidence

For each wave, under `scraper/data/county_content/<date>/`, which stays private:
- `ledger.json`;
- page images of every cited page;
- review prompts and raw outputs;
- candidate builds;
- browser reports;
- `preservation.json`;
- the deployment check.

The public record is a dated `county_content_<date>.md` plus a ledger table, like the
October release.

## 9. Release gates for each wave

The October gates, unchanged:

- **Strict build** with `--as-of`, from a backup copy of the database. The production
  database is never written; its hash is unchanged.
- **Preservation:** only that wave's measure pages change. Every other page is
  byte-identical. Finance, insights, recommendations, topic and quiz data are unchanged.
- **Browser checks** at 1440, 390 and 320px for every changed record:
  - the explanation and question are shown in full;
  - page citations are correct;
  - the finance fallback appears;
  - history IDs are valid;
  - no overflow and no JavaScript errors.

  Also run the election-status checker. Fix R7 first, since these records will have
  results.
- **Recovery:** a fresh frozen workspace, a private recovery update and an R2 read-back.
- **Igor's go-ahead**, then publish.
- **After publishing:** compare the served bytes with the tested bytes, check the live site
  on desktop and mobile, and write the receipt.

## 10. Traps already hit

- A file labelled "impartial analysis" that is really an argument in favor (San
  Bernardino's Measure Z). Confirm roles from the page.
- Scanned packets where text extraction returns nothing or garbage.
- Packets with several measures, where the question is attached to the wrong measure.
- Numbers that differ between the question and the resolution.
- A Windows console that shows a valid UTF-8 apostrophe as `�`. Check bytes, not terminal
  output.
- An approval threshold guessed from the measure type. Show "Not listed" unless the county
  publishes it.
- CEDA jurisdiction codes shown as place names. Phase 1b fixes this; don't copy CEDA
  labels into explanations.
- Blocked counties. Santa Clara (403), Contra Costa and Riverside all challenged scripts in
  August. Never bypass a challenge; use a person's browser download and record its hash,
  or leave the county at questions and results.

## 11. Out of scope

- Local campaign finance. The honest "not imported" notice stays.
- Statewide content.
- On-demand briefings, which stay BYO-LLM or pay-per-use with no bulk generation.
- Measures from other elections.

## 12. Questions for Igor before E1

1. Order of waves: Los Angeles first (most readers), or the smallest counties first
   (cheapest to prove the pipeline)?
2. Release cadence: publish after every wave, or batch several?
3. Is "AI-assisted, checked against the cited official documents" still the right label at
   this scale?
4. Is the 30–65 word range right, or should post-election explanations be shorter?

## 13. Prompt to start this work

```text
You are picking up the CalBallot local-explanations plan in
docs/plans/local_explanations_parity_plan_20261111.md (repo cal_vgp). Read CLAUDE.md,
docs/LESSONS_LEARNED.md, docs/plans/local_measures_checklist_20261107.md and that plan in
full before doing anything.

Confirm the preconditions in §2 against the repo and the checklist. If any is unmet, stop
and report which.

Then do chunk E0 only (§5): count the work per county from the captured sources,
generalize SOURCE_HOSTS/LISTING_URLS and county slugs with tests (§4), and write the
drafting and review prompts (§6–§7). Propose answers to the §4.5 and §4.6 decisions.
Add E0 items with evidence to the checklist.

Constraints: no content entries yet; production DB read-only (SQLite backup API for
builds); downloaded files untrusted (own directory, python -I); never bypass bot
challenges; no push, merge or publish without Igor's go; name files explicitly when
committing. Stop after E0 for a Codex review.
```
