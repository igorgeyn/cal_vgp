"""
San Bernardino County registrar scraper — the first real county.

Capture and interpretation are deliberately separate:

- Pure capture extraction (no network/storage/clock/role knowledge):
  `extract_measures_page` records every table link with its row,
  column, label, URL, and neutral filename. Offline role assignment
  lives in `sb_interpretation.py` and is called only by the parser.
- `extract_discovery_candidates` turns the cross-election landing
  page into candidate election dates.
- `SbScraper(CountyRegistrarScraper)`: hybrid enumeration (static
  anchors as the coverage contract + weekly discovery), per-election
  scrape via base-class primitives only, manifest-last snapshots
  with SB audit extras.

Page states the capture layer recognizes (fixture facts):
- PUBLISHED: table cells link documents. Capture records every link;
  the offline interpreter currently recognizes up to nine roles.
- ANNOUNCED: rows exist (letters may be "TBD") but carry no links;
  a valid zero-expected-documents observation, not a failure.
- Mixed rows are handled per cell; expected documents are exactly
  the links the current page advertises. A formerly linked document
  disappearing is an observed retraction, not a scraper failure
  (Codex round-5).

Anchor lifecycle (Codex round-5 blocker fix): anchors are active
while election_date >= as_of_date in America/Los_Angeles; discovery
must contain every ACTIVE anchor; past anchors retire automatically;
no active anchors + no forward candidates = successful idle run.
"""
from __future__ import annotations

import re
from datetime import date, timezone
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .base import CountyRegistrarScraper, ScraperError, ScrapeResult
from .contracts import CapturedDocument, CapturedMeasureRow, CapturedMeasuresPage

LA_TZ = ZoneInfo("America/Los_Angeles")

SB_HOST = "elections.sbcounty.gov"
SB_BASE_URL = f"https://{SB_HOST}"
LANDING_URL = f"{SB_BASE_URL}/elections/measures/"

# Static coverage contract (reviewed, versioned). Anchors retire
# automatically once their date passes in LA time; pruning entries
# from this tuple is cosmetic housekeeping, not correctness.
SB_FORWARD_ANCHORS: tuple[str, ...] = ("2026-11-03",)

# The full normalized header set that identifies THE measures table.
# Matching is by header name (never column position); normalization
# collapses internal whitespace — the live "Percentage to Pass"
# header contains a <br/>.
EXPECTED_HEADERS = frozenset(
    {
        "letter",
        "jurisdiction",
        "measure description",
        "analysis",
        "arguments",
        "percentage to pass",
    }
)

_CANDIDATE_PATH = re.compile(r"^/elections/(\d{4})/(\d{4})/measures/?$", re.I)
_SAFE_FILENAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class SbSchemaError(ScraperError):
    """The page violated the SB measures-table contract. Signals
    site drift: pin a new fixture and revise deliberately."""


class SbEnumerationError(ScraperError):
    """Election discovery violated the coverage contract (empty
    discovery or a missing active anchor)."""


def _norm_text(node_or_text) -> str:
    text = (
        node_or_text
        if isinstance(node_or_text, str)
        else node_or_text.get_text(" ", strip=True)
    )
    return re.sub(r"\s+", " ", text).strip()


def _soup(body: bytes) -> BeautifulSoup:
    # Fixtures are valid strict UTF-8; tolerant decode is defensive
    # only (raw bytes stay pristine in the artifact regardless).
    return BeautifulSoup(body.decode("utf-8", errors="replace"), "lxml")


def _resolve_document_url(href: str, page_url: str, context: str) -> str:
    resolved = urljoin(page_url, href.strip())
    parsed = urlparse(resolved)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SbSchemaError(
            f"document link is not absolute HTTPS ({context}): {href!r}"
        )
    return resolved


def _column_slug(column: str) -> str:
    slug = "-".join(re.findall(r"[a-z0-9]+", column.casefold()))
    if not slug:
        raise SbSchemaError(f"column header yields empty filename slug: {column!r}")
    return slug


# --- ownership-scoped traversal (Codex round-6) -----------------------
# All row/cell/link scans consider only nodes whose NEAREST ancestor
# table is the selected measures table. Without this, a nested table
# (or a future <th scope="row"> accessibility change) could silently
# drop measure rows — and zero rows is a VALID state, so the failure
# mode was a silently empty published snapshot.


def _owned_rows(table) -> list:
    return [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]


def _direct_cells(tr) -> list:
    return tr.find_all(["th", "td"], recursive=False)


def _owned_links(cell, table) -> list:
    return [
        a
        for a in cell.find_all("a", href=True)
        if a.find_parent("table") is table
    ]


def _find_header_row(table):
    """First owned row whose direct cells are all <th>. Returns
    (row, normalized_headers) or (None, ())."""
    for tr in _owned_rows(table):
        cells = _direct_cells(tr)
        if cells and all(c.name == "th" for c in cells):
            return tr, tuple(_norm_text(c).lower() for c in cells)
    return None, ()


def extract_measures_page(body: bytes, page_url: str) -> CapturedMeasuresPage:
    """Capture every link in the identified SB measures table.

    Contract (fixture-driven, Codex rounds 4-5):
    - exactly ONE table matches the full normalized header set;
    - columns map by header name, order irrelevant;
    - zero data rows is valid (unpublished-late pages);
    - expected documents are exactly ALL LINKS in the identified
      table's cells, with no role, label, or cardinality decisions;
    - links outside the measures table (nav, resource sidebars) are
      ignored entirely.
    """
    soup = _soup(body)

    matches = []
    for table in soup.find_all("table"):
        header_row, headers = _find_header_row(table)
        if (
            header_row is not None
            and len(headers) == len(EXPECTED_HEADERS)
            and set(headers) == EXPECTED_HEADERS
        ):
            matches.append((table, header_row, headers))

    if len(matches) != 1:
        raise SbSchemaError(
            f"expected exactly 1 measures table with headers "
            f"{sorted(EXPECTED_HEADERS)}, found {len(matches)}"
        )
    table, header_row, headers = matches[0]
    col = {name: i for i, name in enumerate(headers)}

    owned = _owned_rows(table)
    header_index = owned.index(header_row)
    # Fail loud, not silent: content rows BEFORE the header row are
    # out of contract (we would otherwise ignore them).
    for tr in owned[:header_index]:
        if _direct_cells(tr):
            raise SbSchemaError("unexpected content row before the header row")

    raw_rows = []
    for tr in owned[header_index + 1:]:
        # Direct th OR td: tolerates a future <th scope="row"> letter
        # cell. Only the recognized header row is skipped — never a
        # data row that happens to contain a descendant <th>.
        cells = _direct_cells(tr)
        if not cells:
            continue
        if len(cells) != len(headers):
            raise SbSchemaError(
                f"malformed row: {len(cells)} cells, expected {len(headers)}"
            )
        raw_rows.append(cells)

    rows: list[CapturedMeasureRow] = []
    all_docs: list[CapturedDocument] = []
    for idx, cells in enumerate(raw_rows, start=1):
        letter = _norm_text(cells[col["letter"]])
        docs: list[CapturedDocument] = []
        for column_index, col_name in enumerate(headers):
            for link_index, link in enumerate(
                _owned_links(cells[column_index], table), start=1
            ):
                url = _resolve_document_url(
                    link["href"], page_url, f"{col_name}, row {idx}"
                )
                docs.append(
                    CapturedDocument(
                        filename=(
                            f"row{idx:03d}_{_column_slug(col_name)}-cell_"
                            f"{link_index:02d}.pdf"
                        ),
                        url=url,
                        column=col_name,
                        label=_norm_text(link),
                        measure_letter=letter,
                        table_row=idx,
                    )
                )

        rows.append(
            CapturedMeasureRow(
                table_row=idx,
                letter=letter,
                jurisdiction=_norm_text(cells[col["jurisdiction"]]),
                description=_norm_text(cells[col["measure description"]]),
                percentage_to_pass=_norm_text(cells[col["percentage to pass"]]),
                documents=tuple(docs),
            )
        )
        all_docs.extend(docs)

    # Defensive invariants: names are storage-safe and unique by
    # construction; a violation is an extractor bug, surfaced loudly.
    names = [d.filename for d in all_docs]
    if len(names) != len(set(names)):
        raise SbSchemaError(f"internal error: duplicate filenames {names}")
    for n in names:
        if not _SAFE_FILENAME.match(n):
            raise SbSchemaError(f"internal error: unsafe filename {n!r}")

    return CapturedMeasuresPage(
        headers=headers,
        rows=tuple(rows),
        expected_documents=tuple(all_docs),
    )


def extract_discovery_candidates(body: bytes, page_url: str) -> tuple[date, ...]:
    """Pure discovery: canonical per-election measures URLs found
    ANYWHERE on the landing page (the live candidate link sits in
    duplicated site navigation, not the content table), deduplicated
    by election date, sorted ascending. Links that merely resemble
    the pattern but carry an invalid calendar date are skipped."""
    soup = _soup(body)
    found: set[date] = set()
    for link in soup.find_all("a", href=True):
        resolved = urljoin(page_url, link["href"].strip())
        parsed = urlparse(resolved)
        if parsed.scheme != "https" or parsed.netloc.lower() != SB_HOST:
            continue
        m = _CANDIDATE_PATH.match(parsed.path)
        if not m:
            continue
        year, mmdd = int(m.group(1)), m.group(2)
        try:
            found.add(date(year, int(mmdd[:2]), int(mmdd[2:])))
        except ValueError:
            continue
    return tuple(sorted(found))


def measures_url(d: date) -> str:
    return f"{SB_BASE_URL}/elections/{d.year}/{d:%m%d}/measures/"


class SbScraper(CountyRegistrarScraper):
    county = "sb"
    fetch_mode: str = "requests"
    version = "0.2.0"

    anchors: tuple[str, ...] = SB_FORWARD_ANCHORS

    def _as_of_date(self) -> date:
        now = self._clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.astimezone(LA_TZ).date()

    def scrape(self) -> ScrapeResult:
        as_of = self._as_of_date()
        active = tuple(
            d
            for d in (date.fromisoformat(a) for a in self.anchors)
            if d >= as_of
        )

        landing = self.fetch(LANDING_URL)
        discovered = extract_discovery_candidates(
            landing.body, landing.final_url
        )
        forward = tuple(d for d in discovered if d >= as_of)

        missing = sorted(set(active) - set(forward))
        if missing:
            raise SbEnumerationError(
                "discovery is missing active anchor(s) "
                f"{[d.isoformat() for d in missing]} "
                f"(discovered forward candidates: "
                f"{[d.isoformat() for d in forward]}). A changed index "
                "page must be visible, not silently incomplete."
            )

        if not active and not forward:
            # Successful idle: nothing to collect is a valid outcome
            # once all anchors have retired (Codex round-5).
            self._log.info(
                "idle run: no active anchors, no forward candidates "
                "(as of %s)", as_of.isoformat(),
            )
            return ScrapeResult(county=self.county)

        active_set = set(active)
        snapshots = []
        for d in sorted(set(forward) | active_set):
            provenance = (
                "anchor_and_discovered" if d in active_set else "discovered"
            )
            snapshots.append(self._scrape_election(d, provenance))
        return ScrapeResult(county=self.county, snapshots=tuple(snapshots))

    def _scrape_election(self, d: date, provenance: str):
        url = measures_url(d)
        page_fetch = self.fetch(url)
        # Round-6: validate the FULL final URL, not just the origin —
        # a same-origin redirect to another election's measures page
        # would otherwise be silently stored under the wrong date.
        final = urlparse(page_fetch.final_url)
        final_date = None
        m = _CANDIDATE_PATH.match(final.path or "")
        if m:
            try:
                mmdd = m.group(2)
                final_date = date(int(m.group(1)), int(mmdd[:2]), int(mmdd[2:]))
            except ValueError:
                final_date = None
        if (
            final.scheme != "https"
            or final.netloc.lower() != SB_HOST
            or final_date != d
        ):
            raise SbSchemaError(
                f"measures page for {d.isoformat()} ended off-origin or on "
                f"a different election: {page_fetch.final_url}"
            )

        writer = self.open_snapshot(d.isoformat())
        # page.html saved before structural validation: a schema
        # failure leaves an orphan diagnostic (invisible to parsers).
        writer.save("page.html", page_fetch)

        page = extract_measures_page(page_fetch.body, page_fetch.final_url)

        pdf_audit = []
        for doc in page.expected_documents:
            pdf = self.fetch(doc.url)
            # Round-6: cross-origin HTTPS redirects are fine (the
            # official page advertised the source), but a downgrade
            # to plain HTTP is never acceptable for saved documents.
            if urlparse(pdf.final_url).scheme != "https":
                raise SbSchemaError(
                    f"PDF fetch ended on a non-HTTPS URL (column {doc.column!r}, "
                    f"{doc.url} -> {pdf.final_url})"
                )
            content_type = pdf.content_type or ""
            if content_type != "application/pdf" and not pdf.body.startswith(
                b"%PDF-"
            ):
                raise SbSchemaError(
                    f"advertised PDF is not a PDF (column {doc.column!r}, "
                    f"{doc.url}): content-type {content_type!r}"
                )
            writer.save(doc.filename, pdf)
            # Audit map for the parser. Filenames are snapshot-local
            # storage keys; source_url is a continuity HINT across
            # snapshots, sha256 (in the artifact entry) identifies
            # exact bytes — neither is a measure identity. Lineage
            # is the parser's job (Codex round-6).
            pdf_audit.append(
                {
                    "filename": doc.filename,
                    "table_row": doc.table_row,
                    "measure_letter": doc.measure_letter,
                    "column": doc.column,
                    "label": doc.label,
                    "source_url": doc.url,
                }
            )

        writer.finalize(
            schema_version=2,
            extra={
                "source_base_url": SB_BASE_URL,
                "election_url": url,
                "discovery": {
                    "index_url": LANDING_URL,
                    "provenance": provenance,
                },
                "table_row_count": len(page.rows),
                "table_headers": list(page.headers),
                "pdf_counts": {
                    "expected": len(page.expected_documents),
                    "saved": len(pdf_audit),
                },
                "pdf_artifacts": pdf_audit,
            }
        )
        return writer.summary()
