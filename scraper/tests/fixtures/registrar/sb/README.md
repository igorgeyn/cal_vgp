# SB registrar fixtures

Live captures from `elections.sbcounty.gov` / `uploads.rov.sbcounty.gov`,
2026-07-09, polite UA (`cal-vgp-registrar-scraper/0.1`). Raw response
bytes preserved unchanged; each file has a `.meta.json` sidecar with
source/final URL, status, content type, ETag/Last-Modified, sha256,
capture time. Design: `docs/plans/registrar_phase1_sb.md`.

## Files

| File | What it is |
|---|---|
| `landing_measures.html` | Cross-election landing `/elections/measures/` — discovery input |
| `measures_2026_0324.html` | March 2026 measures page — **published state** (2 rows, all links live) |
| `measures_2026_1103.html` | Nov 2026 measures page — **announced state** (2 rows, zero links) |
| `pdf_res_v.pdf` | Measure V resolution (Jurisdiction-cell link, `RES_*`) |
| `pdf_ord_v.pdf` | Measure V ordinance = full measure text (Description-cell link, `ORD_*`) |
| `pdf_ia_v.pdf` | Measure V impartial analysis (`IA_*`) |
| `pdf_af_v.pdf` / `pdf_raf_v.pdf` | Argument For / Rebuttal to Argument For (`AF_*` / `RAF_*`) |
| `pdf_aa_v.pdf` / `pdf_raa_v.pdf` | Argument Against / Rebuttal to Argument Against (`AA_*` / `RAA_*`) |

## Fixture facts (supersede recon assumptions)

1. **Table shape confirmed** — one `<table class="table striped">`, no
   `<thead>`; header row is `<th>` cells inside the first `<tbody>`
   `<tr>`. Headers exactly: `Letter | Jurisdiction | Measure
   Description | Analysis | Arguments | Percentage<br/>to Pass` —
   note the `<br/>` inside the last header; normalization must
   collapse internal whitespace/line breaks.
2. **Seven PDF roles, not five.** Published rows link from EVERY
   cell: Jurisdiction → `RES_*.pdf` (resolution), Measure
   Description → `ORD_*.pdf` (ordinance/full text), Analysis →
   `IA_*.pdf` (label "Impartial"), Arguments list → `AF_/RAF_/AA_/RAA_`
   (labels "Argument For", "Rebuttal to Argument For", "Argument
   Against", "Rebuttal to Argument Against"). Role is by COLUMN for
   jurisdiction/description (their link labels are variable text)
   and by LABEL within the Arguments list.
3. **All PDFs are off-origin** — hosted on
   `uploads.rov.sbcounty.gov` (absolute HTTPS URLs), pattern
   `/ROV/Elections/{yyyy}/{mmdd}/Measures/{JurisdictionSlug}/{internal-id}/{ROLE}_{JurisdictionSlug}.pdf`.
   Off-origin is the NORM, not the exception. Content-Type is a
   clean `application/pdf`; all bodies start `%PDF-`.
4. **"Announced" page state exists** (the 1103 fixture): rows
   present with Letter "TBD", NO links anywhere — Analysis cell is
   plain text "Impartial", Arguments cell is prose ("Contact the …
   City Clerk's Office for argument filing deadlines."). Expected
   documents must be defined as *cells containing links*; text-only
   cells = announced-not-published = zero expected docs, NOT a
   schema failure. A valid snapshot of this page has
   `pdf_counts {expected: 0, saved: 0}` with `table_row_count: 2`.
5. **Encoding hazard** — the 1103 page declares UTF-8 but contains
   at least one non-UTF-8 byte (Windows-1252 apostrophe in the
   clerk prose). Parse with tolerant decoding; raw artifact bytes
   stay pristine regardless.
6. **Landing/discovery** — exactly ONE canonical
   `/elections/{yyyy}/{mmdd}/measures/` link on the landing page
   today (2026/1103). Other elections are linked WITHOUT the
   `/measures/` suffix (`/elections/2026/0324`, `/Elections/2026/0602/`
   — note case variance). Strict-shape discovery therefore yields
   the next big election; past elections enter via anchors/backfill.
7. **Watch-item #1 resolved for the observed case**: the county
   links a measures page ~4 months early, but the page EXISTS (200,
   announced state) — no linked-but-404 observed. Discovery
   criterion 4 works as designed for this case.
