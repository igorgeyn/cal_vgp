"""San Mateo County registrar capture adapter.

The live page is not tabular.  Four named measure sections each own one
``<smc-accordion>`` and every direct ``<smc-accordion-panel>`` is a measure.
Capture records every link owned by those panels without assigning roles;
``smc_interpretation`` performs strict label-based role assignment offline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timezone
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .base import CountyRegistrarScraper, ScraperError, ScrapeResult


LA_TZ = ZoneInfo("America/Los_Angeles")
SMC_HOST = "smcacre.gov"
SMC_BASE_URL = f"https://{SMC_HOST}"
INDEX_URL = f"{SMC_BASE_URL}/elections/past-elections-results"
NOVEMBER_2026_URL = (
    f"{SMC_BASE_URL}/elections/november-3-2026-statewide-general-election"
)

# The archive index does not list elections until they are past.  Forward
# anchors are therefore the reviewed coverage contract; the index adds dated
# historical/future candidates when they appear, but cannot validate an active
# anchor's presence (fixture fact 8).
SMC_FORWARD_ANCHORS: tuple[tuple[str, str], ...] = (
    ("2026-11-03", NOVEMBER_2026_URL),
)

EXPECTED_GROUPS = (
    "county measures",
    "regional measure",
    "school district measures",
    "city measures",
)

_MONTHS = {
    name.casefold(): number
    for number, name in enumerate(
        (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ),
        start=1,
    )
}
_ELECTION_PATH = re.compile(
    r"^/elections/([a-z]+)-(\d{1,2})-(\d{4})-(.+)$",
    re.I,
)
_MEASURE_HEADING = re.compile(r"^Measure\s+([A-Z]+)$", re.I)
_SAFE_FILENAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class SmcSchemaError(ScraperError):
    """The page violated San Mateo's structural capture contract."""


class SmcEnumerationError(ScraperError):
    """The election index contained ambiguous or invalid candidates."""


@dataclass(frozen=True)
class ElectionCandidate:
    election_date: date
    url: str


@dataclass(frozen=True)
class CapturedDocument:
    filename: str
    url: str
    column: str          # owning measure-group heading (audit context)
    label: str
    measure_letter: str
    table_row: int       # shared parser name; 1-based measure-panel index


@dataclass(frozen=True)
class CapturedMeasureRow:
    table_row: int
    letter: str
    jurisdiction: str
    description: str
    percentage_to_pass: str
    documents: tuple[CapturedDocument, ...]


@dataclass(frozen=True)
class CapturedMeasuresPage:
    # The shared manifest field is named table_headers for schema compatibility;
    # San Mateo stores its ordered measure-group headings here.
    headers: tuple[str, ...]
    rows: tuple[CapturedMeasureRow, ...]
    expected_documents: tuple[CapturedDocument, ...]


def _norm_text(node_or_text) -> str:
    text = (
        node_or_text
        if isinstance(node_or_text, str)
        else node_or_text.get_text(" ", strip=True)
    )
    return re.sub(r"\s+", " ", text).strip()


def _soup(body: bytes) -> BeautifulSoup:
    return BeautifulSoup(body.decode("utf-8", errors="replace"), "lxml")


def _parse_election_path(url: str) -> date | None:
    parsed = urlparse(url)
    match = _ELECTION_PATH.fullmatch(parsed.path.rstrip("/"))
    if not match:
        return None
    month_name, day_raw, year_raw, suffix = match.groups()
    # Results/news are not election-information pages.
    if suffix.casefold().endswith("election-results"):
        return None
    month = _MONTHS.get(month_name.casefold())
    if month is None:
        return None
    try:
        return date(int(year_raw), month, int(day_raw))
    except ValueError:
        return None


def extract_discovery_candidates(body: bytes, page_url: str) -> tuple[ElectionCandidate, ...]:
    """Extract unique same-origin ``Election Information`` destinations.

    The live Drupal page duplicates several link blocks. Identical duplicates
    are collapsed, while two distinct information URLs for one date are an
    ambiguity and fail rather than being selected by document order.
    """
    soup = _soup(body)
    by_date: dict[date, set[str]] = {}
    for link in soup.find_all("a", href=True):
        if _norm_text(link).casefold() != "election information":
            continue
        resolved = urljoin(page_url, link["href"].strip())
        parsed = urlparse(resolved)
        if parsed.scheme != "https" or parsed.netloc.casefold() != SMC_HOST:
            continue
        election_date = _parse_election_path(resolved)
        if election_date is None:
            continue
        canonical = resolved.rstrip("/")
        by_date.setdefault(election_date, set()).add(canonical)

    ambiguous = {d: sorted(urls) for d, urls in by_date.items() if len(urls) != 1}
    if ambiguous:
        raise SmcEnumerationError(
            f"multiple election-information URLs for one date: {ambiguous}"
        )
    return tuple(
        ElectionCandidate(d, next(iter(urls)))
        for d, urls in sorted(by_date.items())
    )


def _owned_panels(accordion) -> list:
    return [
        panel
        for panel in accordion.find_all("smc-accordion-panel")
        if panel.find_parent("smc-accordion") is accordion
    ]


def _owned_links(panel) -> list:
    return [
        link
        for link in panel.find_all("a", href=True)
        if link.find_parent("smc-accordion-panel") is panel
    ]


def _find_measure_groups(soup: BeautifulSoup) -> tuple[tuple[str, object], ...]:
    found: dict[str, list] = {group: [] for group in EXPECTED_GROUPS}
    for container in soup.find_all("outline-container"):
        headings = container.find_all("h3")
        if len(headings) != 1:
            continue
        group = _norm_text(headings[0]).casefold()
        if group not in found:
            continue
        sibling = container.find_next_sibling()
        if sibling is None or sibling.name != "smc-accordion":
            raise SmcSchemaError(
                f"measure-group heading {group!r} is not immediately followed "
                "by an <smc-accordion>"
            )
        found[group].append(sibling)

    bad = {group: len(items) for group, items in found.items() if len(items) != 1}
    if bad:
        raise SmcSchemaError(
            "expected exactly one accordion for each measure group; "
            f"violations={bad}"
        )
    return tuple((group, found[group][0]) for group in EXPECTED_GROUPS)


def _split_heading(group: str, heading: str, row_number: int) -> tuple[str, str, str]:
    pieces = re.split(r"\s+[\u2013\u2014-]\s+", heading, maxsplit=1)
    if len(pieces) != 2:
        raise SmcSchemaError(
            f"malformed measure heading in panel {row_number}: {heading!r}"
        )
    designation, remainder = pieces
    match = _MEASURE_HEADING.fullmatch(designation)
    if match:
        letter = match.group(1).upper()
    elif group == "regional measure" and designation.casefold() == "regional transit measure":
        # This four-county measure has a name but no alphanumeric designation.
        letter = "Regional Transit"
    else:
        raise SmcSchemaError(
            f"unknown measure designation in panel {row_number}: {designation!r}"
        )

    if group == "county measures":
        prefix = "San Mateo County "
        if not remainder.casefold().startswith(prefix.casefold()):
            raise SmcSchemaError(
                f"county measure panel {row_number} lacks {prefix!r}: {heading!r}"
            )
        jurisdiction = "San Mateo County"
        description = remainder[len(prefix):].strip()
    else:
        jurisdiction, separator, description = remainder.partition(":")
        if not separator:
            raise SmcSchemaError(
                f"measure panel {row_number} lacks jurisdiction separator: {heading!r}"
            )
        jurisdiction, description = jurisdiction.strip(), description.strip()

    if not jurisdiction or not description:
        raise SmcSchemaError(
            f"measure panel {row_number} has empty jurisdiction/description"
        )
    return letter, jurisdiction, description


_THRESHOLDS = {
    "majority voter approval required": "50% + 1",
    "2/3 voter approval required": "2/3",
    "55% voter approval required": "55%",
}


def _panel_threshold(panel, row_number: int) -> str:
    matches = [
        _THRESHOLDS[text.casefold()]
        for paragraph in panel.find_all("p")
        if paragraph.find_parent("smc-accordion-panel") is panel
        for text in [_norm_text(paragraph)]
        if text.casefold() in _THRESHOLDS
    ]
    if len(matches) != 1:
        raise SmcSchemaError(
            f"measure panel {row_number} has {len(matches)} recognized approval labels"
        )
    return matches[0]


def _document_url(href: str, page_url: str, row_number: int) -> str:
    wrapper = urlparse(urljoin(page_url, href.strip()))
    if (
        wrapper.scheme != "https"
        or wrapper.netloc.casefold() != SMC_HOST
        or wrapper.path.rstrip("/") != "/archival-document"
    ):
        raise SmcSchemaError(
            f"document link in panel {row_number} is not an SMC archival wrapper: {href!r}"
        )
    values = parse_qs(wrapper.query, keep_blank_values=True).get("document", [])
    if len(values) != 1:
        raise SmcSchemaError(
            f"document wrapper in panel {row_number} has {len(values)} document targets"
        )
    source = values[0]
    parsed = urlparse(source)
    if (
        parsed.scheme != "https"
        or parsed.netloc.casefold() != SMC_HOST
        or not parsed.path.casefold().endswith(".pdf")
    ):
        raise SmcSchemaError(
            f"document target in panel {row_number} is not a same-origin HTTPS PDF: {source!r}"
        )
    return source


def extract_measures_page(body: bytes, page_url: str) -> CapturedMeasuresPage:
    """Capture all and only links owned by the four measure accordions."""
    soup = _soup(body)
    groups = _find_measure_groups(soup)

    rows: list[CapturedMeasureRow] = []
    all_documents: list[CapturedDocument] = []
    for group, accordion in groups:
        for panel in _owned_panels(accordion):
            row_number = len(rows) + 1
            headings = [
                heading
                for heading in panel.find_all(attrs={"slot": "heading"})
                if heading.find_parent("smc-accordion-panel") is panel
            ]
            if len(headings) != 1:
                raise SmcSchemaError(
                    f"measure panel {row_number} has {len(headings)} owned headings"
                )
            letter, jurisdiction, description = _split_heading(
                group, _norm_text(headings[0]), row_number
            )
            threshold = _panel_threshold(panel, row_number)
            documents: list[CapturedDocument] = []
            for link_number, link in enumerate(_owned_links(panel), start=1):
                documents.append(
                    CapturedDocument(
                        filename=f"row{row_number:03d}_link_{link_number:02d}.pdf",
                        url=_document_url(link["href"], page_url, row_number),
                        column=group,
                        label=_norm_text(link),
                        measure_letter=letter,
                        table_row=row_number,
                    )
                )
            row = CapturedMeasureRow(
                table_row=row_number,
                letter=letter,
                jurisdiction=jurisdiction,
                description=description,
                percentage_to_pass=threshold,
                documents=tuple(documents),
            )
            rows.append(row)
            all_documents.extend(documents)

    if not rows:
        raise SmcSchemaError("measure accordions contain zero owned panels")
    filenames = [document.filename for document in all_documents]
    if len(filenames) != len(set(filenames)):
        raise SmcSchemaError(f"internal error: duplicate filenames {filenames}")
    if any(not _SAFE_FILENAME.fullmatch(name) for name in filenames):
        raise SmcSchemaError(f"internal error: unsafe filename in {filenames}")
    return CapturedMeasuresPage(
        headers=tuple(group for group, _ in groups),
        rows=tuple(rows),
        expected_documents=tuple(all_documents),
    )


class SmcScraper(CountyRegistrarScraper):
    county = "smc"
    fetch_mode = "requests"
    version = "0.1.0"

    anchors: tuple[tuple[str, str], ...] = SMC_FORWARD_ANCHORS

    def _as_of_date(self) -> date:
        now = self._clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.astimezone(LA_TZ).date()

    def scrape(self) -> ScrapeResult:
        as_of = self._as_of_date()
        active = {
            date.fromisoformat(raw_date): url
            for raw_date, url in self.anchors
            if date.fromisoformat(raw_date) >= as_of
        }

        index_fetch = self.fetch(INDEX_URL)
        final_index = urlparse(index_fetch.final_url)
        if (
            final_index.scheme != "https"
            or final_index.netloc.casefold() != SMC_HOST
            or final_index.path.rstrip("/") != "/elections/past-elections-results"
        ):
            raise SmcEnumerationError(
                f"election index redirected off contract: {index_fetch.final_url}"
            )
        discovered = {
            candidate.election_date: candidate.url
            for candidate in extract_discovery_candidates(
                index_fetch.body, index_fetch.final_url
            )
            if candidate.election_date >= as_of
        }

        for election_date in set(active) & set(discovered):
            if active[election_date].rstrip("/") != discovered[election_date].rstrip("/"):
                raise SmcEnumerationError(
                    f"anchor/discovery URL conflict for {election_date}: "
                    f"{active[election_date]!r} != {discovered[election_date]!r}"
                )

        candidates = {**discovered, **active}
        if not candidates:
            self._log.info("idle run: no active anchors or forward index candidates")
            return ScrapeResult(county=self.county)

        snapshots = []
        for election_date, url in sorted(candidates.items()):
            provenance = (
                "anchor_and_discovered"
                if election_date in active and election_date in discovered
                else "anchor"
                if election_date in active
                else "discovered"
            )
            snapshots.append(self._scrape_election(election_date, url, provenance))
        return ScrapeResult(county=self.county, snapshots=tuple(snapshots))

    def _scrape_election(self, election_date: date, url: str, provenance: str):
        page_fetch = self.fetch(url)
        final = urlparse(page_fetch.final_url)
        if (
            final.scheme != "https"
            or final.netloc.casefold() != SMC_HOST
            or _parse_election_path(page_fetch.final_url) != election_date
            or final.path.rstrip("/") != urlparse(url).path.rstrip("/")
        ):
            raise SmcSchemaError(
                f"election page for {election_date} ended off-origin or on a "
                f"different election: {page_fetch.final_url}"
            )

        writer = self.open_snapshot(election_date.isoformat())
        writer.save("page.html", page_fetch)
        page = extract_measures_page(page_fetch.body, page_fetch.final_url)

        pdf_audit = []
        for document in page.expected_documents:
            pdf = self.fetch(document.url)
            final_pdf = urlparse(pdf.final_url)
            if final_pdf.scheme != "https" or final_pdf.netloc.casefold() != SMC_HOST:
                raise SmcSchemaError(
                    f"PDF fetch redirected off-origin ({document.label!r}, "
                    f"{document.url} -> {pdf.final_url})"
                )
            content_type = pdf.content_type or ""
            if content_type != "application/pdf" and not pdf.body.startswith(b"%PDF-"):
                raise SmcSchemaError(
                    f"advertised document is not a PDF ({document.label!r}, "
                    f"{document.url}): content-type {content_type!r}"
                )
            writer.save(document.filename, pdf)
            pdf_audit.append(
                {
                    "filename": document.filename,
                    "table_row": document.table_row,
                    "measure_letter": document.measure_letter,
                    "column": document.column,
                    "label": document.label,
                    "source_url": document.url,
                }
            )

        writer.finalize(
            schema_version=2,
            extra={
                "source_base_url": SMC_BASE_URL,
                "election_url": url,
                "discovery": {"index_url": INDEX_URL, "provenance": provenance},
                "table_row_count": len(page.rows),
                "table_headers": list(page.headers),
                "pdf_counts": {
                    "expected": len(page.expected_documents),
                    "saved": len(pdf_audit),
                },
                "pdf_artifacts": pdf_audit,
            },
        )
        return writer.summary()
