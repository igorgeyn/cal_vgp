# San Mateo registrar fixtures

Live captures from `smcacre.gov`, 2026-08-31 Pacific time, using the
project-identifying `cal-vgp-registrar-scraper/0.1` User-Agent. Raw response
bytes are unchanged. Every artifact has a `.meta.json` sidecar containing its
source/final URL, response metadata, checksum, capture time, and User-Agent.

## Files

| File | What it is |
|---|---|
| `election_2026_1103.html` | Live November 3, 2026 election page: 29 measure panels in four measure-group accordions |
| `past_elections_results.html` | Archive/index used to discover dated election-information pages |
| `pdf_resolution_text_tax_r.pdf` | Measure R's scanned 12-page composite packet |
| `pdf_resolution_text_g.pdf` | Measure G's text-layer 13-page composite packet |

## Fixture facts

1. The page contains four measure-group headings immediately followed by an
   `<smc-accordion>`: County Measures (4 panels / 9 document links), Regional
   Measure (1 / 6), School District Measures (7 / 35), and City Measures
   (17 / 85). Each owned
   `<smc-accordion-panel>` is one measure. Non-measure PDFs elsewhere on the
   page are outside these four accordions.
2. The 29 panels contain exactly 135 measure-document links. Normalized label
   census: 29 `Impartial Analysis`; 26 `Primary Argument in Favor`; 24
   `Resolution and Full Text`; 18 `Primary Argument Against`; 17 `Rebuttal to
   Argument Against`; 16 `Rebuttal to Argument in Favor`; 4 `Resolution, Full
   Text and Tax Rate Statement`; and 1 `Resolution`.
3. Label spelling is not byte-stable. The fixture contains `Primary Argument
   In Favor`, non-breaking spaces in two labels, and extra whitespace in a
   measure heading. Interpretation must normalize case and whitespace.
4. Document links are same-origin `/archival-document` wrappers. Their
   `document` query parameter is the authoritative HTTPS PDF URL; fetching the
   wrapper itself returns HTML, not the PDF artifact.
5. The composite labels describe real packet contents, not shorthand for a
   single role. In the pinned Measure R bytes, pages 1-6 are the resolution,
   pages 7-11 contain the full bond proposition, and page 12 is headed `TAX
   RATE STATEMENT`. Measure G contains a resolution followed by `Exhibit A -
   Ordinance - Full Text Measure`. One captured PDF therefore supplies two or
   three semantic roles during offline interpretation.
6. The four county charter measures share the same source PDF. Capture still
   records one neutral artifact per panel/link because snapshot filenames are
   row-owned and immutable; source-URL equality must not collapse measures.
7. Approval labels are 21 majority, 5 two-thirds, and 3 at 55 percent.
8. The archive index does not list the still-upcoming November election. Its
   newest election-information link is June 2, 2026. Forward coverage therefore
   needs a versioned active anchor; the index provides historical discovery,
   not proof that a forward anchor still exists.
