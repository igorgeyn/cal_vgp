# Codex: Bay Area recon sweep (workplan B2)

> **For Codex:** Reconnaissance, not a build. The deliverable is
> **findings and a recommendation**, not a scraper. Estimated half a
> day. Do not write any county scraper as part of this task.
>
> Self-contained; assume no session memory. Facts verified 2026-08-31.

---

## 1. Why this is now the priority

The registrar pipeline has one live county: **San Bernardino**, which
publishes its measures roughly **four months before** the election,
with official documents attached — notices, resolutions, full text,
impartial analyses, tax rate statements, and arguments on both sides.
That forward-looking capture is the product: voters can read the
official record before they vote.

**Los Angeles was going to be next, and recon just disqualified it for
that purpose.** Its results portal (`results.lavote.gov/text-results/{id}`)
lists 73 elections, all of them past. The highest ID is 4338 (the June
2, 2026 primary); 4339, 4340 and 4342 all return HTTP 500. LA publishes
elections **at or after** election day. It is a rich *archive* source —
73 elections, though with multi-character measure letters (BB, CPT,
LCF, NDC) — but it contributes **nothing** to November 2026 coverage.

That exposes an assumption nobody has tested: **we do not know whether
any county other than San Bernardino publishes measures ahead of an
election.** If none do, "current-election coverage" is not a reachable
goal this cycle and the project is an archive effort until 2028. That
is the question this sweep exists to answer.

## 2. Counties to probe

Chosen by local-measure volume, not population — the original
five-county selection used population and that turned out to be the
wrong proxy (see `docs/plans/registrar_county_expansion_workplan.md`
§2). These five have **never been probed** and each individually
out-produces Orange, Riverside, and San Bernardino:

| County | Local measure records | Share |
|---|---:|---:|
| Alameda | 598 | 5.4% |
| Santa Clara | 531 | 4.8% |
| San Mateo | 458 | 4.2% |
| San Francisco | 386 | 3.5% |
| Contra Costa | 370 | 3.4% |

**Starting-point domains are guesses and must be verified, not
trusted.** A prior plan listed `sbcrov.com` for San Bernardino; by the
time it was built, that domain no longer resolved and the real host was
`elections.sbcounty.gov`. Find each county's actual registrar/elections
site rather than assuming. San Francisco is a consolidated city-county
and may be structured differently from the rest.

## 3. The decisive question

For each county, in priority order:

1. **Does it publish measures for an upcoming election, before that
   election?** This is the one that matters. If yes, what lead time —
   is November 2026 visible now?
2. **What documents accompany a measure?** Impartial analysis,
   arguments for/against, rebuttals, full text, tax rate statements —
   or only a name and a number? Document availability is the project's
   differentiator.
3. **Is there a stable per-election URL pattern**, and how are
   elections enumerated? San Bernardino uses `{year}/{mmdd}`; Orange
   uses slugs; LA uses sequential integer IDs. Expect a fourth shape.
4. **What is the page structure?** A table (San Bernardino), sectioned
   contest blocks (LA), or something else. Note whether it is
   server-rendered or needs JavaScript.
5. **Any access barrier?** San Diego 403s generic User-Agents;
   Riverside sits behind a Cloudflare challenge. Record what the
   polite UA does and does not defeat.
6. **Does it publish results too**, and how far back?

## 4. How to probe

Use the existing harness at `scraper/scripts/recon/probe.py`, or the
same approach if you prefer a fresh script.

**The polite User-Agent is non-negotiable:**

```
cal-vgp-registrar-scraper/0.1 (+https://github.com/igorgeyn/cal_vgp; contact: igorgeyn@gmail.com)
```

Rate-limit yourself — a couple of seconds between requests to the same
host, and keep total volume low. These are public-records sites run by
county governments on modest infrastructure, and the politeness
defaults exist because this project intends to keep scraping them
weekly for years. Do not crawl broadly; probe the specific pages you
need to answer §3.

Save raw artifacts under `scraper/data/registrar_recon/` (gitignored)
so findings are re-checkable.

## 5. Deliverables

1. **Update `docs/plans/registrar_manifest.md`** with a section per
   county, matching the existing entries' structure. Mark clearly what
   was verified versus inferred.
2. **A recommendation**: which of the five is the best next build, and
   why. Weigh forward-publication ability first, then document
   richness, then structural simplicity. A county that publishes ahead
   with documents beats a higher-volume county that only publishes
   results.
3. **Answer the strategic question explicitly:** is San Bernardino
   unusual in publishing ahead, or is it normal? If none of the five
   publish ahead, say so plainly — that finding is more valuable than
   a build recommendation, and it should change the roadmap.
4. **Effort estimates** per county, in the shape of
   `docs/setup/registrar_developer_guide.md` §9's per-county notes.

## 6. Out of scope

- Writing any scraper, extractor, or test.
- Pinning test fixtures — that belongs to the build task for whichever
  county is chosen.
- Los Angeles, Orange, San Diego, Riverside — already recon'd, and LA
  was just re-verified.
- Modifying `scraper/data/ballot_measures.db` or any deployed site
  artifact.

## 7. Report

State per county: the real registrar domain, whether an upcoming
election is published and with what lead time, what documents are
attached, the URL/enumeration pattern, page structure, access
barriers, and your confidence in each. Then the overall
recommendation and the answer to §5.3.
