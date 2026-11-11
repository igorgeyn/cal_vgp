"""One election-status contract: Python rule, browser rule, links and pages."""

import importlib.util
import json
import shutil
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.website.election_status import (
    DATE_DRIVEN_STATUSES,
    VOTE_FIELDS,
    ELECTION_STATUS_SCRIPT,
    attach_election_status,
    election_status,
    format_checked_date,
    load_official_results,
    pacific_date,
    parse_election_date,
    results_link_for,
    status_sentence,
)

ELECTION = "2026-11-03"
REPO = Path(__file__).resolve().parents[2]

spec = importlib.util.spec_from_file_location("measure_pages", REPO / "build_measure_pages.py")
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


def current(**extra):
    return {"id": 1, "year": 2026, "county": "San Mateo", "election_date": ELECTION,
            "upcoming_scope": "local", "passed": None, **extra}


@pytest.mark.parametrize("as_of, expected", [
    ("2026-11-02", "upcoming"),
    ("2026-11-03", "election_day"),
    ("2026-11-04", "results_pending"),
    ("2026-12-31", "results_pending"),
    ("2027-01-01", "results_pending"),  # the year rolling over changes nothing
])
def test_status_follows_the_election_date(as_of, expected):
    assert election_status(current(), date.fromisoformat(as_of)) == expected


def test_pacific_midnight_is_the_boundary_not_utc_midnight():
    # PST (UTC-8) applies on November 3-4, 2026.
    late_election_night = datetime(2026, 11, 4, 7, 59, tzinfo=timezone.utc)
    after_midnight = datetime(2026, 11, 4, 8, 0, tzinfo=timezone.utc)
    assert pacific_date(late_election_night) == date(2026, 11, 3)
    assert pacific_date(after_midnight) == date(2026, 11, 4)
    assert election_status(current(), pacific_date(late_election_night)) == "election_day"
    assert election_status(current(), pacific_date(after_midnight)) == "results_pending"
    with pytest.raises(ValueError):
        pacific_date(datetime(2026, 11, 4, 8, 0))


def test_recorded_outcomes_and_withdrawal_take_precedence_over_dates():
    as_of = date(2026, 11, 1)
    assert election_status(current(passed=1), as_of) == "passed"
    assert election_status(current(passed=0), as_of) == "failed"
    assert election_status(current(ballot_status="withdrawn", passed=1), as_of) == "withdrawn"


STORED_VOTES = [(field, value) for field in VOTE_FIELDS
                for value in (("PassT",) if field == "pass_fail" else (40.0, 0))]


def test_vote_fields_cover_every_stored_vote_column():
    assert set(VOTE_FIELDS) == {"percent_yes", "percent_no", "yes_votes", "no_votes", "total_votes", "pass_fail"}


@pytest.mark.parametrize("field, value", STORED_VOTES)
def test_stored_votes_without_an_outcome_are_unknown_not_pending(field, value):
    # 48 CEDA 2011 rows carry percent_yes and pass_fail with passed NULL.
    row = current(election_date="2011-03-08", **{field: value})
    assert election_status(row, date(2026, 11, 7)) == "unknown"


@pytest.mark.parametrize("field, value", STORED_VOTES)
def test_current_row_with_stored_votes_is_unknown_and_does_not_stop_a_strict_build(field, value):
    # Review R2: a valid date must not be reported as missing.
    row = current(**{field: value})
    assert attach_election_status([row], as_of=date(2026, 11, 7), strict=True) == 0
    assert "election_status" not in row


def test_future_election_outside_the_current_cycle_may_be_upcoming():
    # Review Q5: only a past election with no data is a strict-build error.
    future = {"id": 11, "year": 2028, "county": "Statewide", "election_date": "2028-11-07", "passed": None}
    assert attach_election_status([future], as_of=date(2026, 11, 7), strict=True) == 1
    assert future["election_status"] == "upcoming"


def test_strict_build_refuses_pending_status_outside_the_current_cycle():
    old_gap = {"id": 8, "year": 2016, "county": "Kern", "election_date": "2016-11-08", "passed": None}
    with pytest.raises(ValueError, match="not in the current election cycle"):
        attach_election_status([old_gap], as_of=date(2026, 11, 7), strict=True)


@pytest.mark.parametrize("value", [None, "", "2026", "2026-13-01", "11/03/2026", "2026-11-03T00:00"])
def test_unusable_dates_are_unknown_never_inferred_from_the_year(value):
    assert parse_election_date(value) is None
    assert election_status(current(election_date=value), date(2026, 11, 7)) == "unknown"


def test_only_calendar_dependent_rows_gain_fields():
    historical = {"id": 2, "year": 2024, "county": "San Mateo", "election_date": "2024-11-05", "passed": 1}
    unknown_old = {"id": 3, "year": 1911, "county": "Statewide", "passed": None}
    withdrawn = {"id": 4, "year": 2026, "county": "Statewide", "ballot_status": "withdrawn",
                 "upcoming_scope": "statewide"}
    rows = [current(), historical, unknown_old, withdrawn]
    assert attach_election_status(rows, as_of=date(2026, 11, 7)) == 1
    assert rows[0]["election_status"] == "results_pending"
    for row in rows[1:]:
        assert "election_status" not in row and "official_results" not in row


@pytest.mark.parametrize("value", [" 2026-11-03 ", "2026-W45-2", "20261103"])
def test_strict_build_refuses_a_current_row_with_a_noncanonical_date(value):
    # Review R5: the browser cannot advance such dates, so neither half accepts them.
    with pytest.raises(ValueError, match="expected YYYY-MM-DD"):
        attach_election_status([current(election_date=value)], as_of=date(2026, 11, 7), strict=True)


def test_withdrawn_current_row_needs_no_date():
    row = current(election_date=None, ballot_status="withdrawn")
    assert attach_election_status([row], as_of=date(2026, 11, 7), strict=True) == 0


def test_strict_build_refuses_a_current_row_without_a_date():
    rows = [current(election_date=None)]
    with pytest.raises(ValueError, match="no usable election_date"):
        attach_election_status(rows, as_of=date(2026, 11, 7), strict=True)
    attach_election_status(rows, as_of=date(2026, 11, 7))
    assert "election_status" not in rows[0]


def test_reattaching_replaces_stale_fields():
    row = current(election_status="upcoming", official_results={"url": "https://old.example"})
    attach_election_status([row], as_of=date(2026, 11, 7))
    assert row["election_status"] == "results_pending"
    assert "official_results" not in row


def link(**extra):
    entry = {"election_date": ELECTION, "scope": "local", "county": "San Mateo",
             "publisher": "San Mateo County Elections", "url": "https://results.example.gov/2026",
             "expect_text": "November 3, 2026"}
    entry.update(extra)
    return entry


def write_links(tmp_path, entries):
    path = tmp_path / "links.json"
    path.write_text(json.dumps({"schema_version": 1, "links": entries}), encoding="utf-8")
    return path


@pytest.mark.parametrize("bad", [
    {"url": "http://results.example.gov/2026"},
    {"expect_text": ""},
    {"scope": "regional"},
    {"county": ""},
    {"election_date": "November 3"},
    {"manual_check": {"checked_at": "2026-11-07T17:00:00Z", "ok": True}},
])
def test_malformed_links_stop_the_build(tmp_path, bad):
    with pytest.raises(ValueError):
        load_official_results(write_links(tmp_path, [link(**bad)]))


@pytest.mark.parametrize("bad_check", [
    {"checked_at": "not a time", "ok": True, "http_status": 200, "matched_text": "November 3, 2026"},
    {"checked_at": "2026-11-07T16:10:18", "ok": True, "http_status": 200, "matched_text": "November 3, 2026"},
    {"checked_at": "2026-11-07T16:10:18Z", "ok": "yes", "http_status": 200, "matched_text": "November 3, 2026"},
    {"checked_at": "2026-11-07T16:10:18Z", "ok": True, "http_status": 500, "matched_text": "November 3, 2026"},
    {"checked_at": "2026-11-07T16:10:18Z", "ok": True, "http_status": 200},
    {"checked_at": "2026-11-07T16:10:18Z", "ok": True, "http_status": 200, "matched_text": "other"},
    "ok",
])
def test_malformed_automated_checks_stop_the_build(tmp_path, bad_check):
    # Review R3: no link may be exported on the strength of a malformed check.
    with pytest.raises(ValueError):
        load_official_results(write_links(tmp_path, [link(last_check=bad_check)]))


@pytest.mark.parametrize("bad_manual", [
    {"checked_at": "2026-11-07T17:00:00Z", "ok": False, "by": "Igor", "observed": "x"},
    {"checked_at": "yesterday", "ok": True, "by": "Igor", "observed": "x"},
    {"checked_at": "2026-11-07T17:00:00Z", "ok": True, "by": "", "observed": "x"},
])
def test_malformed_manual_checks_stop_the_build(tmp_path, bad_manual):
    with pytest.raises(ValueError):
        load_official_results(write_links(tmp_path, [link(manual_check=bad_manual)]))


def test_failed_checks_are_valid_records_and_hide_the_link(tmp_path):
    entries = load_official_results(write_links(tmp_path, [link(last_check=FAILED)]))
    assert results_link_for(current(), entries) is None


def test_check_times_compare_as_instants_and_export_canonical_utc():
    later_manual = {**MANUAL, "checked_at": "2026-11-07T11:00:00-08:00"}  # 19:00Z
    earlier_failure = {**FAILED, "checked_at": "2026-11-07T18:30:00Z"}
    shown = results_link_for(current(), [link(last_check=earlier_failure, manual_check=later_manual)])
    assert shown["checked_at"] == "2026-11-07T19:00:00Z"
    ok_offset = {**OK, "checked_at": "2026-11-07T08:10:18-08:00"}
    assert results_link_for(current(), [link(last_check=ok_offset)])["checked_at"] == "2026-11-07T16:10:18Z"


def test_a_failure_at_the_same_instant_as_a_success_wins():
    same_success = {**MANUAL, "checked_at": "2026-11-07T18:30:00+00:00"}
    same_failure = {**FAILED, "checked_at": "2026-11-07T18:30:00Z"}
    assert results_link_for(current(), [link(last_check=same_failure, manual_check=same_success)]) is None


def test_duplicate_links_stop_the_build(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        load_official_results(write_links(tmp_path, [link(), link()]))


OK = {"checked_at": "2026-11-07T16:10:18Z", "ok": True, "http_status": 200, "matched_text": "November 3, 2026"}
FAILED = {"checked_at": "2026-11-07T16:10:18Z", "ok": False, "reason": "bot_challenge"}
MANUAL = {"checked_at": "2026-11-07T18:00:00Z", "ok": True, "by": "Igor", "observed": "Nov 3 results"}


def test_link_is_public_only_when_its_newest_check_succeeded():
    measure = current()
    assert results_link_for(measure, [link()]) is None
    assert results_link_for(measure, [link(last_check=FAILED)]) is None
    shown = results_link_for(measure, [link(last_check=OK)])
    assert shown == {"url": "https://results.example.gov/2026", "publisher": "San Mateo County Elections",
                     "checked_at": OK["checked_at"]}
    # A person's later check can confirm a page that scripts cannot read...
    assert results_link_for(measure, [link(last_check=FAILED, manual_check=MANUAL)])["checked_at"] == MANUAL["checked_at"]
    # ...but a newer automated failure hides an older confirmation.
    newer_failure = {**FAILED, "checked_at": "2026-11-08T16:00:00Z"}
    assert results_link_for(measure, [link(last_check=newer_failure, manual_check=MANUAL)]) is None


def test_links_match_scope_county_and_election():
    statewide = link(scope="statewide", county=None, publisher="California Secretary of State",
                     url="https://sos.example.gov/results", last_check=OK)
    local = link(county="san mateo", last_check=OK)
    other_election = link(election_date="2028-11-07", url="https://results.example.gov/2028", last_check=OK)
    links = [statewide, local, other_election]
    assert results_link_for(current(county="Statewide"), links)["url"] == statewide["url"]
    assert results_link_for(current(), links)["url"] == local["url"]
    assert results_link_for(current(county="San Bernardino"), links) is None
    assert results_link_for(current(election_date="2028-11-07"), links)["url"] == other_election["url"]


def test_checked_dates_are_shown_as_california_dates():
    assert format_checked_date("2026-11-07T16:10:18Z") == "November 7, 2026"
    assert format_checked_date("2026-11-08T05:00:00Z") == "November 7, 2026"
    assert format_checked_date("not a time") == ""
    assert format_checked_date("2026-11-07T16:10:18") == ""


def test_status_sentences_make_no_claim_about_counting():
    assert status_sentence("upcoming", ELECTION) == "On the ballot November 3, 2026."
    assert status_sentence("election_day", ELECTION) == "Election day: November 3, 2026."
    pending = status_sentence("results_pending", ELECTION)
    assert pending == "Voted November 3, 2026. CalBallot has not recorded the result yet."
    for word in ("count", "certif", "passed", "failed", "leading"):
        assert word not in pending.lower()


def test_repository_links_file_is_valid():
    entries = load_official_results()
    assert {entry["scope"] for entry in entries} == {"statewide", "local"}


# --- Browser half -----------------------------------------------------------

NODE = shutil.which("node")


def run_browser_rule(cases):
    script = ELECTION_STATUS_SCRIPT + "\nconst cases = " + json.dumps(cases) + ";\n" + (
        "console.log(JSON.stringify(cases.map(c => getElectionStatus(c.measure, c.today))));")
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(result.stdout)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_browser_rule_matches_python_rule_and_never_moves_backward():
    dates = ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-12-04", "2027-01-01"]
    cases, expected = [], []
    for built_on in dates:
        row = current()
        attach_election_status([row], as_of=date.fromisoformat(built_on))
        for today in dates:
            cases.append({"measure": row, "today": today})
            later = max(built_on, today)  # the reader's clock only moves a status forward
            expected.append(election_status(current(), date.fromisoformat(later)))
    for outcome_row in (current(passed=1), current(passed=0), current(ballot_status="withdrawn"),
                        {"id": 9, "year": 1911, "passed": None}):
        cases.append({"measure": outcome_row, "today": "2026-11-07"})
        expected.append(election_status(outcome_row, date(2026, 11, 7)))
    # A bad reader clock falls back to the build's status.
    built = current(); attach_election_status([built], as_of=date(2026, 11, 7))
    cases.append({"measure": built, "today": None})
    expected.append("results_pending")
    assert run_browser_rule(cases) == expected


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_browser_agrees_on_stored_votes_and_noncanonical_dates():
    rows = [current(**{field: value}) for field, value in STORED_VOTES]
    rows += [current(election_date=value) for value in (" 2026-11-03 ", "2026-W45-2", "20261103")]
    attach_election_status(rows, as_of=date(2026, 11, 2))
    cases = [{"measure": row, "today": "2026-11-07"} for row in rows]
    expected = [election_status(row, date(2026, 11, 7)) for row in rows]
    assert set(expected) == {"unknown"}
    assert run_browser_rule(cases) == expected


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_browser_without_intl_keeps_the_build_status():
    row = current()
    attach_election_status([row], as_of=date(2026, 11, 7))
    script = ("Intl.DateTimeFormat = function () { throw new Error('no Intl'); };\n"
              + ELECTION_STATUS_SCRIPT
              + "\nconsole.log(JSON.stringify([pacificToday(), getElectionStatus(" + json.dumps(row) + ")]));")
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(result.stdout) == [None, "results_pending"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_browser_pacific_today_is_an_iso_date():
    result = subprocess.run([NODE, "-e", ELECTION_STATUS_SCRIPT + "\nconsole.log(pacificToday());"],
                            capture_output=True, text=True, timeout=30, check=True)
    assert parse_election_date(result.stdout.strip()) is not None


# --- Static pages -----------------------------------------------------------

def page_measure(**extra):
    row = {"id": 12450, "year": 2026, "title": "City of Belmont — Special Tax Measure",
           "county": "San Mateo", "election_date": ELECTION, "upcoming_scope": "local", "passed": None}
    row.update(extra)
    return row


def test_static_page_after_election_day_says_results_pending_with_checked_link():
    row = page_measure()
    attach_election_status([row], as_of=date(2026, 11, 7), links=[link(last_check=OK)])
    html = pages.build_page(row)
    assert "Results pending" in html and "Upcoming" not in html
    assert "Voted November 3, 2026. CalBallot has not recorded the result yet." in html
    assert 'href="https://results.example.gov/2026"' in html
    assert "(link checked November 7, 2026)" in html


def test_static_page_before_election_day_says_upcoming_without_results_link():
    row = page_measure()
    attach_election_status([row], as_of=date(2026, 11, 2), links=[link(last_check=OK)])
    html = pages.build_page(row)
    assert "Upcoming" in html and "On the ballot November 3, 2026." in html
    assert "Official results" not in html


def test_static_page_without_a_checked_link_states_status_only():
    row = page_measure()
    attach_election_status([row], as_of=date(2026, 11, 7), links=[link(last_check=FAILED)])
    html = pages.build_page(row)
    assert "Results pending" in html and "Official results" not in html


def test_historical_pages_gain_no_status_markup():
    decided = {"id": 5, "year": 2024, "title": "Old bond", "county": "San Mateo", "passed": 1, "percent_yes": 61.0}
    unknown = {"id": 6, "year": 1911, "title": "Old question", "county": "Statewide", "passed": None}
    for row in (decided, unknown):
        attach_election_status([row], as_of=date(2026, 11, 7))
        assert "Status:" not in pages.build_page(row)
    assert "Result unknown" in pages.build_page(unknown)


def test_explorer_refreshes_statuses_and_never_renders_an_undated_link():
    from src.website.generator import WebsiteGenerator
    script = WebsiteGenerator.__new__(WebsiteGenerator)._get_javascript("[]", "[]", "{}", {"total_measures": 0})
    # Review R1: an open page re-renders when the California date changes.
    assert "function refreshCalendarStatuses()" in script
    assert "setInterval(refreshCalendarStatuses" in script
    assert "visibilitychange" in script
    # Review R3: no check date, no link.
    assert "if (!checked) return '';" in script


def test_release_bundle_records_the_date_it_passes(tmp_path, monkeypatch):
    # Review R6: resolve once, pass to the generator, record the same value.
    import sqlite3
    spec_bundle = importlib.util.spec_from_file_location(
        "build_release_bundle", REPO / "scraper" / "scripts" / "build_release_bundle.py")
    bundle = importlib.util.module_from_spec(spec_bundle)
    spec_bundle.loader.exec_module(bundle)
    root = tmp_path / "workspace"
    (root / "scraper" / "data").mkdir(parents=True)
    sqlite3.connect(root / "scraper" / "data" / "ballot_measures.db").close()
    (root / "release-inputs.json").write_text(json.dumps({"sha256": {}}), encoding="utf-8")
    for name in bundle.ASSETS:
        (root / name).write_text("asset", encoding="utf-8")
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if "--output" in command:
            site = Path(command[command.index("--output") + 1]).parent
            (site / "index.html").write_text("<html></html>", encoding="utf-8")
            (site / "measures-data.json").write_text("[]", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(bundle, "ROOT", root)
    monkeypatch.setattr(bundle.subprocess, "run", fake_run)
    for name, argv in (("explicit", ["--as-of", "2026-11-07"]), ("default", [])):
        output = tmp_path / name
        bundle.main(["--output", str(output), *argv])
        recorded = json.loads((output / "build.json").read_text(encoding="utf-8"))["as_of"]
        generator_command = commands[-2]
        assert recorded and generator_command[generator_command.index("--as-of") + 1] == recorded
        if argv:
            assert recorded == "2026-11-07"


def test_generated_explorer_has_no_year_based_status_rule():
    from src.website.generator import WebsiteGenerator
    script = WebsiteGenerator.__new__(WebsiteGenerator)._get_javascript("[]", "[]", "{}", {"total_measures": 0})
    assert "year >= 2026" not in script
    assert "function getElectionStatus(" in script
    assert "Upcoming Election" not in script
    assert set(DATE_DRIVEN_STATUSES) <= set(json.loads(
        script.split("const DATE_DRIVEN_STATUSES = ", 1)[1].split(";", 1)[0].replace("'", '"')))


# --- P0.2b: no "Pending" for historical rows without an outcome --------------

def explorer_script():
    from src.website.generator import WebsiteGenerator
    return WebsiteGenerator.__new__(WebsiteGenerator)._get_javascript("[]", "[]", "{}", {"total_measures": 0})


def between(script, start, end):
    head = script.index(start)
    return script[head:script.index(end, head)]


def render_explorer_badges(rows):
    """Run the generated card and list-row builders in Node with stub helpers."""
    script = explorer_script()
    source = "\n".join([
        ELECTION_STATUS_SCRIPT,
        between(script, "function isPendingMeasure(", "function formatCheckedDate("),
        between(script, "function createCard(", "// Create list item HTML"),
        between(script, "function createListItem(", "// View measure details in modal"),
        "const allMeasures = [];",
        "const getDisplayMeasureId = m => m.measure_letter ? 'Measure ' + m.measure_letter : '';",
        "const getCleanTitle = m => m.title || '';",
        "const buildDisplayTitle = t => t;",
        "const isAiRefusal = () => false;",
        "const isMetadataSummary = () => false;",
        "const escapeHtml = s => String(s);",
        "const badge = html => /class=\"badge badge-([a-z]+)\">([^<]*)</.exec(html).slice(1);",
        "const rows = " + json.dumps(rows) + ";",
        "console.log(JSON.stringify(rows.map(m => ({card: badge(createCard(m)), list: badge(createListItem(m)),"
        " html: createCard(m) + createListItem(m)}))));",
    ])
    result = subprocess.run([NODE, "-e", source], capture_output=True, encoding="utf-8",
                            timeout=30, check=True)
    return json.loads(result.stdout)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_historical_rows_without_an_outcome_read_result_unknown_not_pending():
    # The 48 CEDA 2011 rows: stored votes, no normalized outcome, no calendar status.
    unknown_votes = {"id": 7, "year": 2011, "title": "School parcel tax", "passed": None,
                     "percent_yes": 61.2, "pass_fail": "PassT"}
    unknown_bare = {"id": 8, "year": 1999, "title": "City measure", "passed": None}
    date_driven = current(title="Belmont special tax")
    attach_election_status([date_driven], as_of=date(2026, 11, 7))
    rows = [unknown_votes, unknown_bare, date_driven,
            {"id": 9, "year": 2010, "title": "Bond", "passed": 1, "percent_yes": 70.0},
            {"id": 10, "year": 2010, "title": "Bond", "passed": 0},
            {"id": 11, "year": 2026, "title": "ACA 13", "passed": None, "ballot_status": "withdrawn"}]
    rendered = render_explorer_badges(rows)
    assert [r["card"] for r in rendered] == [
        ["pending", "• Result unknown"], ["pending", "• Result unknown"],
        ["pending", "⏳ Results pending"], ["passed", "✓ Passed"], ["failed", "✗ Failed"],
        ["neutral", "Withdrawn"]]
    # List rows keep their compact glyphs; an unknown row shows "?", never "Pending".
    assert [r["list"][1] for r in rendered] == ["?", "?", "Results pending", "✓", "✗", "Withdrawn"]
    for r in rendered[:2]:
        assert "pending" not in r["html"].replace("badge-pending", "").lower()


def test_explorer_has_no_legacy_pending_or_bare_unknown_badge():
    script = explorer_script()
    assert "• Pending" not in script
    assert "• Unknown" not in script
    # Card and modal badge both use the shared "Result unknown" label.
    assert script.count("`• ${getElectionStatusLabel('unknown')}`") == 2
    assert "unknown: 'Result unknown'" in script
