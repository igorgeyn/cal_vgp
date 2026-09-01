"""San Mateo registrar capture, interpretation, enumeration, and storage tests."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest

from src.scrapers.registrar import smc_interpretation
from src.scrapers.registrar.parser import SnapshotValidationError, parse_election
from src.scrapers.registrar.smc import (
    EXPECTED_GROUPS,
    INDEX_URL,
    NOVEMBER_2026_URL,
    SmcEnumerationError,
    SmcSchemaError,
    SmcScraper,
    extract_discovery_candidates,
    extract_measures_page,
)
from src.scrapers.registrar.smc_interpretation import (
    SmcInterpretationError,
    interpret_measures_page,
)
from src.scrapers.registrar.storage import LocalArtifactStore


FIXTURES = Path(__file__).parent / "fixtures" / "registrar" / "smc"
ACTIVE_NOW = datetime(2026, 8, 31, 18, 0, 0, tzinfo=timezone.utc)
AFTER_ELECTION = datetime(2026, 11, 9, 20, 0, 0, tzinfo=timezone.utc)


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def normalized(value: str) -> str:
    return " ".join(value.casefold().split())


class FakeResponse:
    def __init__(self, status_code=200, content=b"", headers=None, url=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {"Content-Type": "text/html"}
        self.url = url or ""

    @property
    def text(self):
        return self.content.decode("utf-8", errors="replace")


class FakeSession:
    """Scripted session; unscripted URLs return 404 (robots default-allow)."""

    def __init__(self, responses=None):
        self.responses = dict(responses or {})
        self.calls: list[str] = []

    def get(self, url, headers=None, timeout=None, allow_redirects=True):
        self.calls.append(url)
        queue = self.responses.get(url)
        if not queue:
            return FakeResponse(status_code=404, url=url)
        response = queue.pop(0)
        if not response.url:
            response.url = url
        return response


@pytest.fixture
def store(tmp_path) -> LocalArtifactStore:
    return LocalArtifactStore(base_dir=tmp_path, env="dev")


def html_response(body: bytes, url: str) -> FakeResponse:
    return FakeResponse(
        content=body,
        headers={"Content-Type": "text/html; charset=UTF-8"},
        url=url,
    )


def pdf_response(url: str) -> FakeResponse:
    return FakeResponse(
        content=b"%PDF-1.7\nfixture\n%%EOF",
        headers={"Content-Type": "application/pdf"},
        url=url,
    )


def make_scraper(store, responses, *, when=ACTIVE_NOW, anchors=None):
    scraper = SmcScraper(
        store,
        run_id="testrun",
        clock=lambda: when,
        session=FakeSession(responses),
        sleep=lambda seconds: None,
    )
    if anchors is not None:
        scraper.anchors = anchors
    return scraper


def panel_html(
    heading="Measure A – San Mateo County Test Measure",
    threshold="Majority Voter Approval Required",
    links="",
):
    return (
        '<smc-accordion-panel slot="panels">'
        f'<h5 slot="heading">{heading}</h5>'
        f'<div class="wysiwyg"><p>{threshold}</p><p>{links}</p></div>'
        "</smc-accordion-panel>"
    )


def wrapper(label="Impartial Analysis", target="https://smcacre.gov/system/files/a.pdf"):
    from urllib.parse import quote

    return (
        '<a href="/archival-document?document='
        f'{quote(target, safe="")}&amp;title=x">{label}</a>'
    )


def measures_html(*, group_panels=None, between_heading_and_accordion="") -> bytes:
    group_panels = dict(group_panels or {})
    defaults = {
        "county measures": panel_html(),
        "regional measure": panel_html(
            heading="Regional Transit Measure – Test District: Test Measure"
        ),
        "school district measures": panel_html(
            heading="Measure B – Test School District: Test Measure"
        ),
        "city measures": panel_html(
            heading="Measure C – City of Test: Test Measure"
        ),
    }
    chunks = ["<html><body><div class='slices'>"]
    for group in EXPECTED_GROUPS:
        title = group.title()
        chunks.append(f"<outline-container><div><h3>{title}</h3></div></outline-container>")
        if group == "county measures" and between_heading_and_accordion:
            chunks.append(between_heading_and_accordion)
        chunks.append("<smc-accordion>")
        chunks.append(group_panels.get(group, defaults[group]))
        chunks.append("</smc-accordion>")
    chunks.append("</div></body></html>")
    return "".join(chunks).encode()


# ---------------------------------------------------------------- fixtures


def test_fixture_sidecars_match_raw_bytes():
    for filename in (
        "election_2026_1103.html",
        "past_elections_results.html",
        "pdf_resolution_text_tax_r.pdf",
        "pdf_resolution_text_g.pdf",
    ):
        body = fixture_bytes(filename)
        meta = json.loads((FIXTURES / f"{filename}.meta.json").read_text())
        assert meta["size_bytes"] == len(body)
        assert meta["sha256"] == hashlib.sha256(body).hexdigest()
        assert meta["user_agent"].startswith("cal-vgp-registrar-scraper/0.1")


def test_live_fixture_exact_capture_contract():
    captured = extract_measures_page(
        fixture_bytes("election_2026_1103.html"), NOVEMBER_2026_URL
    )
    assert captured.headers == EXPECTED_GROUPS
    assert len(captured.rows) == 29
    assert len(captured.expected_documents) == 135
    assert Counter(document.column for document in captured.expected_documents) == {
        "county measures": 9,
        "regional measure": 6,
        "school district measures": 35,
        "city measures": 85,
    }
    assert Counter(normalized(document.label) for document in captured.expected_documents) == {
        "impartial analysis": 29,
        "primary argument in favor": 26,
        "resolution and full text": 24,
        "primary argument against": 18,
        "rebuttal to argument against": 17,
        "rebuttal to argument in favor": 16,
        "resolution, full text and tax rate statement": 4,
        "resolution": 1,
    }
    assert Counter(row.percentage_to_pass for row in captured.rows) == {
        "50% + 1": 21,
        "2/3": 5,
        "55%": 3,
    }
    assert captured.rows[0].letter == "L"
    assert captured.rows[0].jurisdiction == "San Mateo County"
    assert captured.rows[4].letter == "Regional Transit"
    assert captured.rows[-3].letter == "G"  # fixture has extra heading whitespace


def _url_family(url: str) -> str:
    path = urlparse(url).path
    if path.endswith("/San%20Mateo%20County%20Amendments.pdf"):
        return "shared_county_packet"
    for family in (
        "ImpartialAnalysis",
        "RebutArgInFavor",
        "RebutArgInFav",
        "RebutArgAgainst",
        "RebutAgainst",
        "ArgInFavor",
        "ArgAgainst",
        "Contest%20Code-Reso",
        "Contest%20-Code-Reso",
    ):
        if family.casefold() in path.casefold():
            return family
    return "other"


def test_fixture_label_url_distribution_documents_conventions_and_anomalies():
    captured = extract_measures_page(
        fixture_bytes("election_2026_1103.html"), NOVEMBER_2026_URL
    )
    distribution = Counter(
        (normalized(document.label), _url_family(document.url))
        for document in captured.expected_documents
    )
    assert distribution == Counter(
        {
            ("impartial analysis", "ImpartialAnalysis"): 29,
            ("primary argument in favor", "ArgInFavor"): 26,
            ("primary argument against", "ArgAgainst"): 18,
            ("rebuttal to argument in favor", "RebutArgInFavor"): 15,
            ("rebuttal to argument in favor", "RebutArgInFav"): 1,
            ("rebuttal to argument against", "RebutArgAgainst"): 16,
            ("rebuttal to argument against", "RebutAgainst"): 1,
            ("resolution and full text", "Contest%20Code-Reso"): 19,
            ("resolution and full text", "Contest%20-Code-Reso"): 1,
            ("resolution and full text", "shared_county_packet"): 4,
            ("resolution, full text and tax rate statement", "Contest%20Code-Reso"): 4,
            ("resolution", "Contest%20Code-Reso"): 1,
        }
    )
    assert all(urlparse(document.url).netloc == "smcacre.gov" for document in captured.expected_documents)


def test_composites_expand_one_artifact_into_queryable_roles():
    captured = extract_measures_page(
        fixture_bytes("election_2026_1103.html"), NOVEMBER_2026_URL
    )
    page = interpret_measures_page(captured)
    assert Counter(document.role for document in page.expected_documents) == {
        "resolution": 29,
        "text": 28,
        "tax_rate_statement": 4,
        "analysis": 29,
        "argument_for": 26,
        "argument_against": 18,
        "rebuttal_for": 16,
        "rebuttal_against": 17,
    }
    measure_r = next(row for row in page.rows if row.letter == "R")
    composite = measure_r.documents[:3]
    assert [document.role for document in composite] == [
        "resolution", "text", "tax_rate_statement"
    ]
    assert len({document.filename for document in composite}) == 1
    assert len({document.url for document in composite}) == 1


def test_case_and_whitespace_label_variants_are_normalized():
    body = measures_html(
        group_panels={
            "county measures": panel_html(
                links=wrapper("  Primary Argument\u00a0In   Favor  ")
            )
        }
    )
    page = interpret_measures_page(extract_measures_page(body, NOVEMBER_2026_URL))
    assert page.rows[0].documents[0].role == "argument_for"


# ---------------------------------------------------------------- structural capture failures


def test_missing_measure_group_fails_capture():
    body = measures_html().replace(
        b"<h3>City Measures</h3>", b"<h3>Other Documents</h3>"
    )
    with pytest.raises(SmcSchemaError, match="city measures"):
        extract_measures_page(body, NOVEMBER_2026_URL)


def test_duplicate_measure_group_fails_capture():
    body = measures_html().replace(
        b"<h3>City Measures</h3>", b"<h3>County Measures</h3>"
    )
    with pytest.raises(SmcSchemaError, match="county measures"):
        extract_measures_page(body, NOVEMBER_2026_URL)


def test_group_heading_must_immediately_own_accordion():
    body = measures_html(between_heading_and_accordion="<div>interloper</div>")
    with pytest.raises(SmcSchemaError, match="immediately followed"):
        extract_measures_page(body, NOVEMBER_2026_URL)


@pytest.mark.parametrize(
    "heading,error",
    [
        ("Proposition A – San Mateo County Test Measure", "designation"),
        ("Measure A San Mateo County Test Measure", "malformed measure heading"),
        ("Measure A – City of X Test Measure", "separator"),
    ],
)
def test_malformed_panel_heading_fails_capture(heading, error):
    body = measures_html(
        group_panels={"city measures": panel_html(heading=heading)}
    )
    with pytest.raises(SmcSchemaError, match=error):
        extract_measures_page(body, NOVEMBER_2026_URL)


def test_unknown_or_duplicate_threshold_fails_capture():
    unknown = measures_html(
        group_panels={
            "county measures": panel_html(threshold="Three-Fifths Required")
        }
    )
    with pytest.raises(SmcSchemaError, match="0 recognized approval"):
        extract_measures_page(unknown, NOVEMBER_2026_URL)

    duplicate = measures_html(
        group_panels={
            "county measures": panel_html(
                threshold=(
                    "Majority Voter Approval Required</p>"
                    "<p>55% Voter Approval Required"
                )
            )
        }
    )
    with pytest.raises(SmcSchemaError, match="2 recognized approval"):
        extract_measures_page(duplicate, NOVEMBER_2026_URL)


@pytest.mark.parametrize(
    "link",
    [
        '<a href="https://smcacre.gov/system/files/a.pdf">Impartial Analysis</a>',
        '<a href="/archival-document?title=x">Impartial Analysis</a>',
        wrapper(target="http://smcacre.gov/system/files/a.pdf"),
        wrapper(target="https://cdn.example/system/files/a.pdf"),
        wrapper(target="https://smcacre.gov/system/files/a.html"),
    ],
)
def test_invalid_document_wrapper_or_target_fails_capture(link):
    body = measures_html(
        group_panels={"county measures": panel_html(links=link)}
    )
    with pytest.raises(SmcSchemaError):
        extract_measures_page(body, NOVEMBER_2026_URL)


def test_nested_panel_links_are_not_swept_into_owning_measure():
    nested = (
        "<smc-accordion><smc-accordion-panel>"
        f"{wrapper('Unknown Nested Label')}"
        "</smc-accordion-panel></smc-accordion>"
    )
    body = measures_html(
        group_panels={
            "county measures": panel_html(links=wrapper() + nested)
        }
    )
    captured = extract_measures_page(body, NOVEMBER_2026_URL)
    assert [document.label for document in captured.rows[0].documents] == [
        "Impartial Analysis"
    ]


# ---------------------------------------------------------------- interpretation failures happen after capture


def test_unknown_label_is_captured_then_interpretation_fails():
    body = measures_html(
        group_panels={
            "county measures": panel_html(links=wrapper("Fiscal Impact Summary"))
        }
    )
    captured = extract_measures_page(body, NOVEMBER_2026_URL)
    assert captured.rows[0].documents[0].label == "Fiscal Impact Summary"
    with pytest.raises(SmcInterpretationError, match="unknown document label"):
        interpret_measures_page(captured)


def test_duplicate_label_and_duplicate_role_fail_interpretation():
    duplicate_label = measures_html(
        group_panels={
            "county measures": panel_html(links=wrapper() + wrapper())
        }
    )
    with pytest.raises(SmcInterpretationError, match="duplicate document label"):
        interpret_measures_page(
            extract_measures_page(duplicate_label, NOVEMBER_2026_URL)
        )

    duplicate_role = measures_html(
        group_panels={
            "county measures": panel_html(
                links=wrapper("Resolution") + wrapper("Resolution and Full Text")
            )
        }
    )
    with pytest.raises(SmcInterpretationError, match="repeats role"):
        interpret_measures_page(
            extract_measures_page(duplicate_role, NOVEMBER_2026_URL)
        )


# ---------------------------------------------------------------- enumeration and integration


def test_archive_fixture_discovery_is_deduped_and_dated():
    candidates = extract_discovery_candidates(
        fixture_bytes("past_elections_results.html"), INDEX_URL
    )
    assert len(candidates) == len({candidate.election_date for candidate in candidates})
    assert candidates[-1].election_date.isoformat() == "2026-06-02"
    assert candidates[-1].url.endswith("june-2-2026-statewide-direct-primary-election")


def test_ambiguous_discovery_urls_for_same_date_fail():
    body = (
        '<a href="/elections/march-2-2027-special-election">Election Information</a>'
        '<a href="/elections/march-2-2027-city-special-election">Election Information</a>'
    ).encode()
    with pytest.raises(SmcEnumerationError, match="multiple"):
        extract_discovery_candidates(body, INDEX_URL)


def full_fixture_responses() -> dict:
    page_body = fixture_bytes("election_2026_1103.html")
    responses = {
        INDEX_URL: [
            html_response(fixture_bytes("past_elections_results.html"), INDEX_URL)
        ],
        NOVEMBER_2026_URL: [html_response(page_body, NOVEMBER_2026_URL)],
    }
    for document in extract_measures_page(
        page_body, NOVEMBER_2026_URL
    ).expected_documents:
        responses.setdefault(document.url, []).append(pdf_response(document.url))
    return responses


def test_active_anchor_full_fixture_capture_and_offline_parse(store, tmp_path):
    result = make_scraper(store, full_fixture_responses()).scrape()
    assert result.elections_scraped == 1
    assert result.artifacts_written == 136
    snapshot = result.snapshots[0]
    manifest = store.get_manifest(
        county="smc",
        election_date="2026-11-03",
        snapshot_id=snapshot.snapshot_id,
    )
    assert manifest["schema_version"] == 2
    assert manifest["discovery"]["provenance"] == "anchor"
    assert manifest["table_row_count"] == 29
    assert manifest["pdf_counts"] == {"expected": 135, "saved": 135}
    assert len(manifest["pdf_artifacts"]) == 135
    assert all("role" not in audit for audit in manifest["pdf_artifacts"])

    parsed = parse_election(
        store,
        county="smc",
        election_date="2026-11-03",
        output_path=tmp_path / "smc.jsonl",
    )
    assert parsed.record_count == 29
    measure_r = next(
        record for record in parsed.records
        if record["measure"]["measure_letter"] == "R"
    )
    by_role = {document["role"]: document for document in measure_r["documents"]}
    assert {"resolution", "text", "tax_rate_statement"}.issubset(by_role)
    assert by_role["resolution"]["snapshot_filename"] == by_role["text"]["snapshot_filename"]
    assert by_role["text"]["snapshot_filename"] == by_role["tax_rate_statement"]["snapshot_filename"]


def test_second_snapshot_links_shared_packet_rows_by_unique_documents(store, tmp_path):
    first = make_scraper(store, full_fixture_responses(), when=ACTIVE_NOW).scrape()
    second_time = datetime(2026, 9, 7, 18, 0, 0, tzinfo=timezone.utc)
    second = make_scraper(store, full_fixture_responses(), when=second_time).scrape()

    report = parse_election(
        store,
        county="smc",
        election_date="2026-11-03",
        snapshot_id=second.snapshots[0].snapshot_id,
        output_path=tmp_path / "smc-second.jsonl",
    )
    assert report.snapshots_replayed == 2
    assert report.record_count == 29
    assert len({record["measure"]["measure_id"] for record in report.records}) == 29
    assert first.snapshots[0].snapshot_id != second.snapshots[0].snapshot_id


def test_retired_anchor_and_archive_without_future_candidates_is_idle(store):
    responses = {
        INDEX_URL: [
            html_response(fixture_bytes("past_elections_results.html"), INDEX_URL)
        ]
    }
    result = make_scraper(store, responses, when=AFTER_ELECTION).scrape()
    assert result.snapshots == ()


def test_newly_discovered_future_election_is_collected(store):
    future_url = "https://smcacre.gov/elections/march-2-2027-special-election"
    index = (
        f'<a href="{future_url}">Election Information</a>'
        f'<a href="{future_url}">Election Information</a>'
    ).encode()
    responses = {
        INDEX_URL: [html_response(index, INDEX_URL)],
        future_url: [html_response(measures_html(), future_url)],
    }
    result = make_scraper(store, responses, when=AFTER_ELECTION).scrape()
    assert result.elections_scraped == 1
    manifest = store.get_manifest(
        county="smc",
        election_date="2027-03-02",
        snapshot_id=result.snapshots[0].snapshot_id,
    )
    assert manifest["discovery"]["provenance"] == "discovered"
    assert manifest["pdf_counts"] == {"expected": 0, "saved": 0}


def test_unknown_label_does_not_red_capture_but_reds_offline_parse(store, tmp_path):
    body = measures_html(
        group_panels={
            "county measures": panel_html(links=wrapper("New County Filing"))
        }
    )
    responses = {
        INDEX_URL: [
            html_response(fixture_bytes("past_elections_results.html"), INDEX_URL)
        ],
        NOVEMBER_2026_URL: [html_response(body, NOVEMBER_2026_URL)],
        "https://smcacre.gov/system/files/a.pdf": [
            pdf_response("https://smcacre.gov/system/files/a.pdf")
        ],
    }
    result = make_scraper(store, responses).scrape()
    assert result.artifacts_written == 2
    with pytest.raises(SnapshotValidationError, match="unknown document label"):
        parse_election(
            store,
            county="smc",
            election_date="2026-11-03",
            output_path=tmp_path / "never.jsonl",
        )


def test_page_redirect_and_pdf_redirect_fail_capture(store):
    page_redirect = full_fixture_responses()
    page_redirect[NOVEMBER_2026_URL] = [
        html_response(
            fixture_bytes("election_2026_1103.html"),
            "https://smcacre.gov/elections/june-2-2026-statewide-direct-primary-election",
        )
    ]
    with pytest.raises(SmcSchemaError, match="different election"):
        make_scraper(store, page_redirect).scrape()

    body = measures_html(
        group_panels={"county measures": panel_html(links=wrapper())}
    )
    responses = {
        INDEX_URL: [
            html_response(fixture_bytes("past_elections_results.html"), INDEX_URL)
        ],
        NOVEMBER_2026_URL: [html_response(body, NOVEMBER_2026_URL)],
        "https://smcacre.gov/system/files/a.pdf": [
            FakeResponse(
                content=b"%PDF-1.7\n",
                headers={"Content-Type": "application/pdf"},
                url="https://cdn.example/a.pdf",
            )
        ],
    }
    with pytest.raises(SmcSchemaError, match="off-origin"):
        make_scraper(store, responses).scrape()


def test_non_pdf_document_fails_without_complete_snapshot(store):
    body = measures_html(
        group_panels={"county measures": panel_html(links=wrapper())}
    )
    responses = {
        INDEX_URL: [
            html_response(fixture_bytes("past_elections_results.html"), INDEX_URL)
        ],
        NOVEMBER_2026_URL: [html_response(body, NOVEMBER_2026_URL)],
        "https://smcacre.gov/system/files/a.pdf": [
            FakeResponse(
                content=b"<html>not pdf</html>",
                headers={"Content-Type": "text/html"},
                url="https://smcacre.gov/system/files/a.pdf",
            )
        ],
    }
    with pytest.raises(SmcSchemaError, match="not a PDF"):
        make_scraper(store, responses).scrape()
    assert store.list_snapshots(county="smc", election_date="2026-11-03") == []
