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
