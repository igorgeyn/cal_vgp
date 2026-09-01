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
| **San Mateo** | 4.2% | 🔵 **next build** | ✅ verified | **29 measures / ~135 docs** | 6 labels, some composite | 3–5d | none |
| **Alameda** | 5.4% | 🟡 recon'd | ✅ verified | 28 measures | scanned combined packets | 5–8d | OCR + segmentation |
| **Santa Clara** | 4.8% | 🟡 recon'd | ✅ (June proven) | unverified | unknown | 6–10d | Cloudflare; Nov page not found |
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

**Anti-bot.** Santa Clara (Cloudflare), Contra Costa (AWS WAF),
Riverside (Cloudflare). The Playwright fetch path exists but has an
unresolved prerequisite: it checks robots and rate-limits the initial
navigation URL, then delegates redirects and subresource loads to the
browser, where neither applies. It is also single-attempt, and
hard-codes `text/html`. Resolve before enabling any of these three —
one ~1-2 day fix unblocks all of them. See the workstream plan §5.

**Document shape.** Alameda ships scanned, *combined* PDF packets
needing OCR and segmentation. San Mateo has composite documents —
"Resolution, Full Text and Tax Rate Statement" is one PDF carrying
three roles, which breaks the one-document-one-role assumption in the
current model.

**Source timing.** Los Angeles publishes only at/after election day.
San Francisco's voter guide is in maintenance. Neither is a defect to
engineer around; both are calendar facts to wait out.

**Unfound pages.** San Diego's per-election measures listing has never
been located despite the polite UA defeating its 403.

**Maintenance, the real ceiling.** Drift has run ~1 event per county
per 2 weeks. The capture/interpretation decoupling (shipped
`edb2978`) removed the worst consequence — a new document type now
fails an offline parse instead of losing that week's capture — but
structural drift still reds the cron. See the workplan §5.

## Next actions

1. **Build San Mateo** — prompt at
   [`../codex/san_mateo_scraper_build.md`](../codex/san_mateo_scraper_build.md).
2. **Alameda** after it, accepting the OCR work.
3. **Re-probe San Francisco** once the voter guide returns.
4. **Resolve the Playwright per-hop politeness prerequisite** before
   Santa Clara, Contra Costa, or Riverside.
5. **Decide on Los Angeles separately** — archive value is real and
   large, but it is a different project from November coverage.
