"""Tests for scripts/reconcile_ceda_raw.py (P1b.1b). Synthetic data only."""

import datetime
import importlib.util
import json
import sqlite3
from pathlib import Path

import openpyxl
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reconcile_ceda_raw.py"
spec = importlib.util.spec_from_file_location("reconcile_ceda_raw", SCRIPT)
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

HEADERS = ["MeasID", "YEAR", "CNTYNAME", "PLACE", "LTR", "BALQUEST", "DATE", "YES", "NO", "TOTAL",
           "PERCENT", "REQ", "PASSFAIL", "Multi_CO", "Multi_MeasID", "YES_sum", "NO_sum", "Total_sum",
           "Percent_sum", "passfail_sum", "JUR", "RECTYPENAME", "RECTOPNAME", "MEASTYPE"]


def raw_row(measure_id, county="LOS ANGELES", place="Azusa", letter="A", question="Shall A pass?",
            yes=60, no=40, passfail="Pass", multi_co=0, multi_id=None, yes_sum=None, no_sum=None,
            passfail_sum=None, req="M", year=2011, date=datetime.datetime(2011, 3, 8)):
    total = yes + no
    yes_sum = yes if yes_sum is None else yes_sum
    no_sum = no if no_sum is None else no_sum
    return [measure_id, year, county, place, letter, question, date, yes, no, total, yes / total, req,
            passfail, multi_co, multi_id or measure_id, yes_sum, no_sum, yes_sum + no_sum,
            yes_sum / (yes_sum + no_sum), passfail_sum or passfail, 2, "Ordinance", "Governance", "M"]


def parse(rows, headers=HEADERS):
    return rc.parse_rows(headers, rows, source="test.xlsx")


def db_row(row_id, measure_id, **overrides):
    row = {"id": row_id, "measure_id": str(measure_id), "year": 2011, "county": "LOS ANGELES",
           "measure_letter": "A", "title": "Shall A pass?", "ballot_question": None,
           "election_date": "2011-03-08", "yes_votes": 60, "no_votes": 40, "total_votes": 100,
           "percent_yes": 60.0, "pass_fail": "Pass", "passed": 1, "jurisdiction": "2",
           "category_type": "Ordinance", "category_topic": "Governance", "updated_at": "x"}
    row.update(overrides)
    return row


# ---- normalization -------------------------------------------------------

def test_clean_text_removes_invisible_characters_and_excel_errors():
    assert rc.clean_text("  Oak​land\xa0City­  ") == "Oakland City"
    assert rc.clean_text("#NULL!") == "" and rc.clean_text(None) == ""
    assert rc.norm_letter("​A ") == "A" and rc.norm_letter(1.0) == "1"
    assert rc.canonical_county("San Bernadino") == "SAN BERNARDINO"
    assert rc.canonical_county("toulumne") == "TUOLUMNE"


def test_ids_must_be_integral():
    assert rc.as_id(200000174.0) == "200000174" and rc.as_id(" 201400551 ") == "201400551"
    for bad in (200000174.5, "A12", None, True):
        with pytest.raises(ValueError):
            rc.as_id(bad)


def test_dates_use_the_workbook_datemode():
    assert rc.as_date(36837.0, 0) == "2000-11-07"
    assert rc.as_date(36837.0 - 1462, 1) == "2000-11-07"
    assert rc.as_date(datetime.datetime(2024, 11, 5, 0, 0)) == "2024-11-05"
    with pytest.raises(ValueError):
        rc.as_date(36837.0)


def test_percent_is_scaled_and_fractional_votes_are_flagged():
    row = raw_row(1, yes=60, no=40)
    row[7] = 60.486
    parsed = parse([row])[0]
    assert parsed["yes"] == 60 and parsed["fractional_votes"] is True
    assert parsed["percent"] == pytest.approx(60.0)
    status = rc.compare_row(db_row(1, 1), parsed)
    assert status["yes_votes"] == rc.FORMAT and status["percent_yes"] == rc.MATCH


# ---- headers and sheets --------------------------------------------------

def test_measureid_is_accepted_and_multi_measid_never_is_the_id():
    headers = ["MeasureID" if h == "MeasID" else h for h in HEADERS]
    assert rc.map_headers(headers)["id"] == 0
    without_id = [h for h in HEADERS if h != "MeasID"]
    with pytest.raises(ValueError, match="'id'"):
        rc.map_headers(without_id)


def test_header_names_are_case_insensitive_and_exact():
    headers = [{"passfail_sum": "Passfail_sum", "RECTOPNAME": "RECTOPICNAME"}.get(h, h) for h in HEADERS]
    columns = rc.map_headers(headers + ["Outcome_sum", "MeasID_First"])
    assert headers[columns["passfail_sum"]] == "Passfail_sum"
    assert headers[columns["topic_name"]] == "RECTOPICNAME"
    with pytest.raises(ValueError):  # "PERCENTAGE" must not satisfy "percent"
        rc.map_headers(["PERCENTAGE" if h == "PERCENT" else h for h in HEADERS])


def test_duplicate_measure_ids_in_one_file_raise():
    with pytest.raises(ValueError, match="duplicate"):
        parse([raw_row(5), raw_row(5, letter="B")])


def test_measures_sheet_is_chosen_by_name_not_position():
    assert rc.pick_measures_sheet(["Candidates 2022", "Measures 2022"]) == "Measures 2022"
    assert rc.pick_measures_sheet(["measures2014", "candidates2014"]) == "measures2014"
    with pytest.raises(ValueError):
        rc.pick_measures_sheet(["Measures2011", "Measures2011 (2)"])
    with pytest.raises(ValueError):
        rc.pick_measures_sheet(["Sheet1"])


def write_workbook(path, rows, headers=HEADERS, sheet="Measures2011"):
    book = openpyxl.Workbook()
    book.active.title = "Candidates2011"
    book.active.append(["not", "measures"])
    measures = book.create_sheet(sheet)
    measures.append(headers)
    for row in rows:
        measures.append(row)
    book.save(path)


def test_load_raw_file_reads_the_second_sheet(tmp_path):
    path = tmp_path / "ceda_data_2011.xlsx"
    write_workbook(path, [raw_row(201100001), raw_row(201100094, place="Vernon", yes=43, no=9)])
    rows = rc.load_raw_file(path)
    assert [r["id"] for r in rows] == ["201100001", "201100094"]
    assert rows[1]["src"] == {"file": path.name, "row": 3, "sheet": "Measures2011"}
    assert rows[0]["date"] == "2011-03-08"


# ---- classification ------------------------------------------------------

def test_a_row_holding_a_siblings_content_is_a_wrong_row():
    raws = parse([raw_row(1, place="Azusa", question="Shall Azusa act?", yes=2250, no=1059),
                  raw_row(94, place="Vernon", question="Shall Vernon act?", yes=43, no=9)])
    stored = [db_row(10, 1, ballot_question="Shall Vernon act?", title="Los Angeles Measure A",
                     yes_votes=43, no_votes=9, total_votes=52, percent_yes=82.69),
              db_row(11, 94, title="Shall Vernon act?", yes_votes=43, no_votes=9, total_votes=52,
                     percent_yes=82.692)]
    result = rc.reconcile_year(2011, stored, raws)
    by_id = {e["id"]: e for e in result["entries"]}
    assert by_id[10]["class"] == "wrong_row" and by_id[10]["content_of"] == "94"
    assert by_id[11]["class"] == "match"
    assert result["own_vote_mismatch"] == 1


def test_classes_match_format_incomplete_foreign_and_missing():
    raws = parse([raw_row(1), raw_row(2, county="SAN BERNADINO", letter="B", question="Shall B pass?"),
                  raw_row(3, letter="C", question="Shall C pass?"), raw_row(4, letter="D", question="Q4"),
                  raw_row(5, letter="E", question="Q5")])
    stored = [db_row(1, 1),
              db_row(2, 2, county="SAN BERNARDINO", measure_letter="B", title="Shall B pass?"),
              db_row(3, 3, measure_letter="C", title="Shall C pass?", passed=None),
              db_row(4, 4, measure_letter="H", county="MENDOCINO", title="Other text", yes_votes=2116,
                     no_votes=903, total_votes=3019, percent_yes=70.09),
              db_row(9, 999)]
    result = rc.reconcile_year(2011, stored, raws)
    classes = {e["id"]: e["class"] for e in result["entries"]}
    assert classes == {1: "match", 2: "format_only", 3: "incomplete", 4: "foreign", 9: "missing_from_raw"}
    assert [m["measure_id"] for m in result["missing_from_db"]] == ["5"]


def test_placeholder_title_with_a_spaced_designation_is_not_a_difference():
    raw = parse([raw_row(1, county="NAPA", letter="I A", question="Shall an ordinance be adopted?")])[0]
    stored = db_row(1, 1, county="NAPA", measure_letter="I A", title="NAPA Measure I A",
                    ballot_question="Shall an ordinance be adopted?")
    status = rc.compare_row(stored, raw)
    assert status["title"] == rc.FORMAT and rc.classify(status) == "format_only"
    stored["title"] = "NAPA Measure B"
    assert rc.compare_row(stored, raw)["title"] == rc.DIFF


def test_2014_rows_stored_under_the_group_key_are_wrong_key():
    headers = ["MeasureID" if h == "MeasID" else h for h in HEADERS]
    raws = parse([raw_row(551, county="ALAMEDA", letter="K", yes=10, no=20, multi_co=1, multi_id=550,
                          yes_sum=40, no_sum=30, passfail="Fail", passfail_sum="Pass", year=2014),
                  raw_row(552, county="SAN JOAQUIN", letter="K", yes=30, no=10, multi_co=1, multi_id=550,
                          yes_sum=40, no_sum=30, passfail="Pass", passfail_sum="Pass", year=2014),
                  raw_row(600, county="KERN", letter="B", multi_id=600, year=2014)], headers)
    stored = [db_row(1, 550, year=2014, county="ALAMEDA", measure_letter="K", yes_votes=10, no_votes=20,
                     total_votes=30, percent_yes=33.333, pass_fail="Fail", passed=0),
              db_row(2, 600, year=2014, county="KERN", measure_letter="B")]
    result = rc.reconcile_year(2014, stored, raws)
    classes = {e["id"]: (e["class"], e.get("raw_id")) for e in result["entries"]}
    assert classes == {1: ("wrong_key", "551"), 2: ("match", "600")}
    assert [m["measure_id"] for m in result["missing_from_db"]] == ["552"]
    assert result["outcome_flips"] == 1
    assert rc.group_violations(raws) == []


def test_group_violations_are_reported():
    raws = parse([raw_row(1, multi_co=1, multi_id=1, yes=10, no=5, yes_sum=99, no_sum=9),
                  raw_row(2, letter="B", multi_co=1, multi_id=1, yes=20, no=4, yes_sum=30, no_sum=9)])
    problems = rc.group_violations(raws)
    assert any("yes_sum" in p for p in problems) and any("members' sum" in p for p in problems)


def test_distinctive_overlap_prefers_the_matching_question():
    summary = "This measure would amend the Vernon City Charter to limit council terms."
    own = "Shall Ordinance No. 10-O5 adopting a development agreement be approved?"
    sibling = "Shall the Vernon City Charter be amended to limit the number of council terms?"
    assert rc.distinctive_overlap(summary, sibling) - rc.distinctive_overlap(summary, own) >= 0.25


# ---- read-only contract --------------------------------------------------

def make_db(path, rows):
    connection = sqlite3.connect(path)
    columns = ["id", "measure_id", "year", "county", "measure_letter", "title", "ballot_question",
               "election_date", "yes_votes", "no_votes", "total_votes", "percent_yes", "pass_fail",
               "passed", "jurisdiction", "category_type", "category_topic", "updated_at",
               "summary_text", "fingerprint", "update_count"]
    connection.execute(f"CREATE TABLE measures ({', '.join(columns)}, data_source DEFAULT 'CEDA')")
    for row in rows:
        connection.execute(f"INSERT INTO measures ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                           [row.get(column) for column in columns])
    connection.commit()
    connection.close()


def test_connections_are_read_only(tmp_path):
    path = tmp_path / "copy.db"
    make_db(path, [db_row(1, 1)])
    connection = rc.open_readonly(path)
    with pytest.raises(sqlite3.OperationalError):
        connection.execute("UPDATE measures SET passed = 0")
    connection.close()


def test_main_writes_reports_and_leaves_the_database_unchanged(tmp_path, capsys):
    raw_dir, downloads, out = tmp_path / "raw", tmp_path / "raw" / "dl", tmp_path / "out"
    downloads.mkdir(parents=True)
    write_workbook(raw_dir / "ceda_data_2011.xlsx",
                   [raw_row(1, question="Shall Azusa act?", yes=2250, no=1059),
                    raw_row(94, place="Vernon", question="Shall Vernon act?", yes=43, no=9)])
    db = tmp_path / "copy.db"
    make_db(db, [db_row(10, 1, ballot_question="Shall Vernon act?", title="Los Angeles Measure A",
                        yes_votes=43, no_votes=9, total_votes=52, percent_yes=82.69,
                        updated_at="2026-04-12 17:50:43"),
                 db_row(11, 94, title="Shall Vernon act?", yes_votes=43, no_votes=9, total_votes=52,
                        percent_yes=82.692),
                 db_row(12, 77, year=2018)])
    before = rc.sha256_of(db)
    code = rc.main(["--db", str(db), "--out", str(out), "--raw-dir", str(raw_dir), "--downloads", str(downloads)])
    assert code == 0 and rc.sha256_of(db) == before
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["db_sha256_before"] == summary["db_sha256_after"] == before
    assert summary["years"]["2011"]["classes"] == {"wrong_row": 1, "match": 1}
    assert summary["stamp"]["ceda_class"] == {"wrong_row": 1}
    assert summary["ceda_rows_without_raw_by_year"] == {"2018": 1}
    ledger = json.loads((out / "ledger.json").read_text(encoding="utf-8"))
    assert [e["class"] for e in ledger] == ["wrong_row"]
    # Evidence a gate result can be tied to: every raw file's hash, and the tool's.
    assert summary["raw_files"]["2011"]["sha256"] == rc.sha256_of(raw_dir / "ceda_data_2011.xlsx")
    assert summary["raw_files"]["2011"]["rows"] == 2
    assert summary["tool_sha256"] == rc.sha256_of(SCRIPT)
    assert summary["gate"]["clean"] is False and summary["gate"]["blocking"] == {"wrong_row": 1}


# ---- the tool as the P1b.2 gate ------------------------------------------

MEASUREID_HEADERS = ["MeasureID" if h == "MeasID" else h for h in HEADERS]


def raws_2014():
    return parse([raw_row(551, county="ALAMEDA", letter="K", yes=10, no=20, multi_co=1, multi_id=550,
                          yes_sum=40, no_sum=30, passfail="Fail", passfail_sum="Pass", year=2014),
                  raw_row(552, county="SAN JOAQUIN", letter="K", yes=30, no=10, multi_co=1, multi_id=550,
                          yes_sum=40, no_sum=30, passfail="Pass", passfail_sum="Pass", year=2014),
                  raw_row(600, county="KERN", letter="B", multi_id=600, year=2014),
                  raw_row(601, county="KERN", letter="C", multi_id=602, year=2014),
                  raw_row(602, county="KERN", letter="D", multi_id=601, year=2014)], MEASUREID_HEADERS)


def stored_2014(keys):
    """Stored rows for the five raw rows, under the given measure IDs."""
    alameda = dict(year=2014, county="ALAMEDA", measure_letter="K", yes_votes=10, no_votes=20,
                   total_votes=30, percent_yes=33.333, pass_fail="Fail", passed=0)
    joaquin = dict(year=2014, county="SAN JOAQUIN", measure_letter="K", yes_votes=30, no_votes=10,
                   total_votes=40, percent_yes=75.0)
    rows = [db_row(1, keys[0], **alameda), db_row(3, keys[2], year=2014, county="KERN", measure_letter="B"),
            db_row(4, keys[3], year=2014, county="KERN", measure_letter="C"),
            db_row(5, keys[4], year=2014, county="KERN", measure_letter="D")]
    if keys[1] is not None:
        rows.insert(1, db_row(2, keys[1], **joaquin))
    return rows


def test_key_mode_comes_from_the_data_not_the_header():
    # Today: stored under Multi_MeasID, and the group collapsed one member.
    before = rc.reconcile_year(2014, stored_2014([550, None, 600, 602, 601]), raws_2014())
    assert before["key_mode"] == "group"
    assert before["classes"] == {"wrong_key": 3, "match": 1, "missing_from_db": 1}


def test_a_correct_2014_rekey_reconciles_cleanly():
    # After the rekey every row is under its own MeasureID. The header is
    # still "MeasureID"; the tool must not fall back to group resolution.
    after = rc.reconcile_year(2014, stored_2014([551, 552, 600, 601, 602]), raws_2014())
    assert after["key_mode"] == "own"
    assert after["classes"] == {"match": 5}
    assert after["missing_from_db"] == [] and after["own_vote_mismatch"] == 0


def test_a_rekey_that_leaves_a_member_out_is_still_caught():
    after = rc.reconcile_year(2014, stored_2014([551, None, 600, 601, 602]), raws_2014())
    assert after["key_mode"] == "own"
    assert after["classes"] == {"match": 4, "missing_from_db": 1}
    assert after["missing_from_db"][0]["measure_id"] == "552"


def test_the_same_id_on_two_raw_rows_is_a_reported_collision():
    # Two releases give 201600120 to two measures. Loading both must not let
    # the later row stand in for the earlier one.
    older = rc.parse_rows(HEADERS, [raw_row(201600120, county="SANTA CRUZ", place="Santa Cruz County",
                                            letter="D", question="Sales tax?", yes=83816, no=39839,
                                            year=2016)], source="2016.xlsx")
    newer = rc.parse_rows(HEADERS, [raw_row(201600120, county="SANTA CRUZ", place="Santa Cruz City Elementary",
                                            letter="P", question="Parcel tax?", yes=8499, no=2596,
                                            year=2016)], source="2015.xlsx")
    stored = [db_row(4870, 201600120, year=2016, county="SANTA CRUZ", measure_letter="P", title="Parcel tax?",
                     yes_votes=8499, no_votes=2596, total_votes=11095, percent_yes=76.602)]
    result = rc.reconcile_year(2016, stored, older + newer)
    assert [r["measure_id"] for r in result["repeated_ids"]] == ["201600120"]
    assert {r["file"] for r in result["repeated_ids"][0]["rows"]} == {"2016.xlsx", "2015.xlsx"}
    entry = result["entries"][0]
    assert entry["class"] == "id_collision" and entry["stored_candidate"]["letter"] == "P"
    assert [(m["letter"], m["id_collision"]) for m in result["missing_from_db"]] == [("D", True)]


def test_a_shared_id_is_clean_once_both_measures_are_stored():
    # The repaired state: both measures kept under the one CEDA ID, told apart
    # by designation. Each stored row is matched to its own raw row.
    older = rc.parse_rows(HEADERS, [raw_row(201600120, county="SANTA CRUZ", letter="D", question="Sales tax?",
                                            yes=83816, no=39839, year=2016,
                                            date=datetime.datetime(2016, 11, 8))], source="2016.xlsx")
    newer = rc.parse_rows(HEADERS, [raw_row(201600120, county="SANTA CRUZ", letter="P", question="Parcel tax?",
                                            yes=8499, no=2596, year=2016,
                                            date=datetime.datetime(2016, 11, 17))], source="2015.xlsx")
    measure_p = db_row(4870, 201600120, year=2016, county="SANTA CRUZ", measure_letter="P", title="Parcel tax?",
                       election_date="2016-11-17", yes_votes=8499, no_votes=2596, total_votes=11095,
                       percent_yes=76.602)
    measure_d = db_row(12500, 201600120, year=2016, county="SANTA CRUZ", measure_letter="D", title="Sales tax?",
                       election_date="2016-11-08", yes_votes=83816, no_votes=39839, total_votes=123655,
                       percent_yes=67.782)
    result = rc.reconcile_year(2016, [measure_p, measure_d], older + newer)
    assert result["classes"] == {"match": 2} and result["missing_from_db"] == []
    assert result["repeated_ids"][0]["resolved"] is True
    # Before the older release's file is in hand, the restored measure has no
    # raw row: it is reported as such, not matched to its sibling.
    result = rc.reconcile_year(2016, [measure_p, measure_d], newer)
    assert {e["id"]: e["class"] for e in result["entries"]} == {4870: "match", 12500: "missing_from_raw"}


def write_csv(path, rows):
    import csv
    columns = ["year", "measure_id", "county", "measure_letter", "yes_votes", "no_votes", "pass_fail",
               "election_date", "passed", "title"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def reused_id_fixture(tmp_path):
    """The id 4870 case: the 2015 file carries a 2016 row whose ID an older
    release gave to another measure, and the ingest overwrote that measure."""
    raw_dir, downloads = tmp_path / "raw", tmp_path / "raw" / "dl"
    downloads.mkdir(parents=True)
    write_workbook(raw_dir / "ceda_data_2015.xlsx",
                   [raw_row(201500001, year=2015, date=datetime.datetime(2015, 11, 3)),
                    raw_row(201600120, county="SANTA CRUZ", place="Santa Cruz City Elementary", letter="P",
                            question="Parcel tax?", yes=8499, no=2596, year=2016,
                            date=datetime.datetime(2016, 11, 17))], sheet="measures2015")
    measure_p = dict(year=2016, county="SANTA CRUZ", measure_letter="P", title="Parcel tax?",
                     election_date="2016-11-17", yes_votes=8499, no_votes=2596, total_votes=11095,
                     percent_yes=76.602)
    measure_d = dict(year=2016, county="SANTA CRUZ", measure_letter="D", title="Sales tax?",
                     election_date="2016-11-08", yes_votes=83816, no_votes=39839, total_votes=123655,
                     percent_yes=67.782)
    first = db_row(1, 201500001, year=2015, election_date="2015-11-03")
    make_db(tmp_path / "baseline.db", [first, db_row(4870, 201600120, **measure_d)])
    make_db(tmp_path / "now.db", [first, db_row(4870, 201600120, **measure_p)])
    write_csv(tmp_path / "ceda_parsed.csv",
              [{"year": 2016, "measure_id": 201600120, "county": "SANTA CRUZ", "measure_letter": "D",
                "yes_votes": 83816, "no_votes": 39839, "pass_fail": "Pass", "election_date": "2016-11-08",
                "title": "Sales tax?"}])
    return ["--db", str(tmp_path / "now.db"), "--out", str(tmp_path / "out"), "--raw-dir", str(raw_dir),
            "--downloads", str(downloads), "--baseline-db", str(tmp_path / "baseline.db"),
            "--csv", str(tmp_path / "ceda_parsed.csv")]


def test_an_id_reused_between_releases_is_its_own_class(tmp_path):
    arguments = reused_id_fixture(tmp_path)
    assert rc.main(arguments) == 0
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert summary["release_conflicts"] == [{
        "year": 2016, "measure_id": "201600120", "raw": ["SANTA CRUZ P"], "csv": ["SANTA CRUZ D"],
        "stored": [{"id": 4870, "identity": "SANTA CRUZ P"}],
        "stored_in_baseline": [{"id": 4870, "identity": "SANTA CRUZ D"}],
        "identities_not_stored": ["SANTA CRUZ D"]}]
    assert summary["totals"] == {"match": 1, "id_reused": 1}
    ledger = json.loads((tmp_path / "out" / "ledger.json").read_text(encoding="utf-8"))
    reused = [e for e in ledger if e["class"] == "id_reused"]
    assert [(e["id"], e["baseline_identity"]) for e in reused] == [(4870, "SANTA CRUZ D")]
    # The row is not dropped from the comparison with the CSV: it is counted,
    # and it is the row that does not agree.
    assert summary["csv"]["db_vs_csv_in_unheld_years"]["2016"] == {
        "db_rows": 1, "also_checked_against_raw": 1, "not_in_csv": 1, "csv_rows": 1, "csv_distinct_ids": 1}


def test_gate_exit_code_and_waivers(tmp_path):
    arguments = reused_id_fixture(tmp_path)
    assert rc.main(arguments + ["--gate"]) == 1
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert summary["gate"]["blocking"] == {"id_reused": 1}
    assert summary["gate"]["release_conflicts_with_an_identity_not_stored"] == 1
    # A recorded decision can defer one named ID; the waiver is echoed.
    assert rc.main(arguments + ["--gate", "--waive", "2016:201600120"]) == 0
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert summary["gate"]["clean"] is True and summary["gate"]["waived"] == ["2016:201600120"]


def test_a_csv_year_keyed_on_the_group_id_is_not_read_as_id_reuse():
    csv_rows = [{"year": 2014, "measure_id": 550, "county": "ALAMEDA", "measure_letter": "K",
                 "yes_votes": 10, "no_votes": 20},
                {"year": 2014, "measure_id": 550, "county": "SAN JOAQUIN", "measure_letter": "K",
                 "yes_votes": 30, "no_votes": 10},
                {"year": 2014, "measure_id": 600, "county": "KERN", "measure_letter": "B",
                 "yes_votes": 60, "no_votes": 40},
                {"year": 2014, "measure_id": 602, "county": "KERN", "measure_letter": "C",
                 "yes_votes": 60, "no_votes": 40},
                {"year": 2014, "measure_id": 601, "county": "KERN", "measure_letter": "D",
                 "yes_votes": 60, "no_votes": 40}]
    assert rc.release_conflicts(csv_rows, raws_2014(), stored_2014([551, 552, 600, 601, 602])) == []


# ---- cohorts ---------------------------------------------------------------

def test_cohorts_report_stored_per_row_and_combined_results():
    def stored(row_id, year, county, passed, category="GO Bond", source="CEDA"):
        return {"id": row_id, "year": year, "county": county, "category_type": category, "passed": passed,
                "data_source": source, "is_duplicate": 0, "is_active": 1}

    rows = [stored(1, 2000, "SAN BERNARDINO", 1), stored(2, 2000, "SAN BERNARDINO", None),
            stored(3, 2000, "SAN BERNADINO", 0), stored(4, 2002, "SAN BERNARDINO", 0),
            stored(5, 2014, "SAN BERNARDINO", 1), stored(6, 2018, "SAN BERNARDINO", 1),
            stored(7, 1990, "San Bernardino", 0, source="ICPSR"),
            stored(8, 2000, "SAN BERNARDINO", 1, category="Recall"),
            stored(9, 2000, "KERN", 1),
            stored(10, 2026, "San Bernardino", None, source="San_Bernardino_County_Registrar")]
    raw = {2000: parse([raw_row(1, county="SAN BERNARDINO", year=2000),
                        raw_row(2, county="SAN BERNARDINO", letter="B", passfail="FailT", year=2000),
                        raw_row(3, county="SAN BERNADINO", letter="C", passfail="FailT", year=2000)]),
           2002: parse([raw_row(4, county="SAN BERNARDINO", place="KERN COMMUNITY COLLEGE", letter="G",
                                passfail="FailF", passfail_sum="PassF", multi_co=1, year=2002)]),
           2014: parse([raw_row(5, county="SAN BERNARDINO", year=2014),
                        raw_row(50, county="SAN BERNARDINO", letter="Z", passfail="FailF", year=2014)],
                       MEASUREID_HEADERS)}
    for year, parsed in raw.items():
        for row in parsed:
            row["type_name"] = "GO Bond"
    report = rc.cohort_report(rows, raw, {"go bond"}, constant_years={2014})
    assert report["counties"] == ["san bernardino"]
    # Stored: rows 1, 4, 5, 6, 7. Row 2 has no outcome; row 3 is misspelled.
    # Raw replaces 2000 and 2002: all three 2000 rows now count. 2014 keeps
    # its stored row, so the extra raw 2014 row is not added.
    assert report["cohorts"] == {"san bernardino | go bond": {
        "stored": [3, 5], "raw_per_row": [3, 7], "raw_combined": [4, 7]}}
    assert [(d["measure_id"], d["own"], d["combined"], d["multi_co"])
            for d in report["own_and_combined_outcomes_differ"]] == [("4", 0, 1, 1)]


def test_reviewed_categories_come_from_the_site_module():
    module = SCRIPT.parents[1] / "src" / "website" / "local_measure_context.py"
    categories = rc.load_reviewed_categories(module)
    assert "go bond" in categories and "sales tax" in categories and None not in categories
