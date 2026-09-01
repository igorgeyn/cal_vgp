# Scout: Alameda + Santa Clara (2026-08-31)

> **Exploratory probe ahead of the build**, run to de-risk Track B and
> Track C of [`bay_area_county_workstream.md`](bay_area_county_workstream.md).
> Everything below was fetched live with the production User-Agent, at
> ≥2.5s per host, and saved under the gitignored
> `scraper/data/registrar_recon/`.
>
> **Headline: the Alameda OCR spike (B2) is answered — cancel it. And
> C3 unblocks two counties, not three.**

---

## 1. Alameda — the B2 question is settled

### The answer: OCR everything, or OCR nothing. Choose nothing.

All 30 PDFs on the November 3 2026 election page were downloaded and
examined for an extractable text layer:

| | |
|---|---:|
| PDFs | 30 |
| Total pages | **569** |
| Pages with any extractable text | **11 (2%)** |
| Measure packets with **zero** extractable text | **22 of 28** |
| Packets that are mostly born-digital | **0** |

The only two files with a usable text layer are the single-page
Randomized Alphabet Drawing PDFs, which are **not measures**.

Two details make this worse than "just run OCR":

**Page counts vary 5× to 56×, not the uniform 15 the recon reported
from its single sample.** Berkeley's rent ordinance packet is 24 pages;
the regional transit packet is 56. Median is ~19.

**The text that does exist is partly bad OCR already baked in.** From
`dublin_usd_parcel_tax_measure.pdf` page 17 — the only page of 20 with
any text:

```
BALLOT MEASURE ARGUMENT
SUBMISSION FORM
IXI Argument in Favor          <- checkbox glyph read as "IXI"
AUG 1 v 2025                   <- date stamp mangled
Tit e o 'E ection: ___________ <- "Title of Election"
```

That is worse than no text layer, because a parser would accept it.
Any role segmentation built on embedded text would be building on
this.

### But the structured data is available clean, with no OCR at all

`https://alamedacountyca.gov/rov_app/measures/election/260` returns 28
`.measureDescGroup` blocks, each carrying everything a card needs:

```html
<div class="measureDescGroup">
  <h3 class="measureDesc">Measure RTM - Regional Transit Measure</h3>
  <div class="measurePerc">Percentage Passing: N/A</div>
  <p class="measureText">To prevent major service cuts to BART …</p>
</div>
```

Letter, jurisdiction, title, threshold, and the **full ballot
question** — server-rendered, zero tables, all-ASCII.

**So the workstream plan's "fallback" is actually the right primary
design.** Capture the packet whole as `role="packet"`, ship the
fragment's structured fields, and defer per-role OCR indefinitely. The
card loses nothing a voter would notice; what is deferred is only the
ability to link *directly* to the argument-in-favor page inside a
scanned packet.

**Revised Alameda estimate: ~3–4 days, down from 5–8.** The OCR work
was the entire difference.

### Six things the recon got wrong or missed

**1.1 — The measures app is on a different host.** The recon records
`/rov_app/measures/election/{id}` without noting that it lives on
`alamedacountyca.gov`, not `acvote.alamedacountyca.gov`. On the acvote
host that path returns **404**. Alameda needs a **two-host** scraper —
the election page on `acvote.`, the measure questions on the bare
domain. Verified both ways.

**1.2 — Enumeration is a server-rendered `<select>`**, at
`alamedacountyca.gov/rov_app/measures`. It lists exactly six elections:

| ID | Election |
|---:|---|
| 260 | November 03, 2026 — General |
| 259 | June 02, 2026 — Direct Primary |
| 252 | November 05, 2024 — General |
| 248 | November 08, 2022 — General |
| 249 | May 03, 2022 — Livermore USD Special |
| 241 | November 03, 2020 — General |

This confirms the recon's warning that IDs are not chronological (249
post-dates 248 but precedes it by ID). It also caps this endpoint's
archive depth at **2020** — six elections, not the "2018-present"
the election-selector suggested. Backfill beyond that needs the
separate archived-elections page.

**1.3 — Non-measure PDFs are separable by directory, not just label.**
Measure documents live under
`/acvote-assets/02_election_information/PDFs/20261103/Measures/`;
the two Randomized Alphabet Drawings live under
`.../20261103/Random Alpha/`. A path-based exclusion is far more
robust than matching on link text — and note the **election date is in
the path** (`20261103`), which is a second, independent scope check.

**1.4 — One filename contains literal spaces.**
`city_of_berkeley sales tax measure.pdf`, where the other 27 use
underscores. It fetches fine with `%20`, but a naive
filename-as-storage-key will produce a different key than a naive
URL-derived one. Pin it as a fixture.

**1.5 — The published threshold is missing on four measures**, and
they are not measures without thresholds:

| Threshold shown | Count |
|---|---:|
| `50%` | 19 |
| `2/3` | 5 |
| **`N/A`** | **4** |

The four are RTM, San Lorenzo USD **Education Parcel Tax** (legally
2/3), Sunol Glen USD **GO Bond** (55% for school bonds), and Emeryville
Business Tax. San Mateo publishes the same regional measure as
"Majority Voter Approval Required" while Alameda shows `N/A` — so
`N/A` means *unpublished*, not *no threshold*. **Load it as null and
fail loud; never as a threshold value.** This is
[`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md) #1 arriving from a new source.

**1.6 — The two hosts disagree on title casing.** The election page
says "City of Alameda"; the fragment says "City Of Alameda". **Join
the two sources on measure letter, never on title text.**

### What the election page gives you for free

The 28 measure links are already fully structured in their link text —
`Measure {LETTER} - {JURISDICTION} - {TITLE}` — so letter and
jurisdiction are parseable from the election page alone. Letters run
**RTM, then I through II** (I–Z, AA–II).

## 2. Santa Clara — worse than "gated", and C3 will not fix it

Every county-operated host tested returns **HTTP 403 with Cloudflare's
"Attention Required!"** page:

| Host | Result |
|---|---|
| `vote.santaclaracounty.gov` (all paths) | 403 Cloudflare |
| `vote.santaclaracounty.gov/robots.txt` | **403 Cloudflare** |
| `sccvote.sccgov.org` | 403 Cloudflare |
| `www.sccgov.org/robots.txt` | 403 Cloudflare |

**This is a firewall block, not a JavaScript challenge.** The
distinction decides whether Playwright helps. A JS challenge serves
HTTP 503 and "Just a moment…", and a real browser solves it by
executing the challenge. A 403 "Attention Required!" is a WAF rule
that already decided to refuse — headless Chromium from the same IP
with the same honest User-Agent will get the same 403.

**Therefore C3 (the Playwright politeness prerequisite) unblocks two
counties, not three.** Contra Costa returns HTTP 202 with
`x-amzn-waf-action: challenge`, which *is* the solvable kind, and
Riverside was recorded as a challenge too. Santa Clara is a different
problem and needs a different move. The workstream plan overstated
this and is corrected.

**No alternative channel exists.** `data.sccgov.org` is a Socrata open
data portal that *is* reachable, with a permissive robots.txt
(`User-agent: * / Crawl-delay: 1`). Its Santa Clara-scoped catalog
holds **two** election datasets — "Post-Election Trends" and "Oaths of
Office" — and **zero ballot-measure data**. Dead end.

### A robots.txt divergence worth knowing about

When robots.txt returns 403, the two conventions disagree:

- **This project** treats any status ≥ 300 as unfetchable → **allowed**
  ([`base.py:669`](../../scraper/src/scrapers/registrar/base.py#L669)).
  This matches RFC 9309 §2.3.1.3.
- **Python's stdlib `robotparser`** treats 401/403 as
  **disallow-everything**, following the older Google convention.

Not a bug — the project is RFC-conformant, and it fails fast anyway
since `_request_with_retries` never retries a non-429 4xx. But it
means the scraper *would* attempt Santa Clara and collect 403s, rather
than declining up front. Worth a comment in `base.py` so the next
person does not read it as an oversight.

### The recommendation: ask

Search engines can evidently crawl these pages — the recon read the
June 2026 measure list through indexed copies — so the block is
keyed on User-Agent or IP reputation, not on the content. **Email the
Registrar of Voters and ask for an allowlist entry or a data feed.**
County ROVs generally want their measure data distributed; this is a
one-email experiment with a plausible yes, and it costs a fraction of
any engineering workaround. Deliberately spoofing a browser
User-Agent to get around the WAF is the one option that should stay
off the table — it is exactly the discipline this project has been
strict about everywhere else.

If the answer is no, defer Santa Clara to 2028 and spend the time on
Contra Costa, which at least fails in a solvable way.

## 3. Cross-county: one measure, five counties

**Measure RTM is a regional measure spanning Alameda, Contra Costa,
San Mateo, Santa Clara, and San Francisco.** Verified in two counties
already:

| County | Letter | Threshold shown |
|---|---|---|
| Alameda | `Measure RTM` | `N/A` |
| San Mateo | `Regional Measure` | `Majority Voter Approval Required` |

Its own notice PDF names all five counties, and the ballot question
specifies a 0.5% sales tax in four of them and 1% in San Francisco.

The identity model mints IDs as `REG_{COUNTY}_{DATE}_{digest}`, keyed
per county. So **five county scrapers will mint five distinct
measure_ids for one real measure**, with different letters, different
thresholds, and different document sets. Three of those five counties
are in this workstream, and San Mateo is being built right now.

This is not a blocker — it is arguably correct that a San Mateo voter
sees it as their measure. But it needs a deliberate decision before
the second instance lands, or the site will show near-duplicate cards
with contradictory thresholds and no relationship between them.

**Suggested shape:** keep per-county rows (they are genuinely
different ballot items with different local documents), add a nullable
`regional_measure_key` that all five share, and let the UI collapse or
cross-link on it. Cheap now, expensive after five counties ship.

## 4. What changes in the plan

| Item | Was | Now |
|---|---|---|
| **B2** OCR spike | 1 day, go/no-go | **Cancel.** Answered: 2% of pages have text. Go packet-whole. |
| **B3** Alameda build | 5–8 days | **3–4 days** — OCR was the whole difference |
| **C3** Playwright | unblocks 3 counties | **unblocks 2** (Contra Costa, Riverside) |
| **C1** Santa Clara | blocked by C3 | **blocked on a policy/contact decision** |
| — | — | **NEW:** regional-measure identity, before San Mateo lands |

## 5. Reproducing this

Script: `scratchpad/scout_alameda_sc.py` (session scratchpad).
Artifacts: `scraper/data/registrar_recon/` — gitignored, currently
315 MB including prior runs. The 30 Alameda PDFs are worth keeping
until Alameda's fixtures are pinned; they are the evidence for §1.

Network volume was ~40 MB across ~45 requests over two hosts, all at
≥2.5s spacing with the production User-Agent.
