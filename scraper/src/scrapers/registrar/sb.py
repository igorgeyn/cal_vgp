"""
San Bernardino County registrar scraper — the first real county.

Two layers, per docs/plans/registrar_phase1_sb.md:

- Pure extraction (no network/storage/clock): `extract_measures_page`
  turns raw page bytes into a typed page contract — normalized
  headers, rows, and expected-document descriptors with semantic
  filenames; `extract_discovery_candidates` turns the cross-election
  landing page into candidate election dates. Both are fixture-tested
  against pinned live captures in tests/fixtures/registrar/sb/.
- `SbScraper(CountyRegistrarScraper)`: hybrid enumeration (static
  anchors as the coverage contract + weekly discovery), per-election
  scrape via base-class primitives only, manifest-last snapshots
  with SB audit extras.

Page states the extractor recognizes (fixture facts):
- PUBLISHED: every cell links a PDF; seven roles per measure
  (resolution from the Jurisdiction cell, full text from the
  Description cell, analysis, and four argument variants by label).
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
from dataclasses import dataclass
from datetime import date, timezone
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .base import CountyRegistrarScraper, ScraperError, ScrapeResult

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

# Argument-cell link labels (normalized) → role. Unknown or
# duplicated labels are schema failures (complete-capture rule).
ARGUMENT_ROLES = {
    "argument for": "argument_for",
    "rebuttal to argument for": "rebuttal_for",
    "argument against": "argument_against",
    "rebuttal to argument against": "rebuttal_against",
}

# Single-link cells: role comes from the COLUMN (their link labels
# are variable text — jurisdiction name / measure title).
COLUMN_ROLES = {
    "jurisdiction": "resolution",
    "measure description": "text",
    "analysis": "analysis",
}

_CANDIDATE_PATH = re.compile(r"^/elections/(\d{4})/(\d{4})/measures/?$", re.I)
_SAFE_FILENAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class SbSchemaError(ScraperError):
    """The page violated the SB measures-table contract. Signals
    site drift: pin a new fixture and revise deliberately."""


class SbEnumerationError(ScraperError):
    """Election discovery violated the coverage contract (empty
    discovery or a missing active anchor)."""


@dataclass(frozen=True)
class ExpectedDocument:
    """One advertised PDF: where it lives and what to call it."""
    filename: str        # semantic, storage-safe
    url: str             # resolved absolute HTTPS
    role: str            # resolution|text|analysis|argument_*|rebuttal_*
    measure_letter: str  # raw Letter cell text (e.g. "V", "TBD")
    table_row: int       # 1-based data-row index


@dataclass(frozen=True)
class MeasureRow:
    table_row: int
    letter: str
    jurisdiction: str
    description: str
    percentage_to_pass: str
    documents: tuple[ExpectedDocument, ...]


@dataclass(frozen=True)
class MeasuresPage:
    headers: tuple[str, ...]          # normalized, table order
    rows: tuple[MeasureRow, ...]
    expected_documents: tuple[ExpectedDocument, ...]


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


def _letter_slug(letter: str) -> str:
    runs = re.findall(r"[a-z0-9]+", letter.lower())
    if not runs:
        raise SbSchemaError(f"letter cell yields empty slug: {letter!r}")
    return "_".join(runs)


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


def extract_measures_page(body: bytes, page_url: str) -> MeasuresPage:
    """Pure extraction of an SB measures page.

    Contract (fixture-driven, Codex rounds 4-5):
    - exactly ONE table matches the full normalized header set;
    - columns map by header name, order irrelevant;
    - zero data rows is valid (unpublished-late pages);
    - expected documents are exactly the LINKS in the identified
      table's cells: Jurisdiction/Description/Analysis carry zero or
      exactly one link each (more = schema failure); Arguments
      carries 0-4 uniquely labelled links; links elsewhere in the
      row (Letter / Percentage cells) are schema failures;
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

    # Collision rule: letters normally appear once; if slugs repeat,
    # every colliding row's filenames get a stable row suffix.
    slugs = [_letter_slug(_norm_text(c[col["letter"]])) for c in raw_rows]
    colliding = {s for s in slugs if slugs.count(s) > 1}

    rows: list[MeasureRow] = []
    all_docs: list[ExpectedDocument] = []
    for idx, cells in enumerate(raw_rows, start=1):
        letter = _norm_text(cells[col["letter"]])
        slug = slugs[idx - 1]
        stem = f"measure_{slug}_r{idx:03d}" if slug in colliding else f"measure_{slug}"

        # Letter / Percentage cells must not carry links at all —
        # a link we have no role for would violate complete capture.
        for plain_col in ("letter", "percentage to pass"):
            if _owned_links(cells[col[plain_col]], table):
                raise SbSchemaError(
                    f"unexpected link in {plain_col!r} cell (row {idx})"
                )

        docs: list[ExpectedDocument] = []

        # Single-link columns: zero or exactly one link, role by column.
        for col_name, role in COLUMN_ROLES.items():
            links = _owned_links(cells[col[col_name]], table)
            if len(links) > 1:
                raise SbSchemaError(
                    f"{col_name!r} cell has {len(links)} links (row {idx}); "
                    "zero or one allowed — never silently drop a document"
                )
            if links:
                url = _resolve_document_url(
                    links[0]["href"], page_url, f"{col_name}, row {idx}"
                )
                docs.append(
                    ExpectedDocument(
                        filename=f"{stem}_{role}.pdf",
                        url=url,
                        role=role,
                        measure_letter=letter,
                        table_row=idx,
                    )
                )

        # Arguments: 0-4 links, role by unique label.
        seen_labels: set[str] = set()
        for link in _owned_links(cells[col["arguments"]], table):
            label = _norm_text(link).lower()
            role = ARGUMENT_ROLES.get(label)
            if role is None:
                raise SbSchemaError(
                    f"unknown argument link label {label!r} (row {idx})"
                )
            if label in seen_labels:
                raise SbSchemaError(
                    f"duplicate argument link label {label!r} (row {idx})"
                )
            seen_labels.add(label)
            url = _resolve_document_url(
                link["href"], page_url, f"arguments, row {idx}"
            )
            docs.append(
                ExpectedDocument(
                    filename=f"{stem}_{role}.pdf",
                    url=url,
                    role=role,
                    measure_letter=letter,
                    table_row=idx,
                )
            )

        rows.append(
            MeasureRow(
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

    return MeasuresPage(
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
    version = "0.1.0"

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
                    f"PDF fetch ended on a non-HTTPS URL (role {doc.role}, "
                    f"{doc.url} -> {pdf.final_url})"
                )
            content_type = pdf.content_type or ""
            if content_type != "application/pdf" and not pdf.body.startswith(
                b"%PDF-"
            ):
                raise SbSchemaError(
                    f"advertised PDF is not a PDF (role {doc.role}, "
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
                    "role": doc.role,
                    "source_url": doc.url,
                }
            )

        writer.finalize(
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
