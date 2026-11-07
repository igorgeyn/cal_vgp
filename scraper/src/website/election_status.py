"""One election-status contract for every site surface.

The status of a measure without a recorded outcome depends on its election
date and the date in California, never on its year alone. Build-time code
(``measures-data.json`` and the static measure pages) evaluates the rule for an
explicit ``as_of`` date. The explorer re-evaluates the date-driven part with the
reader's clock, moving a status forward only, so a site that is not rebuilt on
election day still stops saying "Upcoming" (the October 2026 failure).

Statuses:

``upcoming``         before election day (Pacific)
``election_day``     on election day (Pacific)
``results_pending``  after election day, with no outcome recorded by CalBallot
``passed``/``failed`` an outcome recorded in our sources
``withdrawn``        removed from the ballot
``unknown``          votes stored without a normalized outcome, or no usable
                     election date

"Results pending" says only that CalBallot has not recorded a result. It makes
no claim about whether the county is still counting or has certified.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, MutableMapping, Optional
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")

# Statuses whose value changes with the calendar, in the only order allowed.
DATE_DRIVEN_STATUSES = ("upcoming", "election_day", "results_pending")

STATUS_LABELS = {
    "upcoming": "Upcoming",
    "election_day": "Election day",
    "results_pending": "Results pending",
    "passed": "Passed",
    "failed": "Failed",
    "withdrawn": "Withdrawn",
    "unknown": "Result unknown",
}

OFFICIAL_RESULTS_PATH = Path(__file__).with_name("data") / "official_results_links.json"


def pacific_date(moment: datetime) -> date:
    """Return the California calendar date of an aware datetime."""
    if moment.tzinfo is None:
        raise ValueError("pacific_date needs a timezone-aware datetime")
    return moment.astimezone(PACIFIC).date()


def today_in_pacific() -> date:
    return pacific_date(datetime.now(PACIFIC))


def parse_election_date(value: object) -> Optional[date]:
    """Parse a stored ISO election date; anything else is no date at all."""
    text = str(value or "").strip()
    if len(text) != 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def has_recorded_votes(measure: MutableMapping) -> bool:
    """True when any vote figure or source outcome code is stored for the row."""
    return any(measure.get(field) not in (None, "") for field in
               ("percent_yes", "yes_votes", "no_votes", "total_votes", "pass_fail"))


def date_status(election_date: date, as_of: date) -> str:
    if as_of < election_date:
        return "upcoming"
    if as_of == election_date:
        return "election_day"
    return "results_pending"


def election_status(measure: MutableMapping, as_of: date) -> str:
    """Status of one measure on the Pacific date ``as_of``."""
    if measure.get("ballot_status") == "withdrawn":
        return "withdrawn"
    if measure.get("passed") == 1:
        return "passed"
    if measure.get("passed") == 0:
        return "failed"
    if has_recorded_votes(measure):
        # Votes are in our sources but no normalized outcome is (e.g. 48 CEDA
        # 2011 rows with percent_yes and pass_fail but passed NULL). That is a
        # data gap, not a pending election.
        return "unknown"
    election_date = parse_election_date(measure.get("election_date"))
    if election_date is None:
        return "unknown"
    return date_status(election_date, as_of)


def format_election_date(value: object) -> str:
    parsed = parse_election_date(value)
    return f"{parsed:%B} {parsed.day}, {parsed.year}" if parsed else ""


def format_checked_date(value: object) -> str:
    """California date of a recorded UTC check time, e.g. "November 7, 2026"."""
    text = str(value or "").strip()
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if moment.tzinfo is None:
        return ""
    local = pacific_date(moment)
    return f"{local:%B} {local.day}, {local.year}"


def status_sentence(status: str, election_date: object) -> str:
    """Plain sentence for static pages and meta descriptions."""
    when = format_election_date(election_date)
    if status == "upcoming":
        return f"On the ballot {when}." if when else "Upcoming election."
    if status == "election_day":
        return f"Election day: {when}." if when else "Election day."
    if status == "results_pending":
        voted = f"Voted {when}. " if when else ""
        return f"{voted}CalBallot has not recorded the result yet."
    return ""


def load_official_results(path: Path = OFFICIAL_RESULTS_PATH) -> list[dict]:
    """Load reviewed official-results links; malformed entries stop the build."""
    if not Path(path).exists():
        return []
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("official results links: unsupported schema_version")
    entries = payload.get("links")
    if not isinstance(entries, list):
        raise ValueError("official results links: 'links' must be a list")
    seen = set()
    for entry in entries:
        scope = entry.get("scope")
        if scope not in ("statewide", "local"):
            raise ValueError(f"official results links: bad scope {scope!r}")
        if parse_election_date(entry.get("election_date")) is None:
            raise ValueError(f"official results links: bad election_date in {entry!r}")
        if scope == "local" and not str(entry.get("county") or "").strip():
            raise ValueError("official results links: local entries need a county")
        url = str(entry.get("url") or "")
        if urlsplit(url).scheme != "https" or not urlsplit(url).netloc:
            raise ValueError(f"official results links: URL must be https: {url!r}")
        if not str(entry.get("publisher") or "").strip():
            raise ValueError(f"official results links: publisher missing for {url}")
        if not str(entry.get("expect_text") or "").strip():
            raise ValueError(f"official results links: expect_text missing for {url}")
        manual = entry.get("manual_check")
        if manual is not None and not (
            manual.get("ok") is True and manual.get("checked_at") and manual.get("by")
            and manual.get("observed")
        ):
            raise ValueError(f"official results links: incomplete manual_check for {url}")
        key = (entry["election_date"], scope, entry.get("county") if scope == "local" else None)
        if key in seen:
            raise ValueError(f"official results links: duplicate entry {key}")
        seen.add(key)
    return entries


def _public_results_link(entry: dict) -> Optional[dict]:
    """Expose a link only when its newest recorded check succeeded.

    The newest of the automated ``last_check`` and a person's ``manual_check``
    decides, so a later automated failure hides an older manual success.
    """
    checks = [check for check in (entry.get("last_check"), entry.get("manual_check"))
              if check and check.get("checked_at")]
    if not checks:
        return None
    newest = max(checks, key=lambda check: check["checked_at"])
    if newest.get("ok") is not True:
        return None
    return {
        "url": entry["url"],
        "publisher": entry["publisher"],
        "checked_at": newest["checked_at"],
    }


def results_link_for(measure: MutableMapping, links: Iterable[dict]) -> Optional[dict]:
    election_date = str(measure.get("election_date") or "")
    county = str(measure.get("county") or "").strip()
    statewide = not county or county.casefold() == "statewide"
    for entry in links:
        if entry["election_date"] != election_date:
            continue
        if statewide and entry["scope"] == "statewide":
            return _public_results_link(entry)
        if not statewide and entry["scope"] == "local" and entry["county"].casefold() == county.casefold():
            return _public_results_link(entry)
    return None


def attach_election_status(
    measures: Iterable[MutableMapping],
    *,
    as_of: date,
    links: Optional[Iterable[dict]] = None,
    strict: bool = False,
) -> int:
    """Attach ``election_status`` (and a checked results link) to current rows.

    Only rows whose status depends on the calendar gain fields, so historical
    records and their static pages are unchanged. Returns the count attached.
    In strict mode a current-cycle row without a usable election date stops
    the build rather than silently becoming "unknown".
    """
    links = list(links or [])
    attached = 0
    for measure in measures:
        measure.pop("election_status", None)
        measure.pop("official_results", None)
        status = election_status(measure, as_of)
        if status == "unknown" and strict and measure.get("upcoming_scope"):
            raise ValueError(
                f"current-cycle measure {measure.get('id')!r} has no usable election_date"
            )
        if status not in DATE_DRIVEN_STATUSES:
            continue
        if strict and not measure.get("upcoming_scope"):
            # An older row with a date but no votes is a data gap; "Results
            # pending" would misdescribe it. Make a person look.
            raise ValueError(
                f"measure {measure.get('id')!r} would show {status!r} but is not in the "
                "current election cycle; check its election_date and vote data"
            )
        measure["election_status"] = status
        link = results_link_for(measure, links)
        if link:
            measure["official_results"] = link
        attached += 1
    return attached


# Browser half of the contract. It must agree with ``election_status`` above;
# tests run both over the same date matrix. ``today`` is injectable for tests.
ELECTION_STATUS_SCRIPT = r"""
        const DATE_DRIVEN_STATUSES = ['upcoming', 'election_day', 'results_pending'];
        const ELECTION_STATUS_LABELS = {
            upcoming: 'Upcoming',
            election_day: 'Election day',
            results_pending: 'Results pending',
            passed: 'Passed',
            failed: 'Failed',
            withdrawn: 'Withdrawn',
            unknown: 'Result unknown'
        };

        function pacificToday() {
            try {
                const parts = new Intl.DateTimeFormat('en-US', {
                    timeZone: 'America/Los_Angeles', year: 'numeric', month: '2-digit', day: '2-digit'
                }).formatToParts(new Date());
                const value = type => parts.find(part => part.type === type).value;
                return `${value('year')}-${value('month')}-${value('day')}`;
            } catch (error) {
                return null;
            }
        }

        function getElectionStatus(measure, today = pacificToday()) {
            if (!measure) return 'unknown';
            if (measure.ballot_status === 'withdrawn') return 'withdrawn';
            if (measure.passed === 1) return 'passed';
            if (measure.passed === 0) return 'failed';
            const built = measure.election_status;
            if (!DATE_DRIVEN_STATUSES.includes(built)) return 'unknown';
            const electionDate = /^\d{4}-\d{2}-\d{2}$/.test(measure.election_date || '') ? measure.election_date : null;
            if (!electionDate || !/^\d{4}-\d{2}-\d{2}$/.test(today || '')) return built;
            const byDate = today < electionDate ? 'upcoming' : (today === electionDate ? 'election_day' : 'results_pending');
            // The reader's clock may only move a status forward from the build.
            return DATE_DRIVEN_STATUSES.indexOf(byDate) > DATE_DRIVEN_STATUSES.indexOf(built) ? byDate : built;
        }

        function getElectionStatusLabel(status) {
            return ELECTION_STATUS_LABELS[status] || ELECTION_STATUS_LABELS.unknown;
        }

        function formatElectionDate(value) {
            const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || '');
            if (!match) return '';
            const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
                            'August', 'September', 'October', 'November', 'December'];
            return `${months[Number(match[2]) - 1]} ${Number(match[3])}, ${match[1]}`;
        }
"""
