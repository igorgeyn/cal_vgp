"""Tests for the San Bernardino scraper: pure extraction against
pinned live fixtures, synthetic schema-failure cases, anchor
lifecycle (clock-controlled), and fixture-session integration."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.scrapers.registrar.base import ScraperError
from src.scrapers.registrar.sb import (
    LANDING_URL,
    SbEnumerationError,
    SbSchemaError,
    SbScraper,
    extract_discovery_candidates,
    extract_measures_page,
    measures_url,
)
from src.scrapers.registrar.storage import LocalArtifactStore

FIXTURES = Path(__file__).parent / "fixtures" / "registrar" / "sb"

URL_0324 = "https://elections.sbcounty.gov/elections/2026/0324/measures/"
URL_1103 = "https://elections.sbcounty.gov/elections/2026/1103/measures/"

ALL_ROLES = (
    "resolution",
    "text",
    "analysis",
    "argument_for",
    "rebuttal_for",
    "argument_against",
    "rebuttal_against",
)


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# ---------------------------------------------------------------- fakes


class FakeResponse:
    def __init__(self, status_code=200, content=b"", headers=None, url=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers if headers is not None else {"Content-Type": "text/html"}
        self.url = url or ""

    @property
    def text(self):
        return self.content.decode("utf-8", errors="replace")


class FakeSession:
    """Scripted session; unscripted URLs 404 (robots default-allow)."""

    def __init__(self, responses=None):
        self.responses = dict(responses or {})
        self.calls: list[str] = []

    def get(self, url, headers=None, timeout=None, allow_redirects=True):
        self.calls.append(url)
        queue = self.responses.get(url)
        if not queue:
            return FakeResponse(status_code=404, url=url)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if not item.url:
            item.url = url
        return item


JULY = datetime(2026, 7, 27, 18, 0, 0, tzinfo=timezone.utc)  # LA: Jul 27


def make_sb(store, responses, when=JULY, anchors=None):
    scraper = SbScraper(
        store,
        run_id="testrun",
        clock=lambda: when,
        session=FakeSession(responses),
        sleep=lambda s: None,
    )
    if anchors is not None:
        scraper.anchors = anchors
    return scraper


@pytest.fixture
def store(tmp_path) -> LocalArtifactStore:
    return LocalArtifactStore(base_dir=tmp_path, env="dev")


def html_response(body: bytes, url: str) -> FakeResponse:
    return FakeResponse(
        content=body, headers={"Content-Type": "text/html; charset=UTF-8"}, url=url
    )


def pdf_response(url: str) -> FakeResponse:
    return FakeResponse(
        content=b"%PDF-1.4\nfake\n%%EOF",
        headers={"Content-Type": "application/pdf"},
        url=url,
    )


# ---------------------------------------------------------------- extraction: fixtures


def test_extract_published_page_all_seven_roles():
    page = extract_measures_page(fixture_bytes("measures_2026_0324.html"), URL_0324)

    assert page.headers == (
        "letter",
        "jurisdiction",
        "measure description",
        "analysis",
        "arguments",
        "percentage to pass",
    )
    assert [r.letter for r in page.rows] == ["V", "W"]
    assert all(r.jurisdiction == "City of Ontario" for r in page.rows)
    assert all(r.percentage_to_pass == "50% + 1" for r in page.rows)

    assert len(page.expected_documents) == 14
    for letter in ("v", "w"):
        names = {
            d.filename for d in page.expected_documents
            if d.filename.startswith(f"measure_{letter}_")
        }
        assert names == {f"measure_{letter}_{role}.pdf" for role in ALL_ROLES}
    # Off-origin uploads host is the norm; every URL absolute HTTPS.
    for d in page.expected_documents:
        assert d.url.startswith("https://uploads.rov.sbcounty.gov/")


def test_extract_announced_page_zero_expected_documents():
    """TBD rows with no links = valid observation; the out-of-table
    Form 9600 resource link must NOT leak into expected documents."""
    page = extract_measures_page(fixture_bytes("measures_2026_1103.html"), URL_1103)

    assert len(page.rows) == 2
    assert [r.letter for r in page.rows] == ["TBD", "TBD"]
    assert {r.jurisdiction for r in page.rows} == {
        "City of Colton",
        "City of Highland",
    }
    assert page.expected_documents == ()


def test_extract_mixed_state_fixture_exact_contract():
    """The 2026-07-27 live page (pinned from the first production
    run): 8 rows, all letters still TBD (collision suffixes on every
    filename), 16 docs across mixed per-row publication states."""
    page = extract_measures_page(
        fixture_bytes("measures_2026_1103_mixed.html"), URL_1103
    )

    assert len(page.rows) == 8
    assert all(r.letter == "TBD" for r in page.rows)
    assert len(page.expected_documents) == 16

    pairs = [(d.table_row, d.role) for d in page.expected_documents]
    assert pairs == [
        (2, "resolution"),
        (3, "resolution"), (3, "text"), (3, "analysis"),
        (4, "resolution"), (4, "text"),
        (5, "resolution"), (5, "analysis"), (5, "argument_for"),
        (6, "resolution"), (6, "text"), (6, "analysis"), (6, "argument_for"),
        (7, "resolution"), (7, "text"), (7, "analysis"),
    ]
    names = [d.filename for d in page.expected_documents]
    assert all(n.startswith("measure_tbd_r") for n in names)
    assert len(names) == len(set(names))


def test_extract_lettered_fixture_with_tax_rate_statements():
    """The 2026-08-13 live page: letters assigned (no TBD, so no
    collision suffixes), 20 rows, and the Analysis cell carrying two
    document types — the drift that failed the Aug 10 cron."""
    page = extract_measures_page(
        fixture_bytes("measures_2026_1103_lettered.html"), URL_1103
    )

    assert len(page.rows) == 20
    letters = [r.letter for r in page.rows]
    assert "TBD" not in letters
    assert len(set(letters)) == 20  # unique → no r{NNN} suffixes
    assert all("_r0" not in d.filename for d in page.expected_documents)

    roles = Counter(d.role for d in page.expected_documents)
    assert roles["analysis"] == 8
    assert roles["tax_rate_statement"] == 6
    assert roles["resolution"] == 20
    assert roles["text"] == 19
    assert roles["argument_for"] == 3

    # Measure L (City of Needles, row 14) carries BOTH analysis docs.
    row14 = [d for d in page.expected_documents if d.table_row == 14]
    assert {d.role for d in row14} == {
        "resolution", "text", "analysis", "tax_rate_statement",
    }
    by_role = {d.role: d for d in row14}
    assert by_role["analysis"].filename == "measure_l_analysis.pdf"
    assert by_role["tax_rate_statement"].filename == (
        "measure_l_tax_rate_statement.pdf"
    )
    assert "/IA_" in by_role["analysis"].url
    assert "/TR_" in by_role["tax_rate_statement"].url

    # Every tax rate statement resolves to a TR_ document — proof the
    # label keying prevents the misattribution role-by-column allowed.
    for d in page.expected_documents:
        if d.role == "tax_rate_statement":
            assert "/TR_" in d.url
        if d.role == "analysis":
            assert "/IA_" in d.url


def test_tax_rate_statement_alone_is_not_an_analysis():
    """The silent-misattribution case: a row whose ONLY analysis-cell
    link is a Tax Rate Statement must not be filed as 'analysis'."""
    row = ROW_PUBLISHED.replace(
        '<td><a href="https://uploads.rov.sbcounty.gov/ia.pdf">Impartial</a></td>',
        '<td><a href="https://uploads.rov.sbcounty.gov/tr.pdf">'
        "Tax Rate Statement</a></td>",
    )
    page = extract_measures_page(table_html(HEADERS_OK, row), URL_1103)
    roles = {d.role for d in page.expected_documents}
    assert "tax_rate_statement" in roles
    assert "analysis" not in roles


def test_unknown_analysis_label_is_schema_failure():
    row = ROW_PUBLISHED.replace(">Impartial<", ">Fiscal Impact Summary<")
    with pytest.raises(SbSchemaError, match="unknown analysis link label"):
        extract_measures_page(table_html(HEADERS_OK, row), URL_1103)


def test_duplicate_analysis_label_is_schema_failure():
    row = ROW_PUBLISHED.replace(
        '<td><a href="https://uploads.rov.sbcounty.gov/ia.pdf">Impartial</a></td>',
        '<td><a href="https://uploads.rov.sbcounty.gov/ia.pdf">Impartial</a>'
        '<a href="https://uploads.rov.sbcounty.gov/ia2.pdf">Impartial</a></td>',
    )
    with pytest.raises(SbSchemaError, match="duplicate analysis link label"):
        extract_measures_page(table_html(HEADERS_OK, row), URL_1103)


def test_discovery_finds_single_deduped_candidate():
    """The landing page links 2026-11-03 from duplicated site nav;
    other elections are linked without the /measures/ suffix."""
    candidates = extract_discovery_candidates(
        fixture_bytes("landing_measures.html"), LANDING_URL
    )
    assert candidates == (date(2026, 11, 3),)


# ---------------------------------------------------------------- extraction: synthetic


def table_html(header_cells: str, body_rows: str) -> bytes:
    return (
        f"<html><body><table><tbody><tr>{header_cells}</tr>"
        f"{body_rows}</tbody></table></body></html>"
    ).encode("utf-8")


HEADERS_OK = (
    "<th>Letter</th><th>Jurisdiction</th><th>Measure Description</th>"
    "<th>Analysis</th><th>Arguments</th><th>Percentage<br/>to Pass</th>"
)

ROW_PUBLISHED = (
    '<tr><td>V</td>'
    '<td><a href="https://uploads.rov.sbcounty.gov/res.pdf">City of X</a></td>'
    '<td><a href="https://uploads.rov.sbcounty.gov/ord.pdf">Some Measure</a></td>'
    '<td><a href="https://uploads.rov.sbcounty.gov/ia.pdf">Impartial</a></td>'
    '<td><ul><li><a href="https://uploads.rov.sbcounty.gov/af.pdf">Argument For</a></li></ul></td>'
    '<td>50% + 1</td></tr>'
)


def test_synthetic_published_row_and_br_header():
    page = extract_measures_page(table_html(HEADERS_OK, ROW_PUBLISHED), URL_1103)
    assert len(page.rows) == 1
    assert {d.role for d in page.expected_documents} == {
        "resolution", "text", "analysis", "argument_for",
    }


def test_zero_data_rows_is_valid():
    page = extract_measures_page(table_html(HEADERS_OK, ""), URL_1103)
    assert page.rows == ()
    assert page.expected_documents == ()


def test_reordered_columns_map_by_header_name():
    headers = (
        "<th>Arguments</th><th>Letter</th><th>Percentage to Pass</th>"
        "<th>Jurisdiction</th><th>Analysis</th><th>Measure Description</th>"
    )
    row = (
        "<tr><td></td><td>Z</td><td>66.67%</td><td>County</td>"
        '<td><a href="https://uploads.rov.sbcounty.gov/ia.pdf">Impartial</a></td>'
        "<td>Desc</td></tr>"
    )
    page = extract_measures_page(table_html(headers, row), URL_1103)
    assert page.rows[0].letter == "Z"
    assert page.rows[0].percentage_to_pass == "66.67%"
    assert [d.role for d in page.expected_documents] == ["analysis"]


@pytest.mark.parametrize(
    "headers",
    [
        HEADERS_OK.replace("Analysis", "Analyses"),   # changed header
        HEADERS_OK.replace("<th>Analysis</th>", ""),  # missing header
        HEADERS_OK.replace(
            "<th>Analysis</th>", "<th>Analysis</th><th>Analysis</th>"
        ),                                            # duplicated header
    ],
)
def test_wrong_headers_reject_table(headers):
    with pytest.raises(SbSchemaError, match="exactly 1 measures table"):
        extract_measures_page(table_html(headers, ROW_PUBLISHED), URL_1103)


def test_two_matching_tables_is_schema_failure():
    one = table_html(HEADERS_OK, ROW_PUBLISHED).decode()
    two = one.replace("</body></html>", "") + one.split("<body>")[1]
    with pytest.raises(SbSchemaError, match="exactly 1 measures table"):
        extract_measures_page(two.encode(), URL_1103)


def test_malformed_row_cell_count():
    with pytest.raises(SbSchemaError, match="malformed row"):
        extract_measures_page(
            table_html(HEADERS_OK, "<tr><td>V</td><td>City</td></tr>"), URL_1103
        )


def test_two_links_in_single_link_cell_is_schema_failure():
    row = ROW_PUBLISHED.replace(
        '<td><a href="https://uploads.rov.sbcounty.gov/ord.pdf">Some Measure</a></td>',
        '<td><a href="https://uploads.rov.sbcounty.gov/ord.pdf">Some Measure</a>'
        '<a href="https://uploads.rov.sbcounty.gov/ord2.pdf">Amended</a></td>',
    )
    with pytest.raises(SbSchemaError, match="never silently drop"):
        extract_measures_page(table_html(HEADERS_OK, row), URL_1103)


def test_unknown_argument_label_is_schema_failure():
    row = ROW_PUBLISHED.replace(">Argument For<", ">Community Statement<")
    with pytest.raises(SbSchemaError, match="unknown arguments link label"):
        extract_measures_page(table_html(HEADERS_OK, row), URL_1103)


def test_duplicate_argument_label_is_schema_failure():
    row = ROW_PUBLISHED.replace(
        "</li></ul>",
        '</li><li><a href="https://uploads.rov.sbcounty.gov/af2.pdf">'
        "Argument For</a></li></ul>",
    )
    with pytest.raises(SbSchemaError, match="duplicate arguments link label"):
        extract_measures_page(table_html(HEADERS_OK, row), URL_1103)


def test_letter_cell_link_is_the_notice_of_election():
    """2026-08-24 drift: the Letter cell began carrying the official
    Notice of Election. The label is just the letter, so the role
    comes from the column."""
    row = ROW_PUBLISHED.replace(
        "<td>V</td>",
        '<td><a href="https://uploads.rov.sbcounty.gov/Notice_X.pdf">V</a></td>',
    )
    page = extract_measures_page(table_html(HEADERS_OK, row), URL_1103)
    notices = [d for d in page.expected_documents if d.role == "notice"]
    assert len(notices) == 1
    assert notices[0].filename == "measure_v_notice.pdf"
    assert notices[0].url.endswith("/Notice_X.pdf")


def test_two_links_in_letter_cell_is_schema_failure():
    """Cardinality still holds for the Letter cell."""
    row = ROW_PUBLISHED.replace(
        "<td>V</td>",
        '<td><a href="https://uploads.rov.sbcounty.gov/n1.pdf">V</a>'
        '<a href="https://uploads.rov.sbcounty.gov/n2.pdf">V</a></td>',
    )
    with pytest.raises(SbSchemaError, match="never silently drop"):
        extract_measures_page(table_html(HEADERS_OK, row), URL_1103)


def test_link_in_percentage_cell_is_schema_failure():
    """The Percentage cell still has no defined role for links."""
    row = ROW_PUBLISHED.replace(
        "<td>50% + 1</td>", '<td><a href="https://x.gov/p.pdf">50% + 1</a></td>'
    )
    with pytest.raises(SbSchemaError, match="unexpected link"):
        extract_measures_page(table_html(HEADERS_OK, row), URL_1103)


def test_extract_notice_era_fixture_contract():
    """The 2026-08-24 live page: nine roles in play, arguments now
    being filed as deadlines pass."""
    page = extract_measures_page(
        fixture_bytes("measures_2026_1103_notice.html"), URL_1103
    )
    assert len(page.rows) == 20
    roles = Counter(d.role for d in page.expected_documents)
    assert roles["notice"] == 7
    assert roles["resolution"] == 20
    assert roles["text"] == 19
    assert roles["analysis"] == 16
    assert roles["tax_rate_statement"] == 7
    assert roles["argument_for"] == 15
    assert roles["argument_against"] == 4
    assert sum(roles.values()) == 88
    # Roles come from the LINK LABEL, which is authoritative — not
    # from the county's URL naming, which is merely conventional.
    # Proof that this matters: SB City USD's "Impartial" link points
    # at AIF_SBCUSD.pdf (an argument-in-favor filename), so 15 of the
    # 16 analysis documents are IA_ and one is AIF_. Keying roles on
    # URL prefixes would have misfiled it. We record what the county
    # published and keep source_url so the anomaly stays auditable.
    prefixes = defaultdict(Counter)
    for d in page.expected_documents:
        prefixes[d.role][d.url.rsplit("/", 1)[-1].split("_")[0]] += 1
    assert dict(prefixes["analysis"]) == {"IA": 15, "AIF": 1}
    assert dict(prefixes["notice"]) == {"Notice": 7}
    assert dict(prefixes["tax_rate_statement"]) == {"TR": 7}
    assert dict(prefixes["resolution"]) == {"RES": 20}
    assert dict(prefixes["text"]) == {"FT": 19}


@pytest.mark.parametrize(
    "href",
    ["http://uploads.rov.sbcounty.gov/ia.pdf", "javascript:void(0)",
     "mailto:rov@sbcounty.gov", "data:text/html,hi"],
)
def test_non_https_document_links_rejected(href):
    row = ROW_PUBLISHED.replace("https://uploads.rov.sbcounty.gov/ia.pdf", href)
    with pytest.raises(SbSchemaError, match="not absolute HTTPS"):
        extract_measures_page(table_html(HEADERS_OK, row), URL_1103)


def test_relative_links_resolve_against_page_url():
    row = ROW_PUBLISHED.replace(
        "https://uploads.rov.sbcounty.gov/ia.pdf", "/docs/ia.pdf"
    )
    page = extract_measures_page(table_html(HEADERS_OK, row), URL_1103)
    analysis = [d for d in page.expected_documents if d.role == "analysis"][0]
    assert analysis.url == "https://elections.sbcounty.gov/docs/ia.pdf"


def test_duplicate_letters_get_row_suffixes():
    row2 = ROW_PUBLISHED.replace("<td>V</td>", "<td>V</td>", 1)
    page = extract_measures_page(
        table_html(HEADERS_OK, ROW_PUBLISHED + row2), URL_1103
    )
    names = [d.filename for d in page.expected_documents]
    assert "measure_v_r001_analysis.pdf" in names
    assert "measure_v_r002_analysis.pdf" in names
    assert len(names) == len(set(names))


def test_empty_letter_slug_is_schema_failure():
    row = ROW_PUBLISHED.replace("<td>V</td>", "<td>--</td>")
    with pytest.raises(SbSchemaError, match="empty slug"):
        extract_measures_page(table_html(HEADERS_OK, row), URL_1103)


def test_nested_th_does_not_hide_data_row():
    """Codex round-6: a nested table (with its own <th>) inside a
    cell must not cause the outer row to be skipped — zero rows is
    valid, so silent skipping publishes a silently empty snapshot."""
    nested = (
        "<table><tr><th>Inner</th></tr>"
        '<tr><td><a href="https://uploads.rov.sbcounty.gov/leak.pdf">x</a>'
        "</td></tr></table>"
    )
    row = ROW_PUBLISHED.replace("<td>50% + 1</td>", f"<td>50% + 1{nested}</td>")
    page = extract_measures_page(table_html(HEADERS_OK, row), URL_1103)

    assert len(page.rows) == 1  # row survives the nested <th>
    # ...and the nested table's link does NOT leak into the row's
    # documents (nor trip the no-links rule for the Percentage cell).
    assert {d.role for d in page.expected_documents} == {
        "resolution", "text", "analysis", "argument_for",
    }
    assert not any("leak.pdf" in d.url for d in page.expected_documents)


def test_th_scope_row_letter_cell_still_parsed():
    row = ROW_PUBLISHED.replace("<td>V</td>", '<th scope="row">V</th>')
    page = extract_measures_page(table_html(HEADERS_OK, row), URL_1103)
    assert page.rows[0].letter == "V"


def test_nested_full_measures_table_is_ambiguous():
    inner = table_html(HEADERS_OK, "").decode()
    inner_table = inner[inner.index("<table"): inner.index("</table>") + 8]
    row = ROW_PUBLISHED.replace("<td>50% + 1</td>", f"<td>50% + 1{inner_table}</td>")
    with pytest.raises(SbSchemaError, match="exactly 1 measures table"):
        extract_measures_page(table_html(HEADERS_OK, row), URL_1103)


def test_header_row_inside_thead_is_found():
    body = (
        f"<html><body><table><thead><tr>{HEADERS_OK}</tr></thead>"
        f"<tbody>{ROW_PUBLISHED}</tbody></table></body></html>"
    ).encode()
    page = extract_measures_page(body, URL_1103)
    assert len(page.rows) == 1


def test_header_cells_containing_links_still_match():
    headers = HEADERS_OK.replace(
        "<th>Analysis</th>", '<th><a href="/help">Analysis</a></th>'
    )
    page = extract_measures_page(table_html(headers, ROW_PUBLISHED), URL_1103)
    assert len(page.rows) == 1


def test_content_row_before_header_fails_loud():
    body = (
        "<html><body><table><tbody><tr><td>preamble</td></tr>"
        f"<tr>{HEADERS_OK}</tr>{ROW_PUBLISHED}</tbody></table></body></html>"
    ).encode()
    with pytest.raises(SbSchemaError, match="before the header row"):
        extract_measures_page(body, URL_1103)


def test_shipped_anchors_parse():
    from src.scrapers.registrar.sb import SB_FORWARD_ANCHORS

    for a in SB_FORWARD_ANCHORS:
        date.fromisoformat(a)  # raises on a typo'd anchor


def test_tolerant_decode_of_invalid_bytes():
    """Defensive path: a synthetic invalid byte must not crash the
    extractor (the live fixtures are valid strict UTF-8)."""
    body = table_html(HEADERS_OK, ROW_PUBLISHED).replace(
        b"City of X", b"City of X\x92s"
    )
    page = extract_measures_page(body, URL_1103)
    assert len(page.rows) == 1


# ---------------------------------------------------------------- discovery: synthetic


def landing_html(links: list[str]) -> bytes:
    anchors = "".join(f'<a href="{u}">link</a>' for u in links)
    return f"<html><body><nav>{anchors}</nav></body></html>".encode()


def test_discovery_rejects_wrong_origin_shape_and_invalid_dates():
    candidates = extract_discovery_candidates(
        landing_html(
            [
                "https://elections.sbcounty.gov/elections/2026/1103/measures/",
                "https://elections.sbcounty.gov/elections/2026/1103/measures/",  # dup
                "https://other.gov/elections/2027/0302/measures/",   # wrong origin
                "http://elections.sbcounty.gov/elections/2027/0302/measures/",  # http
                "/elections/2027/0302/",                              # no /measures/
                "/elections/2027/1399/measures/",                     # invalid date
                "/Elections/2027/0302/measures/",                     # case-variant path
            ]
        ),
        LANDING_URL,
    )
    assert candidates == (date(2026, 11, 3), date(2027, 3, 2))


# ---------------------------------------------------------------- anchor lifecycle


def idle_landing() -> dict:
    return {LANDING_URL: [html_response(landing_html([]), LANDING_URL)]}


def landing_with(dates: list[str]) -> dict:
    urls = [f"https://elections.sbcounty.gov/elections/{d}/measures/" for d in dates]
    return {LANDING_URL: [html_response(landing_html(urls), LANDING_URL)]}


NOV_2 = datetime(2026, 11, 2, 20, 0, 0, tzinfo=timezone.utc)   # LA: Nov 2, noon
NOV_9 = datetime(2026, 11, 9, 20, 0, 0, tzinfo=timezone.utc)   # LA: Nov 9
NOV_3_LATE_UTC = datetime(2026, 11, 4, 6, 0, 0, tzinfo=timezone.utc)  # LA: Nov 3, 10pm


def test_missing_active_anchor_is_red(store):
    """Nov 2 LA time: 2026-11-03 is active; index without it fails."""
    scraper = make_sb(store, landing_with([]), when=NOV_2)
    with pytest.raises(SbEnumerationError, match="2026-11-03"):
        scraper.scrape()


def test_retired_anchor_missing_is_green_idle(store):
    """Nov 9 LA time: the anchor retired; empty discovery = idle."""
    result = make_sb(store, landing_with([]), when=NOV_9).scrape()
    assert result.county == "sb"
    assert result.snapshots == ()
    assert result.elections_scraped == 0


def test_anchor_active_through_election_day_la_time(store):
    """UTC Nov 4 06:00 is still Nov 3 in LA — anchor remains active,
    so a missing index link is still red."""
    scraper = make_sb(store, landing_with([]), when=NOV_3_LATE_UTC)
    with pytest.raises(SbEnumerationError):
        scraper.scrape()


def test_newly_discovered_future_election_is_collected(store):
    """Nov 9: anchors retired, but a new 2027 election on the index
    gets scraped with provenance 'discovered'."""
    responses = landing_with(["2027/0302"])
    page_url = "https://elections.sbcounty.gov/elections/2027/0302/measures/"
    responses[page_url] = [html_response(table_html(HEADERS_OK, ""), page_url)]

    result = make_sb(store, responses, when=NOV_9).scrape()

    assert result.elections_scraped == 1
    snap = result.snapshots[0]
    assert snap.election_date == "2027-03-02"
    manifest = store.get_manifest(
        county="sb", election_date="2027-03-02", snapshot_id=snap.snapshot_id
    )
    assert manifest["discovery"]["provenance"] == "discovered"
    assert manifest["pdf_counts"] == {"expected": 0, "saved": 0}


# ---------------------------------------------------------------- integration


def full_fixture_responses() -> dict:
    """Fake session wired to the real pinned fixtures."""
    return {
        LANDING_URL: [
            html_response(fixture_bytes("landing_measures.html"), LANDING_URL)
        ],
        URL_1103: [
            html_response(fixture_bytes("measures_2026_1103.html"), URL_1103)
        ],
    }


def test_fixture_session_announced_election_end_to_end(store):
    """July run against the real fixtures: anchor 2026-11-03 active,
    discovered on the landing page, announced-state snapshot with
    zero PDFs finalizes as a valid observation."""
    result = make_sb(store, full_fixture_responses(), when=JULY).scrape()

    assert result.county == "sb"
    assert result.elections_scraped == 1
    assert result.artifacts_written == 1  # page.html only
    snap = result.snapshots[0]
    assert snap.election_date == "2026-11-03"

    manifest = store.get_manifest(
        county="sb", election_date="2026-11-03", snapshot_id=snap.snapshot_id
    )
    assert manifest["county"] == "sb"
    assert manifest["election_url"] == URL_1103
    assert manifest["discovery"]["provenance"] == "anchor_and_discovered"
    assert manifest["table_row_count"] == 2
    assert manifest["pdf_counts"] == {"expected": 0, "saved": 0}
    assert manifest["pdf_artifacts"] == []
    assert [a["filename"] for a in manifest["artifacts"]] == ["page.html"]

    refs = store.list_artifacts(
        county="sb", election_date="2026-11-03", snapshot_id=snap.snapshot_id
    )
    assert store.get_artifact(refs[0]) == fixture_bytes("measures_2026_1103.html")


def published_election_responses(pdf_ok=True) -> dict:
    """Synthetic published election with two expected PDFs."""
    row = (
        '<tr><td>V</td><td>City of X</td><td>Desc</td>'
        '<td><a href="https://uploads.rov.sbcounty.gov/d/ia.pdf">Impartial</a></td>'
        '<td><ul><li><a href="https://uploads.rov.sbcounty.gov/d/af.pdf">Argument For</a></li></ul></td>'
        '<td>50% + 1</td></tr>'
    )
    page_url = "https://elections.sbcounty.gov/elections/2027/0302/measures/"
    responses = landing_with(["2027/0302"])
    responses[page_url] = [html_response(table_html(HEADERS_OK, row), page_url)]
    ia = "https://uploads.rov.sbcounty.gov/d/ia.pdf"
    af = "https://uploads.rov.sbcounty.gov/d/af.pdf"
    responses[ia] = [
        pdf_response(ia) if pdf_ok
        else FakeResponse(content=b"<html>error</html>",
                          headers={"Content-Type": "text/html"}, url=ia)
    ]
    responses[af] = [pdf_response(af)]
    return responses


def test_published_election_saves_semantic_pdfs(store):
    result = make_sb(store, published_election_responses(), when=NOV_9).scrape()

    snap = result.snapshots[0]
    assert result.artifacts_written == 3  # page + 2 PDFs
    manifest = store.get_manifest(
        county="sb", election_date="2027-03-02", snapshot_id=snap.snapshot_id
    )
    assert manifest["pdf_counts"] == {"expected": 2, "saved": 2}
    names = [a["filename"] for a in manifest["artifacts"]]
    assert names == ["page.html", "measure_v_analysis.pdf", "measure_v_argument_for.pdf"]
    audit = manifest["pdf_artifacts"]
    assert [(a["role"], a["table_row"]) for a in audit] == [
        ("analysis", 1), ("argument_for", 1),
    ]


def test_html_masquerading_as_pdf_fails_county_no_manifest(store):
    scraper = make_sb(store, published_election_responses(pdf_ok=False), when=NOV_9)
    with pytest.raises(SbSchemaError, match="not a PDF"):
        scraper.scrape()
    # Orphans only — no completed snapshot published.
    assert store.list_snapshots(county="sb", election_date="2027-03-02") == []


def test_missing_expected_pdf_fails_county_no_manifest(store):
    responses = published_election_responses()
    responses["https://uploads.rov.sbcounty.gov/d/af.pdf"] = []  # 404s
    scraper = make_sb(store, responses, when=NOV_9)
    with pytest.raises(ScraperError):
        scraper.scrape()
    assert store.list_snapshots(county="sb", election_date="2027-03-02") == []


def test_measures_page_redirected_off_origin_fails(store):
    responses = landing_with(["2027/0302"])
    page_url = "https://elections.sbcounty.gov/elections/2027/0302/measures/"
    responses[page_url] = [
        html_response(table_html(HEADERS_OK, ""), "https://parked-domain.example/")
    ]
    scraper = make_sb(store, responses, when=NOV_9)
    with pytest.raises(SbSchemaError, match="off-origin"):
        scraper.scrape()


def test_published_to_linkfree_regression_is_valid_observation(store):
    """Codex round-5: a page that HAD links and now has none is an
    observed retraction — a valid 0-expected snapshot, NOT a failure
    (no comparison against prior manifests)."""
    linkfree_row = (
        "<tr><td>V</td><td>City of X</td><td>Desc</td>"
        "<td>Impartial</td><td><ul><li>Contact the clerk.</li></ul></td>"
        "<td>50% + 1</td></tr>"
    )
    page_url = "https://elections.sbcounty.gov/elections/2027/0302/measures/"
    responses = landing_with(["2027/0302"])
    responses[page_url] = [
        html_response(table_html(HEADERS_OK, linkfree_row), page_url)
    ]

    result = make_sb(store, responses, when=NOV_9).scrape()

    manifest = store.get_manifest(
        county="sb",
        election_date="2027-03-02",
        snapshot_id=result.snapshots[0].snapshot_id,
    )
    assert manifest["pdf_counts"] == {"expected": 0, "saved": 0}
    assert manifest["table_row_count"] == 1


def test_same_origin_redirect_to_wrong_election_fails(store):
    """Codex round-6: a same-origin redirect onto ANOTHER election's
    measures page must not be stored under the requested date."""
    responses = landing_with(["2027/0302"])
    page_url = "https://elections.sbcounty.gov/elections/2027/0302/measures/"
    responses[page_url] = [
        html_response(
            table_html(HEADERS_OK, ""),
            "https://elections.sbcounty.gov/elections/2026/1103/measures/",
        )
    ]
    scraper = make_sb(store, responses, when=NOV_9)
    with pytest.raises(SbSchemaError, match="different election"):
        scraper.scrape()


def test_pdf_cross_origin_https_redirect_accepted(store):
    responses = published_election_responses()
    ia = "https://uploads.rov.sbcounty.gov/d/ia.pdf"
    responses[ia] = [
        FakeResponse(
            content=b"%PDF-1.4\nfake",
            headers={"Content-Type": "application/pdf"},
            url="https://cdn.sbcounty.example/d/ia.pdf",  # off-origin, HTTPS
        )
    ]
    result = make_sb(store, responses, when=NOV_9).scrape()
    assert result.artifacts_written == 3


def test_pdf_http_downgrade_rejected(store):
    """Codex round-6: an HTTPS source redirecting to plain HTTP must
    never be accepted as a saved document."""
    responses = published_election_responses()
    ia = "https://uploads.rov.sbcounty.gov/d/ia.pdf"
    responses[ia] = [
        FakeResponse(
            content=b"%PDF-1.4\nfake",
            headers={"Content-Type": "application/pdf"},
            url="http://uploads.rov.sbcounty.gov/d/ia.pdf",  # downgraded
        )
    ]
    scraper = make_sb(store, responses, when=NOV_9)
    with pytest.raises(SbSchemaError, match="non-HTTPS"):
        scraper.scrape()
    assert store.list_snapshots(county="sb", election_date="2027-03-02") == []


def test_pdf_signature_fallback_with_generic_mime(store):
    responses = published_election_responses()
    ia = "https://uploads.rov.sbcounty.gov/d/ia.pdf"
    responses[ia] = [
        FakeResponse(
            content=b"%PDF-1.7\nreal enough",
            headers={"Content-Type": "application/octet-stream"},
            url=ia,
        )
    ]
    result = make_sb(store, responses, when=NOV_9).scrape()
    assert result.artifacts_written == 3


def test_multi_election_ordering_and_earlier_snapshot_survival(store):
    """Two elections: the earlier one completes; the later one fails
    on a missing PDF. County fails, but the completed earlier
    snapshot remains a valid immutable observation."""
    url_a = "https://elections.sbcounty.gov/elections/2027/0302/measures/"
    url_b = "https://elections.sbcounty.gov/elections/2027/0602/measures/"
    bad_row = (
        "<tr><td>Q</td><td>City of Y</td><td>Desc</td>"
        '<td><a href="https://uploads.rov.sbcounty.gov/gone.pdf">Impartial</a></td>'
        "<td></td><td>50% + 1</td></tr>"
    )
    responses = landing_with(["2027/0302", "2027/0602"])
    responses[url_a] = [html_response(table_html(HEADERS_OK, ""), url_a)]
    responses[url_b] = [html_response(table_html(HEADERS_OK, bad_row), url_b)]
    # gone.pdf unscripted -> 404 -> FetchError

    scraper = make_sb(store, responses, when=NOV_9)
    with pytest.raises(ScraperError):
        scraper.scrape()

    # Earlier election published; failed one left no manifest.
    assert store.list_snapshots(county="sb", election_date="2027-03-02") != []
    assert store.list_snapshots(county="sb", election_date="2027-06-02") == []


def test_manifest_extras_survive_json_round_trip(store):
    result = make_sb(store, full_fixture_responses(), when=JULY).scrape()
    snap = result.snapshots[0]
    manifest = store.get_manifest(
        county="sb", election_date="2026-11-03", snapshot_id=snap.snapshot_id
    )
    assert json.loads(json.dumps(manifest)) == manifest
