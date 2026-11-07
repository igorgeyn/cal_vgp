# How fine-grained can election data get for these measures?

**Date:** November 5, 2026 (E+2). Companion to the
[local measures plan](local_measures_completion_plan_20261105.md). Results below are still
unofficial; counties were counting ballots when this was checked. "Tested" means the file or
endpoint was fetched and opened on this date. No data was loaded into CalBallot.

## Answer

| Rank | Grain | Vote choice or turnout | Local measures? | Access | When |
|---|---|---|---|---|---|
| 1 | **Individual ballot** (cast vote record) | Choice | Yes, in principle | County-by-county records requests; mostly not posted | After certification; kept 22 months |
| 1 | **Individual voter** (voter file + history) | Turnout, no choice | Yes, by address | SOS or county application; about $100 maximum statewide; restricted use | After counties update history (date unknown) |
| 2 | **Census block × party, age, sex, surname** | Turnout | Whole election only, not per measure | Free, Statewide Database | Est. spring 2027 |
| 3 | **Precinct split × vote method** | Both | **Yes** | Free, county files | San Mateo today |
| 3 | **Precinct × vote method** | Both, with undervotes in some counties | **Yes** | Free, county files | LA today; all counties by about Dec 3 |
| 4 | Census block (statewide props only) | Choice, modelled from precinct | Props only | Free, Statewide Database | Est. spring 2027 |
| 5 | City and legislative district | Choice | Props only | SOS Supplement, spreadsheets | After Dec 11 |
| 6 | County | Choice | Props only | SOS API | Today |
| 7 | Whole jurisdiction | Both | Yes | County summaries | Today |

**Bottom line:** the finest data usable on the public site is **precinct by vote method**.
It is required by law for precinct, available free, and already live for San Mateo and LA.
Ballot-level and voter-level data are obtainable, but they are research assets, not site
content.

## What each layer actually contains

### Precinct level, the working layer

Law:
- [Elections Code §15374(a)(2)](https://california.public.law/codes/elections_code_section_15374)
  requires the votes "at each precinct for each candidate and for and against each measure".
- [§15372](https://california.public.law/codes/elections_code_section_15372) requires online
  posting in a spreadsheet-compatible format for at least 10 years, but only if the county's
  system can produce that format without modification. So the mandate covers all 53 counties;
  clean spreadsheets are not guaranteed.

| County | Tested | Contents |
|---|---|---|
| San Mateo | [Results page](https://smcacre.gov/elections/november-3-2026-election-results); CSV at `/media/9149` (Nov 5 report; the media ID may change per report) | 34,045 rows, 132 contests, **all 29 measures**, 333 precincts, 349 splits. Registered, voters, turnout, votes, undervotes, overvotes, each split into Vote Centers and Vote by Mail. Burlingame R sums to 68.9% yes. Also a precinct turnout PDF. |
| Los Angeles | [`4348_svc_precinct_public.pdf`](https://content.lavote.gov/docs/rrcc/svc/4348_svc_precinct_public.pdf), 97 MB, 9,805 pages | "Semifinal Official Canvass V2", created Nov 4. 82 measure sections (68 local + 14 props) with registration, ballots cast, yes and no by precinct, plus a vote-by-mail line. Extractable text; needs parsing. |
| Los Angeles | [`text-results/4348`](https://results.lavote.gov/text-results/4348); IDs at [`election-list/text`](https://results.lavote.gov/election-list/text) | County totals for all measures with the full question and supporters/opponents. Turnout 42.81% as of Nov 5, 74.86% by mail. **Note:** IDs 4339-4342 fail; 4348 is the November election. |
| San Bernardino | [Results](https://results.rov.sbcounty.gov/Results/20261103/) with `ElectionSummaryReportRPT.xlsx` | Contest-level turnout today: Upland A shows 17,885 ballots of 50,199 registered. |
| San Bernardino | [June 2026 SOV index](https://elections.sbcounty.gov/elections/2026/0602/sov/) (November should follow the same path) | One PDF per contest: Mail, Polling Place and Total for each precinct, with registered, cards cast, undervotes, overvotes, yes and no. Masks small precincts with `****`. Plus a turnout-by-precinct PDF. Dated June 26, so about 24 days after that election. |

Other formats seen in search results, not opened: Santa Clara PDF and XLS; Marin PDF and
Excel; Inyo spreadsheet; San Luis Obispo and Santa Cruz PDFs; Sonoma, Yolo and Contra Costa
"ElectionStats" sites. Expect a PDF-heavy mix. A per-county format census belongs in Phase 1.

### Individual ballots (cast vote records)

- **State position:** [CC/ROV #24220](https://elections.cdn.sos.ca.gov/ccrov/2024/october/24220rr.pdf)
  says ballot images may not be copied or posted. CVR reports "may be provided to requesters"
  as locked PDFs, with precincts of ten or fewer voters redacted. It is framed as the
  Secretary of State's opinion, and an [Alameda board letter](https://www.acgov.org/board/bos_calendar/documents/DocsAgendaReg_11_12_24/GENERAL%20ADMINISTRATION/Regular%20Calendar/Supervisor%20Carson_378670.pdf)
  calls it non-binding, noting San Francisco did not adopt it.
- **Published openly:** San Francisco, per the Alameda letter and a [2020 Director's Report](https://sfgov.org/electionscommission/sites/default/files/Documents/meetings/2020/2020-12-16-commission/December%202020%20Director%20Report.pdf).
  Its site refused scripted access, so November 2026 files are unverified.
- **Alameda:** the board directed release in 2024. Current practice could not be confirmed.
- **By request:** a [MuckRock campaign](https://www.muckrock.com/accounts/profile/AConevska22/)
  for 2022 and 2024 shows, per search snippets, releases from Orange, San Diego (2024 only, as
  a spreadsheet), Imperial (redacted), Marin and Kern; PDF-only from Merced; nothing from
  Humboldt. Pages could not be opened directly.
- **Prior art:** [Kuriwaki et al.](https://arxiv.org/abs/2411.05020) assembled 14.2 million
  California presidential votes (82%) from 2020 CVRs, naming San Mateo and San Bernardino among
  the counties. Its released scope is partisan offices, so measures would need the raw files.
- **Limits:** that paper says multi-page ballots were irreversibly separated in LA, San
  Francisco, San Bernardino and Ventura, so one voter's full ballot could not be rebuilt there.
  The same may apply to 2026, and it matters for any cross-contest analysis.

### Individual voters

The [SOS application](https://elections.cdn.sos.ca.gov/pdfs/voter-file-application.pdf)
(August 2023 revision) offers voter, voting-history and district files. Participation history
gives election date and voting method. The fee is $15 per thousand records, capped at $100.
Eligible uses are election, scholarly, journalistic, political and governmental. Commercial use
and sharing without approval are prohibited, and the data is "NOT public data". It shows
whether someone voted, never how. It cannot sit in a public repo or on the site.

### Statewide Database

[Precinct metadata](https://statewidedatabase.org/info/metadata/precinct_data.html) and the
[2024 index](https://www.statewidedatabase.org/d20/g24.html) were tested.
- Statewide props and candidates by precinct. Local candidates since 2022, but
  [local measures are excluded](https://statewidedatabase.org/faq.html): San Mateo's 2024 local
  files had zero measure rows.
- Registration, mail, poll and voter files by precinct and **2020 census block**. San Mateo's
  block voter file has 6,449 rows and 141 columns: party, sex, age bands by party, and
  surname-derived Latino and Asian groups. Values are whole numbers.
- Precincts under ten voters are masked. Surname ethnicity is an inference.
- **Lag:** San Mateo files dated 3.7 months after June 2026 and 5 months after November 2025.
  November 2024's are dated a year later, possibly a re-issue. Hence the spring 2027 estimate.

### Secretary of State

- **Working:** [`returns/ballot-measures`](https://api.sos.ca.gov/returns/ballot-measures) and
  `returns/ballot-measures/county/{slug}` give JSON yes/no by prop. "100% of precincts" here does
  not mean counting is finished.
- **Do not use:** `returns/status`. It returned September 2024 values.
- **After certification:** the [2024 Statement of Vote](https://www.sos.ca.gov/elections/prior-elections/statewide-election-results/general-election-nov-5-2024/statement-vote)
  shows the pattern: `csv-ballot-measures.xlsx`, plus Supplement files such as
  `ssov/ballot-measure-all.xlsx`, `-congress` and `-senate`. Local measures are not included.

### Aggregators tested

Neither replaces county files for local measures.

| Source | Result |
|---|---|
| [MEDSL 2024](https://github.com/MEDSL/2024-elections-official) `ca24.zip` | All 58 counties by precinct and 10 props, but 0 local measures, and vote method is `TOTAL` only |
| [OpenElections CA](https://github.com/openelections/openelections-data-ca) | 48 county files for 2024. Butte has 5 offices and no measures |
| [UF Election Lab](https://election.lab.ufl.edu/data-archive/california/) | 2016 and 2020 VEST precinct data, plus some 2024 city files |
| [Coleman](https://californiacityfinance.com/Votes2611prelim.pdf) | Measure-level % yes, useful as a cross-check only |

## Implications for CalBallot

1. **Publish precinct results for local measures; nobody else assembles them.** None of the
   aggregators tested carry them, so this could be a distinctive dataset.
2. **Mask before publishing.** San Mateo's CSV shows a 2-voter precinct split unmasked, so its
   votes can reveal how individuals voted. Adopt one rule, such as merging or hiding precincts of
   ten or fewer voters, whatever the source does.
3. **This solves the multi-county trap.** A cross-county measure's outcome can be rebuilt by
   summing each county's precinct files once they are certified.
4. **Roll-off becomes measurable.** Undervotes per measure show how many voters skipped it.
   This is a real measure-level turnout figure, with a method split in San Mateo.
5. **Keep the precinct IDs and the election.** Boundaries change each election, so precinct
   rows need a per-election key. San Mateo IDs look compatible with the Statewide Database
   (`10001` in both), which could allow a block-level join later. That join is untested.
6. **File 2026 CVR requests after certification** if research use is wanted. Retention is 22
   months, and San Diego's 2022 files were already gone when requested in 2025.

## Not verified

- County formats beyond those tested. This covers about a quarter of the 53 counties, mostly
  from search results.
- San Francisco's current data pages and Alameda's current CVR practice.
- The enacted text of SB 1328; the SOS memo was read, the chaptered bill was not.
- MuckRock outcomes, which come from search snippets.
- When November 2026 participation history reaches the voter file.
- Whether all counties split precinct results by vote method. It is not in §15374, and the
  Statewide Database notes that not all counties report it separately.
