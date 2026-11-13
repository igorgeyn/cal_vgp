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
import re
from datetime import date, datetime, timezone
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


CANONICAL_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Every stored field that means "votes for this measure are in our sources".
VOTE_FIELDS = ("percent_yes", "percent_no", "yes_votes", "no_votes", "total_votes", "pass_fail")


def parse_election_date(value: object) -> Optional[date]:
    """Parse a stored election date written exactly as YYYY-MM-DD.

    Nothing is trimmed or reinterpreted (no ISO week dates), so the browser
    rule, which accepts the same form only, always agrees with this one.
    """
    if not isinstance(value, str) or not CANONICAL_DATE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def has_recorded_votes(measure: MutableMapping) -> bool:
    """True when any vote figure or source outcome code is stored (zero counts)."""
    return any(measure.get(field) not in (None, "") for field in VOTE_FIELDS)


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


def parse_check_time(value: object) -> Optional[datetime]:
    """A recorded check time as an aware UTC instant, or None if unusable."""
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    return moment.astimezone(timezone.utc)


def _validate_check(check: object, kind: str, entry: dict) -> None:
    """Malformed check records stop the build instead of publishing a link."""
    where = f"official results links: {kind} for {entry.get('url')}"
    if not isinstance(check, dict):
        raise ValueError(f"{where} must be an object")
    if parse_check_time(check.get("checked_at")) is None:
        raise ValueError(f"{where} needs a timezone-aware checked_at")
    if not isinstance(check.get("ok"), bool):
        raise ValueError(f"{where} needs a boolean ok")
    if kind == "manual_check":
        if check["ok"] is not True or not check.get("by") or not check.get("observed"):
            raise ValueError(f"{where} must record ok=true, by and observed")
    elif check["ok"] and (check.get("http_status") != 200
                          or check.get("matched_text") != entry.get("expect_text")):
        raise ValueError(f"{where} claims success without status 200 and the expected text")


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
        for kind in ("last_check", "manual_check"):
            if entry.get(kind) is not None:
                _validate_check(entry[kind], kind, entry)
        key = (entry["election_date"], scope, entry.get("county") if scope == "local" else None)
        if key in seen:
            raise ValueError(f"official results links: duplicate entry {key}")
        seen.add(key)
    return entries


def _public_results_link(entry: dict) -> Optional[dict]:
    """Expose a link only when its newest recorded check succeeded.

    Checks are compared as instants, whatever offset they were written in. The
    newest decides, so a later automated failure hides an older manual success;
    a failure at the same instant as a success wins. The exported time is
    canonical UTC (``YYYY-MM-DDTHH:MM:SSZ``).
    """
    checks = []
    for check in (entry.get("last_check"), entry.get("manual_check")):
        moment = parse_check_time((check or {}).get("checked_at"))
        if check and moment is not None:
            checks.append((moment, check.get("ok") is True))
    if not checks:
        return None
    newest_moment = max(moment for moment, _ in checks)
    if not all(ok for moment, ok in checks if moment == newest_moment):
        return None
    return {
        "url": entry["url"],
        "publisher": entry["publisher"],
        "checked_at": newest_moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    Strict builds stop for two data problems, checked separately: a
    current-cycle row (not withdrawn) whose election date is missing or not
    YYYY-MM-DD; and a row outside the current cycle that would read "Results
    pending", meaning a past election with neither votes nor an outcome. A
    future election outside the cycle may read "Upcoming", and stored votes
    without an outcome are "unknown"; neither stops the build.
    """
    links = list(links or [])
    attached = 0
    for measure in measures:
        measure.pop("election_status", None)
        measure.pop("official_results", None)
        current_cycle = bool(measure.get("upcoming_scope")) and measure.get("ballot_status") != "withdrawn"
        if strict and current_cycle and parse_election_date(measure.get("election_date")) is None:
            raise ValueError(
                f"current-cycle measure {measure.get('id')!r} has no usable election_date "
                f"({measure.get('election_date')!r}; expected YYYY-MM-DD)"
            )
        status = election_status(measure, as_of)
        if status not in DATE_DRIVEN_STATUSES:
            continue
        if strict and status == "results_pending" and not current_cycle:
            # A past election with no votes and no outcome is a data gap;
            # "Results pending" would misdescribe it. Make a person look.
            raise ValueError(
                f"measure {measure.get('id')!r} would show 'results_pending' but is not in "
                "the current election cycle; check its election_date and vote data"
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
