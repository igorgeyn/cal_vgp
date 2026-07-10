"""
Base class for county registrar scrapers.

Every county scraper subclasses CountyRegistrarScraper and implements
one method — scrape(). The base class provides the two building
blocks scrape() needs:

- fetch(url): polite HTTP fetch. Project-identifying User-Agent,
  per-domain rate limiting, retries with exponential backoff for
  429/5xx/connection errors (never other 4xx), robots.txt check
  per domain.
  Two fetch modes: "requests" (default) and "playwright" for
  JS-challenged sites (Riverside's Cloudflare wall).
- open_snapshot(election_date): returns a SnapshotWriter that
  accumulates artifacts and writes the snapshot manifest LAST —
  manifest presence signals "snapshot complete", so a crashed run
  never leaves a snapshot that looks finished.

Politeness defaults live in ScraperConfig and are non-negotiable in
spirit: San Diego 403s generic User-Agents (validated 2026-06-08),
and identifying ourselves with a contact is the professional
baseline for hitting county infrastructure on a cron.

See docs/plans/registrar_pipeline_infra.md for design rationale.
"""
from __future__ import annotations

import logging
import math
import time
import urllib.robotparser
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, ClassVar, Optional
from urllib.parse import urljoin, urlparse

import requests

from .storage import (
    ArtifactMetadata,
    ArtifactRef,
    County,
    ElectionDate,
    RawArtifactStore,
    SnapshotID,
)

DEFAULT_USER_AGENT = (
    "cal-vgp-registrar-scraper/0.1 "
    "(+https://github.com/igorgeyn/cal_vgp; "
    "contact: igorgeyn@gmail.com)"
)

SNAPSHOT_ID_FORMAT = "%Y%m%dT%H%M%SZ"  # matches storage.py recommendation

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class ScraperError(Exception):
    """Base error for scraper failures. The runner's per-county
    isolation boundary catches this (and any other Exception) to
    record a failed county without aborting the run."""


class FetchError(ScraperError):
    """A fetch failed terminally: 4xx response, or retries exhausted
    on 5xx/connection errors."""

    def __init__(
        self,
        message: str,
        *,
        url: str,
        http_status: Optional[int] = None,
    ):
        super().__init__(message)
        self.url = url
        self.http_status = http_status


class RobotsDisallowedError(FetchError):
    """robots.txt disallows this URL for our User-Agent. Callers
    should log and skip, not retry."""


@dataclass(frozen=True)
class ScraperConfig:
    """Polite-scraping defaults. Tune per county by passing a
    replacement config; don't loosen the spirit (identify ourselves,
    don't hammer)."""

    user_agent: str = DEFAULT_USER_AGENT
    rate_limit_seconds: float = 2.0     # min interval between requests, per domain
    timeout_seconds: float = 30.0
    max_retries: int = 3                # attempts for 429/5xx/connection errors
    backoff_base_seconds: float = 2.0   # 2s, 4s, 8s...
    respect_robots: bool = True
    max_redirects: int = 10             # manual redirect chain limit
    retry_after_cap_seconds: float = 300.0  # ceiling on honored Retry-After


@dataclass(frozen=True)
class FetchResult:
    """One successful fetch. Bridges into the storage layer via
    to_metadata(); pass the whole result to SnapshotWriter.save()."""

    url: str
    final_url: str
    http_status: int
    content_type: str
    body: bytes
    fetched_at: str             # ISO 8601 UTC
    fetch_mode: str             # "requests" or "playwright"
    etag: Optional[str] = None
    last_modified: Optional[str] = None

    def to_metadata(self) -> ArtifactMetadata:
        return ArtifactMetadata(
            source_url=self.url,
            content_type=self.content_type,
            http_status=self.http_status,
            final_url=self.final_url,
            etag=self.etag,
            last_modified=self.last_modified,
            fetch_mode=self.fetch_mode,
        )


@dataclass(frozen=True)
class SnapshotSummary:
    """Per-snapshot slice of a ScrapeResult; feeds the run manifest."""

    election_date: ElectionDate
    snapshot_id: SnapshotID
    artifacts_written: int


@dataclass(frozen=True)
class ScrapeResult:
    """Returned by scrape(). The runner aggregates these into the
    run-level manifest."""

    county: County
    snapshots: tuple[SnapshotSummary, ...] = ()

    @property
    def elections_scraped(self) -> int:
        return len(self.snapshots)

    @property
    def artifacts_written(self) -> int:
        return sum(s.artifacts_written for s in self.snapshots)


class SnapshotWriter:
    """Accumulates artifacts for one (county, election_date,
    snapshot_id) and writes the snapshot manifest on finalize().

    Manifest-last is enforced structurally: save() after finalize()
    raises, and the manifest only ever contains artifacts that were
    actually written. A snapshot without a manifest is by definition
    incomplete and gets ignored by downstream parsers.

    Created via CountyRegistrarScraper.open_snapshot(); not
    constructed directly by county scrapers.
    """

    def __init__(
        self,
        *,
        store: RawArtifactStore,
        county: County,
        election_date: ElectionDate,
        snapshot_id: SnapshotID,
        run_id: str,
        scraper_version: str,
        fetch_mode: str,
        clock: Callable[[], datetime],
    ):
        self._store = store
        self.county = county
        self.election_date = election_date
        self.snapshot_id = snapshot_id
        self._run_id = run_id
        self._scraper_version = scraper_version
        self._fetch_mode = fetch_mode
        self._clock = clock
        self._entries: list[dict] = []
        self._filenames: set[str] = set()
        self._finalized = False

    def save(self, filename: str, result: FetchResult) -> ArtifactRef:
        """Store a fetched artifact and record its manifest entry."""
        return self.save_bytes(
            filename,
            result.body,
            result.to_metadata(),
            fetched_at=result.fetched_at,
        )

    def save_bytes(
        self,
        filename: str,
        body: bytes,
        metadata: ArtifactMetadata,
        *,
        fetched_at: Optional[str] = None,
    ) -> ArtifactRef:
        """Store raw bytes with caller-built metadata. For content
        that didn't come through fetch() (derived files, test
        fixtures, Playwright screenshots)."""
        if self._finalized:
            raise ScraperError(
                f"snapshot {self.county}/{self.election_date}/"
                f"{self.snapshot_id} already finalized; cannot add "
                f"{filename}"
            )
        if filename in self._filenames:
            # A second write would silently invalidate the first
            # entry's checksum in the manifest (Codex round-2).
            raise ScraperError(
                f"duplicate filename in snapshot "
                f"{self.county}/{self.election_date}/{self.snapshot_id}: "
                f"{filename}"
            )
        ref = self._store.put_artifact(
            county=self.county,
            election_date=self.election_date,
            snapshot_id=self.snapshot_id,
            filename=filename,
            body=body,
            metadata=metadata,
        )
        self._entries.append(
            {
                "filename": filename,
                "source_url": metadata.source_url,
                "final_url": metadata.final_url,
                "http_status": metadata.http_status,
                "content_type": metadata.content_type,
                "etag": metadata.etag,
                "last_modified": metadata.last_modified,
                "fetch_mode": metadata.fetch_mode,
                "fetched_at": fetched_at or _iso_now(self._clock),
                "sha256": ref.sha256,
                "size_bytes": ref.size_bytes,
            }
        )
        self._filenames.add(filename)
        return ref

    def finalize(self, extra: Optional[dict] = None) -> str:
        """Write the snapshot manifest. Call exactly once, after all
        artifacts are saved. `extra` merges scraper-specific fields
        (e.g. source_base_url) into the manifest top level."""
        if self._finalized:
            raise ScraperError(
                f"snapshot {self.county}/{self.election_date}/"
                f"{self.snapshot_id} already finalized"
            )
        manifest = {
            "schema_version": 1,
            "county": self.county,
            "election_date": self.election_date,
            "snapshot_id": self.snapshot_id,
            "run_id": self._run_id,
            "scraped_at": _iso_now(self._clock),
            "scraper_version": self._scraper_version,
            "fetch_mode": self._fetch_mode,
            "artifacts": self._entries,
        }
        if extra:
            clash = manifest.keys() & extra.keys()
            if clash:
                raise ScraperError(
                    "finalize(extra=...) cannot override core manifest "
                    f"fields: {sorted(clash)}"
                )
            manifest.update(extra)
        uri = self._store.put_manifest(
            county=self.county,
            election_date=self.election_date,
            snapshot_id=self.snapshot_id,
            manifest=manifest,
        )
        self._finalized = True
        return uri

    def summary(self) -> SnapshotSummary:
        return SnapshotSummary(
            election_date=self.election_date,
            snapshot_id=self.snapshot_id,
            artifacts_written=len(self._entries),
        )


class CountyRegistrarScraper(ABC):
    """Abstract base for per-county registrar scrapers.

    Subclasses set `county` (short slug) and implement scrape().
    Everything else — polite fetching, snapshot bookkeeping — is
    provided. Raise ScraperError (or let FetchError propagate) on
    failure; the runner isolates per-county failures.

    Constructor injection (clock, session, sleep) exists for tests;
    production callers pass only (store, run_id).
    """

    county: ClassVar[County]
    fetch_mode: ClassVar[str] = "requests"  # or "playwright"
    version: ClassVar[str] = "0.1.0"

    def __init__(
        self,
        store: RawArtifactStore,
        *,
        config: Optional[ScraperConfig] = None,
        run_id: Optional[str] = None,
        clock: Optional[Callable[[], datetime]] = None,
        session: Optional[requests.Session] = None,
        sleep: Optional[Callable[[float], None]] = None,
        monotonic: Optional[Callable[[], float]] = None,
    ):
        if not getattr(self, "county", None):
            raise TypeError(
                f"{type(self).__name__} must define a `county` class attribute"
            )
        self._store = store
        self.config = config or ScraperConfig()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._run_id = run_id or self._clock().strftime(SNAPSHOT_ID_FORMAT)
        self._session = session or requests.Session()
        self._sleep = sleep or time.sleep
        self._monotonic = monotonic or time.monotonic
        self._last_request_at: dict[str, float] = {}  # domain -> monotonic secs
        # origin -> parser, or None when robots.txt is unfetchable (= allow)
        self._robots: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        self._log = logging.getLogger(f"registrar.{self.county}")

    # ------------------------------------------------------------ abstract

    @abstractmethod
    def scrape(self) -> ScrapeResult:
        """Fetch this county's measure pages/PDFs, save them via
        open_snapshot()/SnapshotWriter, and return counts."""
        ...

    # ------------------------------------------------------------ snapshots

    def open_snapshot(
        self,
        election_date: ElectionDate,
        *,
        snapshot_id: Optional[SnapshotID] = None,
    ) -> SnapshotWriter:
        """Start a new immutable snapshot for one election. The
        snapshot_id defaults to the current UTC timestamp; re-scrapes
        of the same election get fresh IDs, never overwrite.

        Raises ScraperError if a COMPLETE snapshot (manifest
        written) already exists under this ID. Orphan artifacts from
        a crashed earlier attempt don't block — retrying with the
        same ID overwrites them, which is the desired self-heal."""
        sid = snapshot_id or self._new_snapshot_id()
        if self._store.exists(
            county=self.county,
            election_date=election_date,
            snapshot_id=sid,
        ):
            raise ScraperError(
                f"snapshot {self.county}/{election_date}/{sid} already "
                "exists and snapshots are immutable; use a fresh "
                "snapshot_id to re-scrape"
            )
        return SnapshotWriter(
            store=self._store,
            county=self.county,
            election_date=election_date,
            snapshot_id=sid,
            run_id=self._run_id,
            scraper_version=self.version,
            fetch_mode=self.fetch_mode,
            clock=self._clock,
        )

    def _new_snapshot_id(self) -> SnapshotID:
        return self._clock().strftime(SNAPSHOT_ID_FORMAT)

    # ------------------------------------------------------------ fetching

    def fetch(self, url: str, *, mode: Optional[str] = None) -> FetchResult:
        """Polite fetch via the given mode (default: the class's
        fetch_mode). Per-call mode override supports mixed counties
        — e.g. Playwright for Riverside's pages but plain requests
        for its PDFs.

        Politeness applies per actual HTTP request: every attempt
        (including retries and each manually-followed redirect hop)
        gets its own robots.txt check and per-domain rate-limit
        wait, so a redirect onto a different origin cannot bypass
        that origin's rules (Codex round-2)."""
        mode = mode or self.fetch_mode
        if mode == "playwright":
            # Browser handles redirects internally; robots + rate
            # limit apply to the navigation as a whole.
            self._check_robots(url)
            self._rate_limit(url)
            return self._fetch_playwright(url)
        if mode == "requests":
            return self._fetch_requests(url)
        raise ScraperError(f"unknown fetch mode: {mode!r}")

    def _check_robots(self, url: str) -> None:
        if self.config.respect_robots and not self._robots_allowed(url):
            self._log.info("robots.txt disallows %s; skipping", url)
            raise RobotsDisallowedError(
                f"robots.txt disallows {url} for our User-Agent", url=url
            )

    def _fetch_requests(self, url: str) -> FetchResult:
        """Fetch with manual redirect following so each hop — even
        onto a different origin — passes its own robots check and
        rate limit."""
        current = url
        for _hop in range(self.config.max_redirects + 1):
            resp = self._request_with_retries(current)
            location = resp.headers.get("Location")
            if resp.status_code in _REDIRECT_STATUSES and location:
                current = urljoin(current, location)
                continue
            return self._result_from_response(url, resp)
        raise FetchError(
            f"redirect chain from {url} exceeded "
            f"{self.config.max_redirects} hops",
            url=url,
        )

    def _request_with_retries(self, url: str) -> requests.Response:
        """One URL, polite: robots check, then per-attempt rate
        limit, retrying 429/5xx/connection errors with backoff
        (honoring Retry-After) and never retrying other 4xx."""
        self._check_robots(url)
        attempts = self.config.max_retries
        last_error: Optional[BaseException] = None
        for attempt in range(attempts):
            self._rate_limit(url)
            try:
                resp = self._session.get(
                    url,
                    headers={"User-Agent": self.config.user_agent},
                    timeout=self.config.timeout_seconds,
                    allow_redirects=False,
                )
            except requests.RequestException as e:
                last_error = e
                self._log.warning(
                    "fetch attempt %d/%d failed for %s: %s",
                    attempt + 1, attempts, url, e,
                )
                if attempt < attempts - 1:
                    self._backoff(attempt)
                continue

            # 429 is the site telling us to slow down — backing off
            # and retrying IS the polite response, unlike other 4xx.
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                last_error = FetchError(
                    f"HTTP {resp.status_code} from {url}",
                    url=url,
                    http_status=resp.status_code,
                )
                self._log.warning(
                    "fetch attempt %d/%d got HTTP %d for %s",
                    attempt + 1, attempts, resp.status_code, url,
                )
                if attempt < attempts - 1:
                    self._sleep(self._retry_delay(resp, attempt))
                continue

            if resp.status_code >= 400:
                # Other 4xx is a programming/permission problem, not
                # transient — retrying would just hammer the site.
                raise FetchError(
                    f"HTTP {resp.status_code} from {url} (not retried)",
                    url=url,
                    http_status=resp.status_code,
                )

            return resp

        if isinstance(last_error, FetchError):
            raise last_error
        raise FetchError(
            f"fetch failed after {attempts} attempts: {last_error}",
            url=url,
        ) from last_error

    def _retry_delay(self, resp: requests.Response, attempt: int) -> float:
        """Server-provided Retry-After (delta-seconds or HTTP-date)
        when present and sane, else exponential backoff. Capped so a
        misconfigured header can't stall the run."""
        backoff = self.config.backoff_base_seconds * (2 ** attempt)
        header = (resp.headers.get("Retry-After") or "").strip()
        if not header:
            return backoff
        try:
            delay = float(header)
        except ValueError:
            try:
                when = parsedate_to_datetime(header)
            except (TypeError, ValueError):
                return backoff
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            delay = (when - self._clock()).total_seconds()
        if not math.isfinite(delay):
            return backoff
        return min(max(delay, 0.0), self.config.retry_after_cap_seconds)

    def _result_from_response(
        self, url: str, resp: requests.Response
    ) -> FetchResult:
        body = resp.content
        content_type = (
            resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        )
        # Logs carry URL + status + size only — never body content
        # (registrar PDFs can hold signer addresses etc.).
        self._log.info(
            "GET %s -> %d (%d bytes, %s)",
            url, resp.status_code, len(body), content_type or "no content-type",
        )
        return FetchResult(
            url=url,
            final_url=resp.url,
            http_status=resp.status_code,
            content_type=content_type,
            body=body,
            fetched_at=_iso_now(self._clock),
            fetch_mode="requests",
            etag=resp.headers.get("ETag"),
            last_modified=resp.headers.get("Last-Modified"),
        )

    def _fetch_playwright(self, url: str) -> FetchResult:
        """Fetch via headless Chromium for JS-challenged sites. The
        rendered DOM is the artifact — raw HTTP HTML is useless for
        these pages. Single attempt; browser-level retry semantics
        get designed when Riverside lands in Phase 1."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise ScraperError(
                "playwright fetch mode requires the playwright package: "
                "pip install playwright && playwright install chromium"
            ) from e

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=self.config.user_agent)
                resp = page.goto(
                    url,
                    timeout=self.config.timeout_seconds * 1000,
                    wait_until="networkidle",
                )
                if resp is None:
                    # goto() returns None for same-URL/anchor
                    # navigations — never a successful fetch here.
                    raise FetchError(
                        f"playwright navigation to {url} produced no "
                        "response",
                        url=url,
                    )
                http_status = resp.status
                final_url = page.url
                body = page.content().encode("utf-8")
            finally:
                browser.close()

        if http_status >= 400:
            raise FetchError(
                f"HTTP {http_status} from {url} (playwright)",
                url=url,
                http_status=http_status,
            )
        self._log.info(
            "GET %s -> %d (%d bytes, playwright-rendered)",
            url, http_status, len(body),
        )
        return FetchResult(
            url=url,
            final_url=final_url,
            http_status=http_status,
            content_type="text/html",
            body=body,
            fetched_at=_iso_now(self._clock),
            fetch_mode="playwright",
        )

    def _backoff(self, attempt: int) -> None:
        self._sleep(self.config.backoff_base_seconds * (2 ** attempt))

    # ------------------------------------------------------------ politeness

    def _rate_limit(self, url: str) -> None:
        domain = urlparse(url).netloc
        last = self._last_request_at.get(domain)
        if last is not None:
            wait = self.config.rate_limit_seconds - (self._monotonic() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_request_at[domain] = self._monotonic()

    def _robots_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)
        parser = self._robots[origin]
        if parser is None:
            # Unfetchable robots.txt (404, timeout, etc.) — standard
            # convention is "allowed".
            return True
        return parser.can_fetch(self.config.user_agent, url)

    def _load_robots(
        self, origin: str
    ) -> Optional[urllib.robotparser.RobotFileParser]:
        robots_url = f"{origin}/robots.txt"
        # The robots fetch is itself a request to the domain — it
        # participates in the rate limit like any other.
        self._rate_limit(robots_url)
        try:
            resp = self._session.get(
                robots_url,
                headers={"User-Agent": self.config.user_agent},
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as e:
            self._log.info("robots.txt unfetchable for %s (%s)", origin, e)
            return None
        if resp.status_code >= 400:
            self._log.info(
                "robots.txt returned %d for %s", resp.status_code, origin
            )
            return None
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(resp.text.splitlines())
        return parser


def _iso_now(clock: Callable[[], datetime]) -> str:
    return clock().isoformat()
