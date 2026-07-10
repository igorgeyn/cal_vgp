"""Tests for the registrar base scraper (polite fetch + snapshot
writing) and the NoOp wiring scraper."""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import pytest
import requests

from src.scrapers.registrar.base import (
    DEFAULT_USER_AGENT,
    CountyRegistrarScraper,
    FetchError,
    FetchResult,
    RobotsDisallowedError,
    ScrapeResult,
    ScraperConfig,
    ScraperError,
    SnapshotSummary,
)
from src.scrapers.registrar.noop import (
    FAKE_ELECTION_DATE,
    FAKE_HTML,
    FAKE_PDF,
    NoOpCountyScraper,
)
from src.scrapers.registrar.storage import ArtifactMetadata, LocalArtifactStore


# ---------------------------------------------------------------- fakes


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        content: bytes = b"",
        headers: dict | None = None,
        url: str | None = None,
    ):
        self.status_code = status_code
        self.content = content
        self.headers = headers if headers is not None else {"Content-Type": "text/html"}
        self.url = url or ""

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class FakeSession:
    """Scripted session. `responses` maps URL -> list of FakeResponse
    or Exception instances, consumed in order. Unscripted URLs get a
    404 (so robots.txt defaults to 'unfetchable = allowed')."""

    def __init__(self, responses: dict[str, list] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, dict]] = []  # (url, headers)
        self.redirect_policy: list[tuple[str, bool]] = []  # (url, allow_redirects)

    def get(self, url, headers=None, timeout=None, allow_redirects=True):
        self.calls.append((url, headers or {}))
        self.redirect_policy.append((url, allow_redirects))
        queue = self.responses.get(url)
        if not queue:
            return FakeResponse(status_code=404, url=url)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if not item.url:
            item.url = url
        return item

    def urls_called(self) -> list[str]:
        return [url for url, _ in self.calls]


class FakeTime:
    """Linked sleep + monotonic: sleeping advances the clock, so
    rate-limit arithmetic is exact and assertions deterministic."""

    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def monotonic(self) -> float:
        return self.now


class DummyScraper(CountyRegistrarScraper):
    county = "dummy"

    def scrape(self) -> ScrapeResult:
        return ScrapeResult(county=self.county)


FIXED_NOW = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)


def make_scraper(session=None, config=None, clock=None):
    """DummyScraper with fakes wired in. Returns (scraper, faketime);
    faketime.sleeps records every sleep."""
    ft = FakeTime()
    scraper = DummyScraper(
        LocalArtifactStore(base_dir="unused-in-fetch-tests"),
        config=config or ScraperConfig(),
        clock=clock or (lambda: FIXED_NOW),
        session=session or FakeSession(),
        sleep=ft.sleep,
        monotonic=ft.monotonic,
    )
    return scraper, ft


NO_ROBOTS = ScraperConfig(respect_robots=False)

PAGE_URL = "https://example.gov/elections/measures/"
ROBOTS_URL = "https://example.gov/robots.txt"


# ---------------------------------------------------------------- fetch: happy path


def test_fetch_sends_polite_user_agent_everywhere():
    session = FakeSession({PAGE_URL: [FakeResponse(content=b"<html/>")]})
    scraper, _ = make_scraper(session=session)

    scraper.fetch(PAGE_URL)

    assert session.urls_called() == [ROBOTS_URL, PAGE_URL]
    for _, headers in session.calls:
        assert headers["User-Agent"] == DEFAULT_USER_AGENT
    assert "cal-vgp-registrar-scraper" in DEFAULT_USER_AGENT
    assert "contact:" in DEFAULT_USER_AGENT


def test_fetch_result_carries_response_fields():
    session = FakeSession(
        {
            PAGE_URL: [
                FakeResponse(
                    content=b"<html>hi</html>",
                    headers={
                        "Content-Type": "text/html; charset=utf-8",
                        "ETag": '"abc"',
                        "Last-Modified": "Mon, 06 Jul 2026 00:00:00 GMT",
                    },
                    url=PAGE_URL + "final",
                )
            ]
        }
    )
    scraper, _ = make_scraper(session=session)
    result = scraper.fetch(PAGE_URL)

    assert result.url == PAGE_URL
    assert result.final_url == PAGE_URL + "final"
    assert result.http_status == 200
    assert result.content_type == "text/html"  # params stripped
    assert result.body == b"<html>hi</html>"
    assert result.etag == '"abc"'
    assert result.last_modified == "Mon, 06 Jul 2026 00:00:00 GMT"
    assert result.fetch_mode == "requests"
    assert result.fetched_at == FIXED_NOW.isoformat()


def test_fetch_result_to_metadata_bridges_to_storage():
    result = FetchResult(
        url="https://x.gov/a",
        final_url="https://x.gov/a/",
        http_status=200,
        content_type="application/pdf",
        body=b"%PDF",
        fetched_at="2026-07-06T12:00:00+00:00",
        fetch_mode="requests",
        etag='"e"',
        last_modified="lm",
    )
    meta = result.to_metadata()
    assert isinstance(meta, ArtifactMetadata)
    assert meta.source_url == "https://x.gov/a"
    assert meta.final_url == "https://x.gov/a/"
    assert meta.content_type == "application/pdf"
    assert meta.http_status == 200
    assert meta.etag == '"e"'
    assert meta.last_modified == "lm"
    assert meta.fetch_mode == "requests"


# ---------------------------------------------------------------- fetch: retries


def test_fetch_retries_5xx_then_succeeds_with_backoff():
    session = FakeSession(
        {
            PAGE_URL: [
                FakeResponse(status_code=503),
                FakeResponse(content=b"recovered"),
            ]
        }
    )
    scraper, ft = make_scraper(session=session)
    result = scraper.fetch(PAGE_URL)

    assert result.body == b"recovered"
    assert session.urls_called().count(PAGE_URL) == 2
    # robots->page rate-limit spacing, then the 2s backoff.
    assert ft.sleeps == [2.0, 2.0]


def test_fetch_retries_connection_errors_then_raises():
    session = FakeSession(
        {
            PAGE_URL: [
                requests.ConnectionError("refused"),
                requests.Timeout("timeout"),
                requests.ConnectionError("refused again"),
            ]
        }
    )
    scraper, ft = make_scraper(session=session)
    with pytest.raises(FetchError) as exc_info:
        scraper.fetch(PAGE_URL)

    assert session.urls_called().count(PAGE_URL) == 3  # max_retries
    assert exc_info.value.url == PAGE_URL
    # Rate-limit spacing after robots, then exponential backoff
    # between attempts (none after the last).
    assert ft.sleeps == [2.0, 2.0, 4.0]


def test_fetch_retries_429_with_backoff():
    """429 means 'slow down', not 'go away' — retry politely."""
    session = FakeSession(
        {
            PAGE_URL: [
                FakeResponse(status_code=429),
                FakeResponse(content=b"welcomed back"),
            ]
        }
    )
    scraper, ft = make_scraper(session=session)
    result = scraper.fetch(PAGE_URL)

    assert result.body == b"welcomed back"
    assert 2.0 in ft.sleeps  # default backoff (no Retry-After sent)


def test_fetch_does_not_retry_4xx():
    session = FakeSession({PAGE_URL: [FakeResponse(status_code=403)]})
    scraper, _ = make_scraper(session=session)
    with pytest.raises(FetchError) as exc_info:
        scraper.fetch(PAGE_URL)

    assert exc_info.value.http_status == 403
    assert session.urls_called().count(PAGE_URL) == 1


def test_fetch_exhausted_5xx_raises_with_status():
    session = FakeSession({PAGE_URL: [FakeResponse(status_code=500)] * 3})
    scraper, _ = make_scraper(session=session)
    with pytest.raises(FetchError) as exc_info:
        scraper.fetch(PAGE_URL)

    assert exc_info.value.http_status == 500
    assert session.urls_called().count(PAGE_URL) == 3


# ---------------------------------------------------------------- fetch: Retry-After


def retry_after_scraper(header_value: str):
    session = FakeSession(
        {
            PAGE_URL: [
                FakeResponse(
                    status_code=429, headers={"Retry-After": header_value}
                ),
                FakeResponse(content=b"ok"),
            ]
        }
    )
    return make_scraper(session=session, config=NO_ROBOTS)


def test_retry_after_delta_seconds_honored():
    scraper, ft = retry_after_scraper("60")
    assert scraper.fetch(PAGE_URL).body == b"ok"
    assert ft.sleeps == [60.0]


def test_retry_after_http_date_honored():
    # 90 seconds after the injected clock's FIXED_NOW.
    scraper, ft = retry_after_scraper("Mon, 06 Jul 2026 12:01:30 GMT")
    assert scraper.fetch(PAGE_URL).body == b"ok"
    assert ft.sleeps == [90.0]


def test_retry_after_malformed_falls_back_to_backoff():
    scraper, ft = retry_after_scraper("soon-ish")
    assert scraper.fetch(PAGE_URL).body == b"ok"
    assert ft.sleeps == [2.0]


def test_retry_after_capped():
    scraper, ft = retry_after_scraper("100000")
    assert scraper.fetch(PAGE_URL).body == b"ok"
    assert ft.sleeps == [300.0]  # retry_after_cap_seconds


def test_retry_after_past_http_date_clamps_to_zero():
    scraper, ft = retry_after_scraper("Mon, 06 Jul 2026 11:00:00 GMT")
    assert scraper.fetch(PAGE_URL).body == b"ok"
    # Clamped Retry-After of 0.0, then the per-domain rate limit
    # still spaces the retry — "now" never beats the 2s interval.
    assert ft.sleeps == [0.0, 2.0]


# ---------------------------------------------------------------- fetch: rate limit


def test_rate_limit_spaces_same_domain_requests():
    session = FakeSession(
        {PAGE_URL: [FakeResponse(content=b"1"), FakeResponse(content=b"2")]}
    )
    scraper, ft = make_scraper(session=session, config=NO_ROBOTS)

    scraper.fetch(PAGE_URL)
    assert ft.sleeps == []  # first request on the domain: no wait
    scraper.fetch(PAGE_URL)
    assert ft.sleeps == [2.0]  # full interval (fake clock: 0s elapsed)


def test_rate_limit_does_not_couple_distinct_domains():
    other_url = "https://other.gov/page"
    session = FakeSession(
        {
            PAGE_URL: [FakeResponse(content=b"1")],
            other_url: [FakeResponse(content=b"2")],
        }
    )
    scraper, ft = make_scraper(session=session, config=NO_ROBOTS)

    scraper.fetch(PAGE_URL)
    scraper.fetch(other_url)

    assert ft.sleeps == []


def test_robots_fetch_counts_against_rate_limit():
    """The robots request is a request; the page fetch right after
    it must wait out the interval."""
    session = FakeSession({PAGE_URL: [FakeResponse(content=b"ok")]})
    scraper, ft = make_scraper(session=session)

    scraper.fetch(PAGE_URL)

    assert session.urls_called() == [ROBOTS_URL, PAGE_URL]
    assert ft.sleeps == [2.0]


# ---------------------------------------------------------------- fetch: robots


def test_robots_disallow_raises_without_fetching_page():
    session = FakeSession(
        {
            ROBOTS_URL: [
                FakeResponse(content=b"User-agent: *\nDisallow: /elections/\n")
            ]
        }
    )
    scraper, _ = make_scraper(session=session)
    with pytest.raises(RobotsDisallowedError):
        scraper.fetch(PAGE_URL)

    assert PAGE_URL not in session.urls_called()


def test_robots_allow_list_permits_fetch():
    session = FakeSession(
        {
            ROBOTS_URL: [
                FakeResponse(content=b"User-agent: *\nDisallow: /admin/\n")
            ],
            PAGE_URL: [FakeResponse(content=b"ok")],
        }
    )
    scraper, _ = make_scraper(session=session)
    assert scraper.fetch(PAGE_URL).body == b"ok"


def test_robots_unfetchable_defaults_to_allowed():
    session = FakeSession(
        {
            ROBOTS_URL: [requests.ConnectionError("nope")],
            PAGE_URL: [FakeResponse(content=b"ok")],
        }
    )
    scraper, _ = make_scraper(session=session)
    assert scraper.fetch(PAGE_URL).body == b"ok"


def test_robots_fetched_once_per_domain():
    session = FakeSession(
        {
            PAGE_URL: [
                FakeResponse(content=b"1"),
                FakeResponse(content=b"2"),
            ]
        }
    )
    scraper, _ = make_scraper(session=session)
    scraper.fetch(PAGE_URL)
    scraper.fetch(PAGE_URL)

    assert session.urls_called().count(ROBOTS_URL) == 1


def test_respect_robots_false_skips_the_check():
    session = FakeSession({PAGE_URL: [FakeResponse(content=b"ok")]})
    scraper, _ = make_scraper(session=session, config=NO_ROBOTS)
    scraper.fetch(PAGE_URL)

    assert ROBOTS_URL not in session.urls_called()


# ---------------------------------------------------------------- fetch: redirects


def test_redirect_followed_with_result_from_final_hop():
    moved_url = "https://example.gov/moved/"
    session = FakeSession(
        {
            PAGE_URL: [
                FakeResponse(
                    status_code=302, headers={"Location": "/moved/"}
                )
            ],
            moved_url: [FakeResponse(content=b"final content")],
        }
    )
    scraper, _ = make_scraper(session=session, config=NO_ROBOTS)
    result = scraper.fetch(PAGE_URL)

    assert result.body == b"final content"
    assert result.url == PAGE_URL          # what we asked for
    assert result.final_url == moved_url   # where we ended up


def test_redirect_to_new_origin_checks_that_origins_robots():
    other_page = "https://other.gov/measures"
    session = FakeSession(
        {
            PAGE_URL: [
                FakeResponse(
                    status_code=301, headers={"Location": other_page}
                )
            ],
            "https://other.gov/robots.txt": [
                FakeResponse(content=b"User-agent: *\nDisallow: /\n")
            ],
        }
    )
    scraper, _ = make_scraper(session=session)
    with pytest.raises(RobotsDisallowedError):
        scraper.fetch(PAGE_URL)

    # The disallowed origin's page was never requested.
    assert other_page not in session.urls_called()


def test_redirect_without_location_raises():
    """A 3xx with no Location header is a broken response, not a
    successful fetch (Codex round-3)."""
    session = FakeSession({PAGE_URL: [FakeResponse(status_code=302, headers={})]})
    scraper, _ = make_scraper(session=session, config=NO_ROBOTS)
    with pytest.raises(FetchError, match="without a Location header"):
        scraper.fetch(PAGE_URL)


def test_robots_redirect_treated_as_unfetchable():
    """robots.txt redirecting (e.g. to another origin) must not be
    auto-followed — a redirected robots is unfetchable = allow."""
    session = FakeSession(
        {
            ROBOTS_URL: [
                FakeResponse(
                    status_code=301,
                    headers={"Location": "https://other.gov/robots.txt"},
                )
            ],
            PAGE_URL: [FakeResponse(content=b"ok")],
        }
    )
    scraper, _ = make_scraper(session=session)
    assert scraper.fetch(PAGE_URL).body == b"ok"

    # The other origin's robots.txt was never fetched, and no
    # request anywhere auto-follows redirects.
    assert "https://other.gov/robots.txt" not in session.urls_called()
    assert all(flag is False for _, flag in session.redirect_policy)


def test_redirect_loop_raises():
    bounce = FakeResponse(status_code=302, headers={"Location": PAGE_URL})
    session = FakeSession({PAGE_URL: [bounce] * 4})
    scraper, _ = make_scraper(
        session=session,
        config=ScraperConfig(respect_robots=False, max_redirects=2),
    )
    with pytest.raises(FetchError, match="redirect chain"):
        scraper.fetch(PAGE_URL)


# ---------------------------------------------------------------- fetch: modes


def test_unknown_fetch_mode_raises():
    scraper, _ = make_scraper(
        session=FakeSession({PAGE_URL: [FakeResponse()]})
    )
    with pytest.raises(ScraperError, match="unknown fetch mode"):
        scraper.fetch(PAGE_URL, mode="carrier-pigeon")


def test_playwright_mode_missing_dep_raises_install_hint(monkeypatch):
    # Force the lazy import to fail even when playwright is installed.
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    monkeypatch.setitem(sys.modules, "playwright", None)
    scraper, _ = make_scraper(
        session=FakeSession({PAGE_URL: [FakeResponse()]})
    )
    with pytest.raises(ScraperError, match="pip install playwright"):
        scraper.fetch(PAGE_URL, mode="playwright")


# ---------------------------------------------------------------- base contract


def test_subclass_without_county_raises():
    class Anonymous(CountyRegistrarScraper):
        def scrape(self) -> ScrapeResult:  # pragma: no cover
            return ScrapeResult(county="?")

    with pytest.raises(TypeError, match="county"):
        Anonymous(LocalArtifactStore())


def test_scrape_result_aggregates_counts():
    result = ScrapeResult(
        county="dummy",
        snapshots=(
            SnapshotSummary("2026-03-24", "s1", 3),
            SnapshotSummary("2026-11-03", "s2", 5),
        ),
    )
    assert result.elections_scraped == 2
    assert result.artifacts_written == 8


# ---------------------------------------------------------------- snapshot writer


@pytest.fixture
def store(tmp_path) -> LocalArtifactStore:
    return LocalArtifactStore(base_dir=tmp_path, env="dev")


def writer_scraper(store) -> DummyScraper:
    return DummyScraper(
        store,
        run_id="20260706T120000Z",
        clock=lambda: FIXED_NOW,
        session=FakeSession(),
        sleep=lambda s: None,
    )


def sample_meta(content_type="text/html") -> ArtifactMetadata:
    return ArtifactMetadata(
        source_url="https://example.gov/page",
        content_type=content_type,
        http_status=200,
    )


def test_snapshot_writer_manifest_written_last_with_entries(store):
    scraper = writer_scraper(store)
    writer = scraper.open_snapshot("2026-03-24")

    writer.save_bytes("page.html", b"<html/>", sample_meta())
    # No manifest until finalize — incomplete snapshots stay invisible.
    assert not store.exists(
        county="dummy",
        election_date="2026-03-24",
        snapshot_id=writer.snapshot_id,
        filename="manifest.json",
    )

    writer.save_bytes("analysis.pdf", b"%PDF", sample_meta("application/pdf"))
    writer.finalize()

    manifest = store.get_manifest(
        county="dummy",
        election_date="2026-03-24",
        snapshot_id=writer.snapshot_id,
    )
    assert manifest["schema_version"] == 1
    assert manifest["county"] == "dummy"
    assert manifest["election_date"] == "2026-03-24"
    assert manifest["snapshot_id"] == writer.snapshot_id
    assert manifest["run_id"] == "20260706T120000Z"
    assert manifest["scraper_version"] == DummyScraper.version
    assert manifest["fetch_mode"] == "requests"
    assert [a["filename"] for a in manifest["artifacts"]] == [
        "page.html",
        "analysis.pdf",
    ]
    for entry in manifest["artifacts"]:
        assert entry["sha256"]
        assert entry["size_bytes"] > 0
        assert entry["source_url"] == "https://example.gov/page"


def test_snapshot_writer_save_after_finalize_raises(store):
    writer = writer_scraper(store).open_snapshot("2026-03-24")
    writer.finalize()

    with pytest.raises(ScraperError, match="finalized"):
        writer.save_bytes("late.html", b"x", sample_meta())
    with pytest.raises(ScraperError, match="finalized"):
        writer.finalize()


def test_snapshot_writer_rejects_duplicate_filename(store):
    """A second write would silently invalidate the first entry's
    checksum in the manifest."""
    writer = writer_scraper(store).open_snapshot("2026-03-24")
    writer.save_bytes("page.html", b"first", sample_meta())

    with pytest.raises(ScraperError, match="duplicate filename"):
        writer.save_bytes("page.html", b"second", sample_meta())


def test_snapshot_writer_finalize_extra_cannot_override_core(store):
    writer = writer_scraper(store).open_snapshot("2026-03-24")
    with pytest.raises(ScraperError, match="core manifest fields"):
        writer.finalize(extra={"county": "spoofed", "note": "fine"})


def test_snapshot_writer_finalize_extra_merges_top_level(store):
    writer = writer_scraper(store).open_snapshot("2026-03-24")
    writer.finalize(extra={"source_base_url": "https://example.gov"})

    manifest = store.get_manifest(
        county="dummy",
        election_date="2026-03-24",
        snapshot_id=writer.snapshot_id,
    )
    assert manifest["source_base_url"] == "https://example.gov"


def test_open_snapshot_rejects_completed_snapshot_id(store):
    """Snapshots are immutable: a finalized snapshot's ID can't be
    reopened. Orphans (no manifest) don't block — retry self-heals."""
    scraper = writer_scraper(store)
    first = scraper.open_snapshot("2026-03-24", snapshot_id="snap-x")
    first.finalize()

    with pytest.raises(ScraperError, match="immutable"):
        scraper.open_snapshot("2026-03-24", snapshot_id="snap-x")


def test_open_snapshot_allows_retry_over_orphan(store):
    scraper = writer_scraper(store)
    orphan = scraper.open_snapshot("2026-03-24", snapshot_id="snap-x")
    orphan.save_bytes("page.html", b"crashed run", sample_meta())
    # No finalize — simulates a crash. Same ID can be retried.

    retry = scraper.open_snapshot("2026-03-24", snapshot_id="snap-x")
    retry.save_bytes("page.html", b"healed", sample_meta())
    retry.finalize()

    refs = store.list_artifacts(
        county="dummy", election_date="2026-03-24", snapshot_id="snap-x"
    )
    assert store.get_artifact(refs[0]) == b"healed"


def test_snapshot_writer_save_records_fetch_result_fields(store):
    writer = writer_scraper(store).open_snapshot("2026-03-24")
    result = FetchResult(
        url="https://example.gov/m",
        final_url="https://example.gov/m/",
        http_status=200,
        content_type="text/html",
        body=b"<html>m</html>",
        fetched_at="2026-07-06T11:59:00+00:00",
        fetch_mode="requests",
        etag='"tag"',
    )
    ref = writer.save("page.html", result)
    writer.finalize()

    entry = store.get_manifest(
        county="dummy",
        election_date="2026-03-24",
        snapshot_id=writer.snapshot_id,
    )["artifacts"][0]
    assert entry["fetched_at"] == "2026-07-06T11:59:00+00:00"
    assert entry["final_url"] == "https://example.gov/m/"
    assert entry["etag"] == '"tag"'
    assert entry["sha256"] == ref.sha256
    assert store.get_artifact(ref) == b"<html>m</html>"


def test_open_snapshot_id_from_injected_clock(store):
    writer = writer_scraper(store).open_snapshot("2026-03-24")
    assert writer.snapshot_id == "20260706T120000Z"

    explicit = writer_scraper(store).open_snapshot(
        "2026-03-24", snapshot_id="custom-snap"
    )
    assert explicit.snapshot_id == "custom-snap"


def test_snapshot_writer_summary_counts(store):
    writer = writer_scraper(store).open_snapshot("2026-03-24")
    writer.save_bytes("page.html", b"<html/>", sample_meta())
    writer.finalize()

    assert writer.summary() == SnapshotSummary(
        election_date="2026-03-24",
        snapshot_id="20260706T120000Z",
        artifacts_written=1,
    )


# ---------------------------------------------------------------- noop scraper


def noop_scraper(store, when=FIXED_NOW) -> NoOpCountyScraper:
    return NoOpCountyScraper(
        store,
        run_id="20260706T120000Z",
        clock=lambda: when,
        session=FakeSession(),
        sleep=lambda s: None,
    )


def test_noop_scrape_writes_html_pdf_and_manifest(store):
    result = noop_scraper(store).scrape()

    assert result.county == "noop"
    assert result.elections_scraped == 1
    assert result.artifacts_written == 2

    snapshot_id = result.snapshots[0].snapshot_id
    refs = store.list_artifacts(
        county="noop",
        election_date=FAKE_ELECTION_DATE,
        snapshot_id=snapshot_id,
    )
    by_name = {r.filename: r for r in refs}
    assert set(by_name) == {"page.html", "analysis.pdf"}
    assert store.get_artifact(by_name["page.html"]) == FAKE_HTML
    assert store.get_artifact(by_name["analysis.pdf"]) == FAKE_PDF
    assert by_name["analysis.pdf"].content_type == "application/pdf"


def test_noop_rescrape_creates_new_snapshot_keeps_old(store):
    first = noop_scraper(store).scrape()
    second = noop_scraper(
        store, when=datetime(2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc)
    ).scrape()

    snaps = store.list_snapshots(
        county="noop", election_date=FAKE_ELECTION_DATE
    )
    assert snaps == [
        first.snapshots[0].snapshot_id,
        second.snapshots[0].snapshot_id,
    ]
    # Old snapshot still fully readable — immutability holds.
    old = store.get_manifest(
        county="noop",
        election_date=FAKE_ELECTION_DATE,
        snapshot_id=first.snapshots[0].snapshot_id,
    )
    assert len(old["artifacts"]) == 2


def test_noop_makes_no_network_calls(store):
    session = FakeSession()
    NoOpCountyScraper(
        store,
        clock=lambda: FIXED_NOW,
        session=session,
        sleep=lambda s: None,
    ).scrape()

    assert session.calls == []
