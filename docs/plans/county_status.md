# County status board

> **The single place to answer "where does each county stand?"**
> Detail lives elsewhere — recon findings in
> [`registrar_manifest.md`](registrar_manifest.md), prioritization and
> the maintenance argument in
> [`registrar_county_expansion_workplan.md`](registrar_county_expansion_workplan.md),
> the build procedure in
> [`../setup/registrar_developer_guide.md`](../setup/registrar_developer_guide.md).
> This file is the index over them. The sequence, the architectural
> debts, and the gates are in
> [`bay_area_county_workstream.md`](bay_area_county_workstream.md).
>
> **Last updated: 2026-08-31.** Update the row when a county's status
> changes; update "Captured now" after a notable cron run.

---

## The board

| County | Share of local measures | Status | Publishes ahead? | Nov 2026 visible | Documents | Effort | Blocker |
|---|---:|---|---|---|---|---|---|
| **San Bernardino** | 3.3% | 🟢 **LIVE** | ✅ ~4 months | **20 measures / 105 docs** | 9 roles, separate files | — | none |
| **San Mateo** | 4.2% | 🟣 **built / not enabled** | ✅ verified | **29 measures / 135 docs** | 8 labels, composite packets | review | rollout intentionally separate |
| **Alameda** | 5.4% | 🟢 **scouted, ready** | ✅ verified | **28 measures / 30 PDFs** | 1 scanned packet each; questions in HTML | **3–4d** | none — OCR taken off the path |
| **Santa Clara** | 4.8% | 🔴 **blocked** | ✅ (June proven) | unreachable | unknown | — | **403 firewall on every host** |
| **San Francisco** | 3.5% | 🟡 recon'd | ⏳ materials collected | guide offline | unknown | 4–7d | voter guide in maintenance |
| **Contra Costa** | 3.4% | 🟡 recon'd | ❓ unknown | unknown | archive 1997–2025 | 7–12d | AWS WAF |
| **Los Angeles** | 12.6% | 🟠 **archive only** | ❌ **no** | none — IDs >4338 are 500 | results only, 73 elections | 3–4d | publishes at/after election day |
| **Orange** | 4.1% | 🟡 recon'd (Jun) | unknown | unknown | unknown | 2–3d | pre-2020 URL pattern unknown |
| **San Diego** | 4.7% | 🟡 partial recon | unknown | unknown | unknown | 0.5d + 2–3d | **measures page never found** |
| **Riverside** | 4.1% | 🔴 blocked | unknown | unknown | unknown | 1d + 3–4d | Cloudflare; Playwright per-hop politeness unresolved |
| *48 others* | 27.1% | ⚪ unexamined | — | — | — | — | see workplan Tier 3 |

Coverage today: **1 of 58 counties — 3.3% of historical local measure
volume.** The ten counties above are 50.0% cumulative.

## The strategic answer (2026-08-31)

**San Bernardino is not unusual in publishing ahead.** Two of the five
newly probed counties expose November 2026 measures right now, 64 days
out; a third demonstrably published ahead of the June election. So
current-election coverage **is reachable this cycle** — the roadmap
does not collapse into an archive-only effort until 2028.

What *is* unusual about San Bernardino is the ~4-month lead and the
clean one-document-per-role structure. Expect counties to come online
at different points in the filing calendar rather than on one date,
and expect messier document shapes.

## What we have

**San Bernardino, November 3 2026** — 6 immutable prod snapshots since
2026-07-27, growing as the county files:

| Snapshot | Rows | Documents |
|---|---:|---:|
| Jul 27 | 8 | 16 |
| Aug 14 | 20 | 56 |
| Aug 27 | 20 | 88 |
| **Aug 31** | **20** | **105** |

Current role breakdown: resolution 20, text 20, analysis 20,
argument_for 19, notice 7, tax_rate_statement 7, and 4 each of
rebuttal_for / argument_against / rebuttal_against. **Rebuttals began
appearing in the Aug 31 run** — the archive is capturing the filing
process as it happens, which is material no other source retains.

20 of these measures are live on the site. The 105 documents are
**not** in the database — only one `pdf_url` per measure is. That gap
is the `measure_documents` table (open threads F1).

**San Mateo, November 3 2026** — the source adapter, fixture-pinned
extractor, offline interpreter, and runner registration are built. The pinned
page has 29 measure panels and 135 linked artifacts. Composite PDFs expand to
several semantic roles only during offline interpretation; four county charter
measures legitimately share one source packet, so San Mateo identity uses each
measure's unique impartial-analysis URL first. The county is deliberately not
in `ENABLED_COUNTIES`; production rollout remains a separate review step.

## What we think we can obtain

**This cycle (Nov 2026):** San Mateo is a straightforward yes.
Alameda is a yes with OCR work. Santa Clara and San Francisco are
probable but gated. That would be roughly **17–21%** of local measure
volume with current-election coverage — versus 3.3% today.

**Archive backfill:** Los Angeles alone is 12.6% and 73 elections
deep. Contra Costa's archive reaches back to 1997. These do not help
November but are large additions to historical depth — and both bring
the untested cross-source reconciliation problem
([`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md) #12) into play, since they
overlap existing CEDA rows.

**Not reachable by this route:** the 48-county tail at 27.1%.
Per-county adapters are the wrong tool at that scale.

## Known obstacles, by kind

**Anti-bot — and two different kinds of it (scouted 2026-08-31).**
Contra Costa (AWS WAF, HTTP 202 `x-amzn-waf-action: challenge`) and
Riverside serve *challenges*, which a browser can solve. **Santa Clara
serves a 403 "Attention Required!" block on every host tested** —
`vote.santaclaracounty.gov`, `sccvote.sccgov.org`, `www.sccgov.org`,
and their `robots.txt` — which a browser cannot, since the WAF has
already refused the IP/UA. So the Playwright prerequisite unblocks
**two** counties, not three. That fix remains worth ~1–2 days: today
the path checks robots and rate-limits only the initial navigation,
then hands redirects and subresources to the browser where neither
applies; it is also single-attempt and hard-codes `text/html`. Santa
Clara needs a different move entirely — ask the Registrar for access.
See the workstream plan §5 and the scout §2.

**Document shape.** Alameda ships scanned, *combined* PDF packets:
measured at **569 pages with 11 (2%) carrying extractable text, and 22
of 28 packets with none at all**. There is no partial-OCR path — but
the structured data (letter, jurisdiction, title, threshold, full
ballot question) is served as clean HTML from a second host, so the
answer is to capture packets whole and skip OCR entirely. San Mateo
has composite documents — "Resolution, Full Text and Tax Rate
Statement" is one PDF carrying three roles, which breaks the
one-document-one-role assumption in the current model.

**Source timing.** Los Angeles publishes only at/after election day.
San Francisco's voter guide is in maintenance. Neither is a defect to
engineer around; both are calendar facts to wait out.

**Unfound pages.** San Diego's per-election measures listing has never
been located despite the polite UA defeating its 403.

**Cross-county duplication (new, scouted).** "Measure RTM" is one
measure on the ballot in five of these counties, and they publish it
under different names and different thresholds. Per-county identity
minting will produce five unrelated records. Needs a decision before
San Mateo lands — see the workstream plan §7.

**Maintenance, the real ceiling.** Drift has run ~1 event per county
per 2 weeks. The capture/interpretation decoupling (shipped
`edb2978`) removed the worst consequence — a new document type now
fails an offline parse instead of losing that week's capture — but
structural drift still reds the cron. See the workplan §5.

## Next actions

1. **Review and enable San Mateo** as a separate production rollout.
2. **Build Alameda** after it, accepting the OCR work.
3. **Re-probe San Francisco** once the voter guide returns.
4. **Resolve the Playwright per-hop politeness prerequisite** before
   Santa Clara, Contra Costa, or Riverside.
5. **Decide on Los Angeles separately** — archive value is real and
   large, but it is a different project from November coverage.
