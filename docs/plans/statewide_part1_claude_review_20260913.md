Independent review: Statewide Part 1
Recommendation: READY FOR PART 2 WITH CONDITIONS
Confidence: high that the data and identities are correct. Medium-high that the conditions below are enough.

The core work holds up. The fourteen-proposition slate, the three identity matches, the ACA 13 withdrawal evidence and the 22 dispositions are all correct. I checked each against the captured SoS and legislative sources directly, not against Codex's ledger. Applying the committed review to a fresh backup reproduces the candidate table for table. Check mode writes nothing, and all 54 tests pass.

But the candidate isn't ready to publish as it stands, and three problems sit in the contract Part 2 builds on:

The public projection shows AI summaries that contradict the official text.
The withdrawn record silently vanishes from the entire archive.
The new proposition search ranks the wrong measure first.
Part 2's page builder has to consume this same projection. Fixing these after Part 2 regenerates about 12,000 pages would mean redoing that integration. So conditions C1–C4 should be Part 2's first step, before any page generation or production load.

None of this requires re-capturing sources or re-deriving identities. The reviewed data stands.

1. Findings, ordered by severity
F1 · HIGH, confirmed — retained AI summaries contradict the official titles shown directly above them
Where:

The modal prefers summary_text over description (generator.py:~14730–14736), and cards do the same.
The projection supplies the official title but no official description (statewide_ballot.py:271–272).
Matched rows have description = NULL.
What readers see:

Prop 4. The official title is "Repeals Prohibition Against Public Funding of Election Campaigns". The summary underneath says it "would establish a public campaign financing system… allowing eligible candidates to receive government funding". The official summary says it repeals a prohibition, and that public funding programs may not use earmarked funds. The measure permits public financing; it does not establish it. Screenshot: 20260913_claude_review/browser/mobile-10956-modal.png.
Prop 5. The retained summary says a recalled office is filled by "existing constitutional succession rules (such as the Lieutenant Governor becoming Governor)". The official summary says vacancies are filled "by subsequent special election or appointment".
Prop 3. The retained summary gives "$360,000–$721,000". The official summary gives "$371,000 (adjusted annually)".
Expected versus actual. The other 11 propositions show the official description under the same "📝 SUMMARY" heading. Props 3–5 show legacy AI text under that identical heading, with no AI label in the SPA. The individual-page builder does label it "AI-generated".

Impact. Two of fourteen statewide measures present a mischaracterization directly beneath the official title, on a page whose purpose is accurate ballot information.

Smallest remedy. review.json already contains a source-validated official description for all 14 entries: read_review checks every one against the captured page. The fix:

Store it in statewide_ballot_entries (or project it from the stored review).
Have cards, modal and individual pages prefer it for assigned statewide records.
Either suppress the three legacy summaries or show them explicitly labeled as AI-generated.
About 1–2 agent-hours.

When: C1, before Part 2 page generation.

F2 · MEDIUM-HIGH, confirmed — is_active=0 removes ACA 13 from the whole archive, not just from the upcoming list
Where: statewide_ballot.py:269–270 (withdrawn rows are dropped), build_measure_pages.py:205–210 (rmtree then active-only regeneration).

What happens, as probed:

Searching "ACA 13" returns 0 results.
The old route silently disappears. Loading #m=1 opens nothing and rewrites the URL to /, with no message and no page error.
The indexed page is stale today, and Part 2 would delete it. measures/1.html is live and in the sitemap, titled "ACA 13 (Ward) — Protect and Retain the Majority Vote Act — 2026" with a year-based "Upcoming" label. Running Part 2's builder as written deletes it, turning an indexed URL into a 404.
Nothing renders the withdrawn assignment. The row exists with its evidence, but no consumer displays it.
Impact. A genuine, newsworthy ballot event becomes undiscoverable, and a live page stays wrong until it's deleted.

Remedy options:

(A) Keep ACA 13 inactive, but have Part 2 emit an explicit withdrawn page at measures/1.html, with an SPA route message.
(B, recommended) Keep ACA 13 active and project ballot_status='withdrawn'. Exclude it from the hero and upcoming selection. Card, modal and page all say "Removed from the November 3, 2026 ballot on June 25, 2026 under ACA 21", which the table already supports.
Both cost roughly 1–2 agent-hours. (B) needs no special-case pages and keeps search and routes working.

When: C2, before page generation. This is Igor's product decision.

F3 · MEDIUM, confirmed — the new proposition search matches substrings and ranks the wrong measure first
Where: the search alias `Prop ${n} Proposition ${n}` (generator.py:10917–10918).

Trigger: type "Proposition 3" into #searchInput.

Actual result: 108 matches. Props 39, 38 and 37 rank above Prop 3, because "proposition 3" is a substring of "proposition 37/38/39". By the same mechanism, "Prop 4" matches Props 40–45.

Why the gate missed it. Codex's browser check asserts only filteredMeasures.some(m => m.id === 10960) (check_statewide_browser.py:59–60), and sets the search state programmatically.

Remedy: word-boundary designation matching, or boosting exact designation matches to the top, plus a test that asserts the first result for "Proposition 3" and "Prop 4". Under 1 agent-hour.

When: C3, before publication.

F4 · MEDIUM, confirmed — identity decisions aren't machine-bound to their evidence
Where: statewide_ballot.py:144–145. identity_evidence only has to be non-empty. The law PDFs, eligible list and AG filing are hashed but never parsed.

Reproduction, on copies:

Swapping the Prop 3 and Prop 4 identities is accepted by read_review, check, and apply. SB_42 becomes Prop 3.
Replacing all evidence with ["x"] also passes.
Impact. None on the current data: I verified the three matches independently (§2). But correctness rests entirely on human reading of the ledger, and Part 3 refreshes will produce new reviews.

Remedy: per match, a machine assertion naming the evidence file and a required literal, checked in read_review. For example, prop-4-law.pdf must contain "Senate Bill 42 of the 2025–2026 Regular Session", and eligible.html must contain "1993. (25-0016)". About 1 agent-hour.

When: before any new review. Optional before Part 2, since this review is verified.

F5 · MEDIUM — no safe path to production for a combined release
Where:

reconcile() refuses production by design (:163–167).
The verifier forbids any other row change relative to its baseline (verify_statewide_candidate.py:83–90).
Part 2 also plans to load the latest registrar capture.
Trigger: a single release DB that contains both the statewide correction and registrar changes.

Expected versus actual. Either the statewide gate rejects the combined DB, or production gets replaced by a file copy with no guard against changes made in the meantime.

Remedy. Define the sequence explicitly:

Back up production.
Run the registrar load and its own gate, if one is needed.
Take a fresh consistent backup.
Apply this review on a scratch copy.
Run this gate.
Replace production only if its SHA-256 still equals the backup source.
When: C4, before any production load.

F6 · LOW-MEDIUM, confirmed mechanism, no current effect — canonical IDs collide across years
The collision:

PROP_1 now spans 2022, 2024 and 2026.
PROP_2 spans 2024 and 2026.
Active measure_id values shared by more than one row go from 2 to 3.
Consumers keyed on measure_id without a year:

Research fallback. research_by_mid (generate_site.py:277) is last-write-wins.
Recommendations. recommendations[measure.measure_id] and allMeasures.find(m => m.measure_id === …) (generator.py:14791, 14796). 2026 rows sort first, so find() returns them.
Verified today: none of these rows has research, and no recommendation keys or targets name PROP_1 or PROP_2.

Trigger: the next research or embedding regeneration. A 2024 Prop 1 briefing could then attach to the 2026 Prop 1.

Remedy: year-scope those two lookups. That also fixes the pre-existing 2022/2024 collision. Alternatively, year-qualify new canonical IDs.

When: before any research or embedding rebuild. Record it in KNOWN_ISSUES.

F7 · LOW — the reconciler can't be re-run once anything else changes
Where: :176–183.

Replay drift (P7). After an unrelated last_seen_at update on a new row, replay raises "Previously applied correction has drifted".
Supersession (P8). An amended review can never be applied on top of this one.
This is fine for a one-shot promotion, but it can't serve as Part 3's refresh mechanism. Remedy in Part 3: check drift on assignment-owned fields only, and add explicit supersession.

F8 · LOW — the scratch-root guard protects only one file
Where: :163–167.

Reproduction (P5): --scratch-root . targeting a registrar backup in scraper/data/ is accepted. In apply mode it would mutate a recovery point.

Remedy: require the root to sit under scraper/data/statewide_recon/. When: before Part 2's recovery work relies on those backups.

F9 · LOW — the verification is less independent than it looks
Shared code. The verifier imports read_review, LEGISLATION_URLS and documents_for_website from the implementation it checks (:18–19).
Narrow public checks. They cover only IDs that already existed, plus assignment fields on new rows.
New rows' links go unchecked. Legislative Props 1, 2 and 43 carry an initiative-only "Eligible Measures (CA SOS)" link.
Scripted browser path. The browser check calls viewMeasure() directly.
Thin fixtures. The test fixture has no historical PROP_ rows, so cross-year behavior is untestable.
None of this hid a data defect. But F1 and F3 passed every gate.

F10 · LOW, optional — new propositions lack topics, and legislative measures show an initiative timeline
No topics. The 11 new records have no topic, so topic filters and Insights counts omit them. For example, filtering by taxes misses Props 40–42.
Wrong timeline. Legislative measures show a Filed → Circulating timeline that doesn't apply to them.
When: Part 4 readiness.

Pre-existing and out of scope: invalid-escape SyntaxWarnings in generator.py's JS strings; the hero hard-coded to 2026 (Part 4); the page builder using legacy titles and year-based "Upcoming" (already on the Part 2 list).

2. Identity decisions and design
I accept the reviewed-input approach. It is the right size for the problem. It avoids the multi-endpoint scraper, pins sources by hash, verifies preimages, and is exactly reproducible (P6).

Identity, verified against the source documents:

Decision	Independent evidence	Verdict
10960 INIT_1993 → Prop 3	eligible.html: "1993. (25-0016) PROVIDES PERMANENT FUNDING…". The AG filing and the Prop 3 law section both contain "The California Children's Education and Health Care Protection Act of 2026" and amend Section 36 of Article XIII, and the act name falls inside the Prop 3 section (chars 4642–41477)	Verified
The INIT_2012 fingerprint	The only "2012" in eligible.html is "the existing 2012 voter-approved tax rates". The legacy parser read a year as an initiative number, so it is a parser artifact, not a second initiative	Explained; supports the match
10956 SB_42 → Prop 4	Law PDF: "Senate Bill 42 of the 2025–2026 Regular Session (Chapter 245, Statutes of 2025)", giving 202520260SB42	Verified
id 2 SCA 1 → Prop 5	Law PDF: "Senate Constitutional Amendment 1 of the 2023–2024 Regular Session (Resolution Chapter 204, Statutes of 2024)". The session correction to 202320240SCA1 is right	Verified
ACA 13 withdrawn	The SoS note, inside the Nov 3 section. The ACA 21 capture carries "Adopted in Assembly JUN 25 2026" and a Secretary of State receipt line. The chapter number (131) appears only in the SoS note	Verified
Prop 2 is new, not AB 440	Law PDF: "Assembly Constitutional Amendment 20 … (Resolution Chapter 130, Statutes of 2026)"	Verified
11 insertions / 22 dispositions	The full-cohort guard rejects a missing disposition (P3). Only the listed rows changed	Verified
Slate reconstruction. I rebuilt the slate without the implementation's parser. There are exactly 14 voter-guide links under the Nov 3 heading. The only note is the ACA 13 removal, with two PDF links. The 2028 section contains only ACA 7. All 14 proposition pages match on number and banner, and each has a single summary paragraph split at "Fiscal Impact", with no campaign language.

Adjacent propositions share law-PDF pages, as the ledger warned. For example, page 4 of the Prop 4 PDF also contains Props 37 and 5. The identity citations come from the correctly labeled sections.

Premise I reject: that preserving legacy content is neutral. Keeping the IDs and fingerprints is right. Presenting unreviewed legacy summaries as the explanation beneath official titles is not (F1).

Second rejected premise: that is_active=0 adequately represents a withdrawal. It conflates "not on the upcoming ballot" with "not in the archive" (F2).

3. Verification performed
Repository state and hashes:

HEAD is ec650a2, unchanged. Part 1 is uncommitted.
I rehashed all 8 production inputs: unchanged.
All 6 code hashes match the evidence.
The final generator.py edit (15:10:31) precedes the build start (15:10:33), and the candidate HTML contains all six generator changes, so reports and bytes cover the same code.
Site and mirror are byte-identical: HTML, JSON and the Use CalBallot page.
Database (SQLite mode=ro on baseline and candidate):

Totals: 12,414 → 12,425 rows; 12,361 → 12,371 active.
The ID sequence runs 12466 → 12477.
The only schema additions are the two new tables and their auto-indexes.
Journal mode is delete.
The new, matched and withdrawn rows match the ledger, and I traced the collision surface.
Everything else:

Sources. Independent HTML reconstruction, plus PyMuPDF text checks on four law PDFs, the AG filing, and ACA 21.
Tests. 54 passed with a fresh reviewer basetemp and no cache.
Mutation probes P1–P10, on copies. Swap, junk evidence and a loose scratch root were accepted. An unmatched active row, reordered entries, drift and a second review were rejected. Reproduction was exact, and check mode left bytes and sidecars unchanged.
Reader probe in Chromium (external requests blocked), 1440px and 390px:
typed searches, a real hero-card click, and a click on a result card
initial-load deep links: #m=10960 and #m=12467 work; #m=1 silently fails
the default archive and the cleared-search archive both show 0 rows for 2026
no page errors
Counts reconcile: 14 propositions, 3 matched, 11 inserted, 1 withdrawn, 12,425 total, 12,371 active, 272 document roles, 239 links on 49 measures, 54 tests. The 129 last_seen_at regenerations match F1's documented exception and are bounded by the build window. The topic decrement (55 → 54) follows from ACA 13 leaving the active set.

Reconciling Codex's claims:

"Proposition search passed" is true only as presence. The ranking is wrong (F3).
"All fourteen modals verified" checked titles and IDs, not summary content (F1).
"Retained #m=<id> routes" holds for the three matched records. The withdrawn route fails silently.
Everything else checked out.
Limitations:

Only the as-captured state (Sept 13, 21:52 UTC) was examined, with no live source or CDN checks.
I used the existing candidate rather than rebuilding it.
No individual pages exist yet; that's Part 2.
The Insights payload was checked only through the verifier's equality test.
Evidence: scraper/data/statewide_recon/20260913_claude_review/, containing probes/, browser/reader-probe.json, the modal screenshots, and pytest-basetemp/.

4. What is sound and should be kept
The reviewed-input correction path and its preimage, full-cohort and hash checks. It is exactly reproducible, and a mid-transaction failure rolls back the new schema too.
Preserving integer and canonical IDs and legacy fingerprints. Finance, keyed on integer ID, and deep links keep working.
The narrow allowed-change lists in the verifier:
exact search-index accounting
multiset equality on unrelated tables
document-projection equality
bounded timestamp exceptions
The strict section parsing and the neutral-description boundary.
Numeric hero ordering, the "On Ballot" stage, and the corrected legislative session links.
The search change leaves the default archive intact.
5. Ordered actions
Before Part 2's page and bundle work:

C1 — Project and prefer official descriptions for assigned statewide records; suppress or label the three legacy AI summaries. (F1)
C2 — Decide ACA 13's representation. Needs Igor; I recommend (B): keep it active with a visible withdrawn status. (F2)
C3 — Word-boundary proposition search, with first-result tests. (F3)
Re-run apply on a fresh consistent backup, rebuild the candidate, and repeat the gate and browser check. Add assertions for summary content and search ranking.
Estimate: 3–5 agent-hours, 30–45 Igor-minutes.

During Part 2, before publication:
5. C4 — The promotion sequence, with a hash-preconditioned production swap. (F5)
6. The page builder consumes the same projection: official description, withdrawn handling, sitemap.
7. Tighten the scratch-root guard (F8). Add machine-checkable identity assertions (F4).

Later (Part 3 and beyond): drift and supersession semantics (F7); year-scoped measure_id consumers before any research or embedding rebuild (F6); topics for the new records and legislative timelines (F10); a more independent verifier (F9).

Decisions that need Igor:

ACA 13: visible as withdrawn (recommended), or removed from the archive with a tombstone page.
Legacy summaries on Props 3–5: replace with the official description (recommended), or keep beside it labeled as AI-generated.
