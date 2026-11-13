#!/usr/bin/env python3
"""Reconcile stored CEDA rows against the raw CEDA files. Read-only (P1b.1b).

Every CEDA row in a year we hold a raw file for is compared field by field
with the raw row that carries the same ``MeasID``. Nothing is written to any
database: every connection is opened ``mode=ro``. Raw files are untrusted, so
run this with ``python -I``. The module imports no project code, except that
the cohort table loads the reviewed categories from
``src/website/local_measure_context.py`` by path.

It is also the gate for the P1b.2 repair. With ``--gate`` it exits 1 unless
it finds no wrong row, wrong key, reused or repeated ID, incomplete row or
missing row. ``summary.json`` records each raw file's SHA-256 and this
script's own, so a gate result can be tied to its inputs.

    python -I scraper/scripts/reconcile_ceda_raw.py \
        --db <copy-or-production.db> --out <folder>

Optional inputs widen the report:

``--baseline-db``  a July 2025 backup, to date the wrong-row defect;
``--csv``          ``ceda_parsed.csv``, a stand-in for years with no raw file
                   and the evidence for IDs reused between CEDA releases.

Row classes
-----------
``match``            no compared field conflicts with raw. Fields the row does
                     not hold (question, jurisdiction, topic) are counted
                     separately, under ``unloaded_fields``
``format_only``      differences vanish after normalizing case, spacing,
                     invisible characters, county spelling or vote rounding,
                     or the title is the "<COUNTY> Measure <LTR>" placeholder
``incomplete``       no conflict, but the outcome or the date was never
                     derived although raw has it; such rows drop out of the
                     site's statistics
``differs``          a real difference, but the content is this measure's
``wrong_row``        the stored content is another raw row's
``foreign``          the stored content appears in no raw row of that year
``wrong_key``        stored under ``Multi_MeasID``, not the row's own ID (2014
                     today). Detected from the data, not from the header
``id_collision``     the stored ID belongs to two or more loaded raw rows
``id_reused``        the ID names different measures in two CEDA releases and
                     the stored row was overwritten by one of them (needs
                     ``--csv`` and ``--baseline-db``)
``missing_from_db``  a raw row with no stored row
``missing_from_raw`` a stored row with no raw row
"""

from __future__ import annotations

import argparse
import collections
import csv
import datetime
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------

# Zero-width space/joiners, BOM and soft hyphen: present in 2006-2024 text.
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍﻿­"))
_EXCEL_ERROR = re.compile(r"#[A-Z0-9/]+[!?]")
COUNTY_TYPOS = {"SAN BERNADINO": "SAN BERNARDINO", "TOULUMNE": "TUOLUMNE"}


def clean_text(value: object) -> str:
    """Text for comparison: no invisible characters, single spaces, no
    Excel error placeholders such as ``#NULL!``. Raw text is kept elsewhere."""
    if value is None:
        return ""
    text = str(value).translate(_INVISIBLE).replace("\xa0", " ")
    text = " ".join(text.split())
    return "" if _EXCEL_ERROR.fullmatch(text) else text


def canonical_county(value: object) -> str:
    upper = clean_text(value).upper()
    return COUNTY_TYPOS.get(upper, upper)


def norm_letter(value: object) -> str:
    """Measure designation for matching. xls files store "1" as 1.0."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = clean_text(value).upper()
    return text[:-2] if re.fullmatch(r"\d+\.0", text) else text


def as_id(value: object) -> str:
    """A ``MeasID`` as the digits the database stores. xls files hold floats;
    a non-integral ID is a file defect, never something to round."""
    if isinstance(value, str):
        value = value.strip()
        if not value.isdigit():
            raise ValueError(f"non-numeric measure ID {value!r}")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"unusable measure ID {value!r}")
    if float(value) != int(value):
        raise ValueError(f"non-integral measure ID {value!r}")
    return str(int(value))


def as_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def as_votes(value: object) -> tuple[int | None, bool]:
    """Vote count and whether the raw value was fractional (2004 has one)."""
    number = as_number(value)
    if number is None:
        return None, False
    return int(round(number)), not float(number).is_integer()


def as_date(value: object, datemode: int | None = None) -> str:
    """ISO date. xls serials need the workbook's own ``datemode``."""
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if datemode is None:
            raise ValueError("a date serial needs the workbook datemode")
        epoch = datetime.datetime(1904, 1, 1) if datemode == 1 else datetime.datetime(1899, 12, 30)
        return (epoch + datetime.timedelta(days=float(value))).date().isoformat()
    text = clean_text(value)
    return text[:10] if re.match(r"\d{4}-\d{2}-\d{2}", text) else ""


def outcome_of(code: object) -> int | None:
    """1 for Pass/PassT/PassF, 0 for Fail*, None otherwise."""
    text = clean_text(code).casefold()
    return 1 if text.startswith("pass") else 0 if text.startswith("fail") else None


# --------------------------------------------------------------------------
# Raw files
# --------------------------------------------------------------------------

# Canonical field -> accepted header names, lower-cased and exact. No
# substring matching: that is how 2014 came to be keyed on Multi_MeasID.
HEADER_ALIASES = {
    "id": ("measid", "measureid"),
    "year": ("year",),
    "county": ("cntyname",),
    "place": ("place",),
    "letter": ("ltr",),
    "question": ("balquest",),
    "date": ("date",),
    "yes": ("yes",),
    "no": ("no",),
    "total": ("total",),
    "percent": ("percent",),
    "req": ("req",),
    "passfail": ("passfail",),
    "multi_co": ("multi_co",),
    "multi_id": ("multi_measid",),
    "yes_sum": ("yes_sum",),
    "no_sum": ("no_sum",),
    "total_sum": ("total_sum",),
    "percent_sum": ("percent_sum",),
    "passfail_sum": ("passfail_sum",),
    "jur": ("jur",),
    "type_name": ("rectypename",),
    "topic_name": ("rectopname", "rectopicname"),
    "meastype": ("meastype",),
}


def map_headers(headers: list[object]) -> dict[str, int]:
    """Column index per canonical field; a missing or doubled header raises."""
    seen: dict[str, int] = {}
    for index, header in enumerate(headers):
        name = clean_text(header).lower()
        if name and name not in seen:
            seen[name] = index
    columns = {}
    for field, names in HEADER_ALIASES.items():
        found = [seen[name] for name in names if name in seen]
        if len(found) != 1:
            raise ValueError(f"CEDA header for {field!r}: expected one of {names}, found {len(found)}")
        columns[field] = found[0]
    return columns


def pick_measures_sheet(names: list[str]) -> str:
    """The measures sheet by normalized name, never by position."""
    hits = [n for n in names if re.sub(r"[\s_]", "", n).lower().startswith("measures")]
    if len(hits) != 1:
        raise ValueError(f"expected one measures sheet, found {hits} in {names}")
    return hits[0]


def read_sheet(path: Path) -> tuple[str, list[object], list[list[object]], int | None]:
    """(sheet name, header row, data rows, datemode) from an .xls or .xlsx."""
    if path.suffix.lower() == ".xls":
        import xlrd

        book = xlrd.open_workbook(str(path))
        sheet = book.sheet_by_name(pick_measures_sheet(book.sheet_names()))
        rows = [sheet.row_values(i) for i in range(sheet.nrows)]
        return sheet.name, rows[0], rows[1:], book.datemode
    import openpyxl

    book = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    name = pick_measures_sheet(book.sheetnames)
    rows = [list(row) for row in book[name].iter_rows(values_only=True)]
    book.close()
    return name, rows[0], rows[1:], None


def parse_rows(headers, rows, datemode=None, source="") -> list[dict]:
    """Normalized raw rows. Raises on a duplicate or unusable measure ID."""
    columns = map_headers(headers)
    id_header = clean_text(headers[columns["id"]])
    parsed, seen = [], set()
    for number, row in enumerate(rows, start=2):
        if all(value is None or clean_text(value) == "" for value in row):
            continue
        get = lambda field: row[columns[field]] if columns[field] < len(row) else None
        measure_id = as_id(get("id"))
        if measure_id in seen:
            raise ValueError(f"{source}: duplicate {id_header} {measure_id}")
        seen.add(measure_id)
        yes, yes_fraction = as_votes(get("yes"))
        no, no_fraction = as_votes(get("no"))
        total, _ = as_votes(get("total"))
        percent, percent_sum = as_number(get("percent")), as_number(get("percent_sum"))
        year = as_number(get("year"))
        multi_co = as_number(get("multi_co"))
        jur = as_number(get("jur"))
        parsed.append({
            "id": measure_id,
            "id_header": id_header,
            "year": int(year) if year is not None else None,
            "county_raw": "" if get("county") is None else str(get("county")),
            "county": canonical_county(get("county")),
            "place": clean_text(get("place")),
            "letter_raw": "" if get("letter") is None else str(get("letter")),
            "letter": norm_letter(get("letter")),
            "question_raw": "" if get("question") is None else str(get("question")),
            "question": clean_text(get("question")),
            "date": as_date(get("date"), datemode),
            "yes": yes, "no": no, "total": total,
            "fractional_votes": yes_fraction or no_fraction,
            "percent": None if percent is None else percent * 100,
            "req": clean_text(get("req")).upper(),
            "passfail": clean_text(get("passfail")),
            "multi_co": None if multi_co is None else int(multi_co),
            "multi_id": as_id(get("multi_id")),
            "yes_sum": as_votes(get("yes_sum"))[0],
            "no_sum": as_votes(get("no_sum"))[0],
            "total_sum": as_votes(get("total_sum"))[0],
            "percent_sum": None if percent_sum is None else percent_sum * 100,
            "passfail_sum": clean_text(get("passfail_sum")),
            "jur": "" if jur is None else str(int(jur)),
            "type_name": clean_text(get("type_name")),
            "topic_name": clean_text(get("topic_name")),
            "meastype": clean_text(get("meastype")),
            "src": {"file": source, "row": number},
        })
    return parsed


def load_raw_file(path: Path) -> list[dict]:
    sheet, headers, rows, datemode = read_sheet(path)
    parsed = parse_rows(headers, rows, datemode, source=path.name)
    for row in parsed:
        row["src"]["sheet"] = sheet
    return parsed


def discover_raw_files(downloads: Path, raw_dir: Path) -> dict[int, Path]:
    """One file per year. On-disk ``ceda_data_{year}.xlsx`` files win over the
    archive downloads (2011 exists in both and is cell-identical)."""
    files: dict[int, Path] = {}
    if downloads.is_dir():
        for folder in sorted(downloads.iterdir()):
            if folder.is_dir() and folder.name.isdigit():
                found = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".xls", ".xlsx"))
                if len(found) != 1:
                    raise ValueError(f"expected one spreadsheet in {folder}")
                files[int(folder.name)] = found[0]
    for path in sorted(raw_dir.glob("ceda_data_*.xlsx")):
        files[int(path.stem.rsplit("_", 1)[1])] = path
    return files


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------

MATCH, FORMAT, DIFF, DB_EMPTY = "match", "format", "diff", "db_empty"


def _text_status(stored: object, raw_value: str, canonical=clean_text) -> str:
    if stored is None or str(stored) == "":
        return DB_EMPTY if raw_value else MATCH
    if str(stored) == raw_value:
        return MATCH
    return FORMAT if canonical(stored).casefold() == canonical(raw_value).casefold() else DIFF


def _title_status(title: str, raw: dict) -> str:
    """A stored title is this measure's question, or the Excel ingest's
    "<COUNTY> Measure <LTR>" placeholder for this county and designation."""
    if not title:
        return DB_EMPTY
    county, marker, letter = title.rpartition(" Measure ")
    if marker and canonical_county(county) == raw["county"] and norm_letter(letter) == raw["letter"]:
        return FORMAT
    if title == raw["question"]:
        return MATCH
    return FORMAT if raw["question"].startswith(title) else DIFF


def compare_row(db: dict, raw: dict) -> dict[str, str]:
    """Status of every compared field for one stored row and one raw row."""
    status = {
        "county": _text_status(db.get("county"), raw["county_raw"], canonical_county),
        "letter": _text_status(db.get("measure_letter"), raw["letter_raw"], norm_letter),
        "pass_fail": _text_status(db.get("pass_fail"), raw["passfail"]),
        "jurisdiction": _text_status(db.get("jurisdiction"), raw["jur"]),
        "category_type": _text_status(db.get("category_type"), raw["type_name"]),
        "category_topic": _text_status(db.get("category_topic"), raw["topic_name"]),
        "ballot_question": _text_status(db.get("ballot_question"), raw["question_raw"]),
    }
    stored_date = db.get("election_date")
    status["election_date"] = (DB_EMPTY if not stored_date
                               else MATCH if stored_date == raw["date"] else DIFF)
    for field, key in (("yes_votes", "yes"), ("no_votes", "no"), ("total_votes", "total")):
        if db.get(field) is None:
            status[field] = DB_EMPTY if raw[key] is not None else MATCH
        elif db[field] == raw[key]:
            status[field] = FORMAT if raw["fractional_votes"] and key != "total" else MATCH
        else:
            status[field] = DIFF
    if db.get("percent_yes") is None:
        status["percent_yes"] = DB_EMPTY if raw["percent"] is not None else MATCH
    else:
        close = raw["percent"] is not None and abs(db["percent_yes"] - raw["percent"]) <= 0.01
        status["percent_yes"] = MATCH if close else DIFF
    expected = outcome_of(raw["passfail"])
    if db.get("passed") is None:
        status["passed"] = DB_EMPTY if expected is not None else MATCH
    else:
        status["passed"] = MATCH if db["passed"] == expected else DIFF
    status["title"] = _title_status(clean_text(db.get("title")), raw)
    return status


IDENTITY_FIELDS = ("yes_votes", "no_votes", "ballot_question", "title")
# Fields every CEDA row was meant to carry. The rest (question, jurisdiction,
# topic) were never loaded for most years; that is the backfill's subject.
CORE_FIELDS = ("county", "letter", "election_date", "yes_votes", "no_votes",
               "total_votes", "percent_yes", "pass_fail", "passed")


def classify(status: dict[str, str]) -> str:
    values = set(status.values())
    if DIFF in values:
        return "differs"
    if any(status[field] == DB_EMPTY for field in CORE_FIELDS):
        return "incomplete"
    return "format_only" if FORMAT in values else "match"


def find_content_owner(db: dict, raws: list[dict]) -> dict | None:
    """The single raw row whose votes (and question, when one is stored)
    equal the stored row's, if exactly one exists."""
    question = clean_text(db.get("ballot_question"))
    hits = [r for r in raws
            if (r["yes"], r["no"]) == (db.get("yes_votes"), db.get("no_votes"))
            and (not question or r["question"] == question)]
    return hits[0] if len(hits) == 1 else None


def resolve_by_group_key(db_rows: list[dict], raws: list[dict]) -> dict[int, dict]:
    """Rows stored under ``Multi_MeasID``: map each stored row ``id`` to its
    one raw row by (group key, county, letter, yes, no)."""
    groups = collections.defaultdict(list)
    for raw in raws:
        groups[raw["multi_id"]].append(raw)
    resolved = {}
    for db in db_rows:
        hits = [r for r in groups.get(str(db["measure_id"]), [])
                if r["county"] == canonical_county(db.get("county"))
                and r["letter"] == norm_letter(db.get("measure_letter"))
                and (r["yes"], r["no"]) == (db.get("yes_votes"), db.get("no_votes"))]
        if len(hits) == 1:
            resolved[db["id"]] = hits[0]
    return resolved


def _same_identity(db: dict, raw: dict) -> bool:
    return (raw["county"] == canonical_county(db.get("county"))
            and raw["letter"] == norm_letter(db.get("measure_letter")))


def detect_key_mode(db_rows: list[dict], raws: list[dict]) -> str:
    """``"group"`` when the stored IDs are the file's ``Multi_MeasID`` values,
    ``"own"`` when they are the rows' own IDs. Decided from the data: a year
    is group-keyed only if more stored rows resolve through the group key
    than agree with the raw row under their own ID. The header name is not
    evidence; a correctly rekeyed 2014 still has a ``MeasureID`` header."""
    by_id = collections.defaultdict(list)
    for raw in raws:
        by_id[raw["id"]].append(raw)
    own = sum(1 for db in db_rows
              if any(_same_identity(db, raw) for raw in by_id.get(str(db["measure_id"]), [])))
    grouped = len(resolve_by_group_key(db_rows, raws))
    return "group" if grouped > own else "own"


def _source(raw: dict) -> dict:
    return {**raw["src"], "county": raw["county"], "letter": raw["letter"], "place": raw["place"]}


def _describe(entry: dict, db: dict, raw: dict) -> str:
    """Attach the field comparison to a ledger entry; return its class."""
    entry["fields"] = compare_row(db, raw)
    entry["own"] = {"county": raw["county"], "place": raw["place"], "letter": raw["letter"],
                    "type": raw["type_name"], "outcome": outcome_of(raw["passfail"]),
                    "combined_outcome": outcome_of(raw["passfail_sum"]), "multi_co": raw["multi_co"]}
    entry["stored"] = {"passed": db.get("passed"), "pass_fail": db.get("pass_fail"),
                       "category_type": db.get("category_type"),
                       "has_summary": bool(clean_text(db.get("summary_text")))}
    entry["unloaded"] = sorted(f for f, v in entry["fields"].items() if v == DB_EMPTY and f not in CORE_FIELDS)
    entry["placeholder_title"] = entry["fields"]["title"] == FORMAT and not (
        clean_text(db.get("title")) and raw["question"].startswith(clean_text(db.get("title"))))
    return classify(entry["fields"])


def reconcile_year(year: int, db_rows: list[dict], raws: list[dict]) -> dict:
    """Classify every stored and raw row of one year."""
    candidates = collections.defaultdict(list)
    for raw in raws:
        candidates[raw["id"]].append(raw)
    # The same ID on two raw rows (two files, or two releases) is reported,
    # never resolved by letting the later row replace the earlier one.
    collisions = {key: rows for key, rows in candidates.items() if len(rows) > 1}
    by_id = {key: rows[0] for key, rows in candidates.items() if len(rows) == 1}
    key_mode = detect_key_mode(db_rows, raws)
    resolved = resolve_by_group_key(db_rows, raws) if key_mode == "group" else {}
    # An ID is "shared" when two raw rows carry it, or two stored rows do (the
    # repaired state: both measures kept, told apart by county and
    # designation). Shared IDs are matched on identity, never on the ID alone.
    stored_by_id = collections.defaultdict(list)
    for db in db_rows:
        stored_by_id[str(db["measure_id"])].append(db)
    shared = set(collisions) | {key for key, rows in stored_by_id.items() if len(rows) > 1 and key_mode == "own"}
    unresolved = {key for key in collisions
                  if any(sum(_same_identity(db, raw) for db in stored_by_id.get(key, [])) != 1
                         for raw in collisions[key])}
    entries, represented = [], set()
    own_vote_mismatch = 0
    for db in db_rows:
        measure_id = str(db["measure_id"])
        own = by_id.get(measure_id)
        if own is not None and (own["yes"], own["no"]) != (db.get("yes_votes"), db.get("no_votes")):
            own_vote_mismatch += 1
        entry = {"id": db["id"], "measure_id": measure_id, "year": year, "updated_at": db.get("updated_at")}
        if measure_id in shared:
            entry["raw_candidates"] = [_source(raw) for raw in candidates.get(measure_id, [])]
            held = [raw for raw in candidates.get(measure_id, []) if _same_identity(db, raw)]
            if len(held) == 1:
                represented.add(id(held[0]))
                entry["content_class"] = _describe(entry, db, held[0])
                entry["stored_candidate"] = _source(held[0])
                entry["class"] = "id_collision" if measure_id in unresolved else entry["content_class"]
            else:
                # A stored measure that no loaded file carries under this ID.
                entry["class"] = "missing_from_raw"
        elif key_mode == "group":
            target = resolved.get(db["id"])
            if target is None:
                entry["class"] = "missing_from_raw"
            else:
                represented.add(id(target))
                entry["content_class"] = _describe(entry, db, target)
                entry["raw_id"] = target["id"]
                entry["class"] = "wrong_key" if target["id"] != measure_id else entry["content_class"]
        elif own is None:
            entry["class"] = "missing_from_raw"
        else:
            represented.add(id(own))
            entry["class"] = _describe(entry, db, own)
            if any(entry["fields"][f] == DIFF for f in IDENTITY_FIELDS):
                owner = find_content_owner(db, raws)
                if owner is not None and owner["id"] != own["id"]:
                    entry["class"], entry["content_of"] = "wrong_row", owner["id"]
                elif owner is None and entry["fields"]["yes_votes"] == DIFF:
                    entry["class"] = "foreign"
        entries.append(entry)
    missing = [{"class": "missing_from_db", "year": year, "measure_id": raw["id"],
                "county": raw["county"], "letter": raw["letter"], "place": raw["place"],
                "multi_co": raw["multi_co"], "id_collision": raw["id"] in collisions, "src": raw["src"]}
               for raw in raws if id(raw) not in represented]
    flips = sum(1 for raw in raws
                if None not in (outcome_of(raw["passfail"]), outcome_of(raw["passfail_sum"]))
                and outcome_of(raw["passfail"]) != outcome_of(raw["passfail_sum"]))
    return {
        "year": year, "file_rows": len(raws), "db_rows": len(db_rows), "key_mode": key_mode,
        "id_matched": sum(1 for db in db_rows if str(db["measure_id"]) in candidates),
        "own_vote_mismatch": own_vote_mismatch,
        "outcome_flips": flips,
        "repeated_ids": [{"year": year, "measure_id": key, "resolved": key not in unresolved,
                          "rows": [_source(raw) for raw in rows]}
                         for key, rows in sorted(collisions.items())],
        "classes": dict(collections.Counter(e["class"] for e in entries + missing)),
        "entries": entries, "missing_from_db": missing,
    }


def group_violations(raws: list[dict]) -> list[str]:
    """Multi-county groups must agree on their combined fields, and the
    combined yes count must equal the members' sum."""
    groups = collections.defaultdict(list)
    for raw in raws:
        if raw["multi_co"] == 1:
            groups[raw["multi_id"]].append(raw)
    problems = []
    for key, members in groups.items():
        for field in ("yes_sum", "no_sum", "total_sum", "passfail_sum", "req", "date"):
            if len({m[field] for m in members}) > 1:
                problems.append(f"{key}: members disagree on {field}")
        if len(members) > 1 and sum(m["yes"] or 0 for m in members) != members[0]["yes_sum"]:
            problems.append(f"{key}: YES_sum is not the members' sum")
    return problems


# --------------------------------------------------------------------------
# Database, baseline and CSV stand-in
# --------------------------------------------------------------------------

def open_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def ceda_rows(connection: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in connection.execute(
        "SELECT * FROM measures WHERE data_source = 'CEDA' ORDER BY id")]


def sha256_of(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def baseline_report(current: list[dict], baseline: list[dict], entries: dict[int, dict]) -> dict:
    """Date the wrong-row defect against an older database (ids are stable)."""
    old = {row["id"]: row for row in baseline}
    letter_keyed = sum(1 for row in baseline if "|MEASURE_" in (row.get("fingerprint") or ""))
    overwritten = {i for i, row in old.items() if (row.get("update_count") or 0) > 0}
    cross = collections.Counter()
    already_wrong = 0
    for row in current:
        entry = entries.get(row["id"])
        if entry is None or row["id"] not in old:
            continue
        cross[("overwritten" if row["id"] in overwritten else "single", entry["class"])] += 1
        if entry["class"] == "wrong_row":
            before = old[row["id"]]
            same = ((before.get("yes_votes"), before.get("no_votes")) == (row.get("yes_votes"), row.get("no_votes"))
                    and clean_text(before.get("ballot_question")) == clean_text(row.get("ballot_question")))
            already_wrong += same
    return {
        "baseline_ceda_rows": len(baseline),
        "baseline_letter_keyed_fingerprints": letter_keyed,
        "baseline_rows_overwritten_at_load": len(overwritten),
        "current_rows_also_in_baseline": sum(1 for row in current if row["id"] in old),
        "class_by_baseline_state": {f"{a}|{b}": n for (a, b), n in sorted(cross.items())},
        "wrong_rows_identical_in_baseline": already_wrong,
        "baseline_rows_by_year": dict(sorted(collections.Counter(r["year"] for r in baseline).items())),
    }


def load_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def release_conflicts(csv_rows: list[dict], raws: list[dict], current: list[dict],
                      baseline: list[dict] | None = None) -> list[dict]:
    """IDs that name different measures in two CEDA releases.

    ``ceda_parsed.csv`` was parsed from a different release than some raw
    files we hold. Where the two give one (year, ID) a different county or
    designation, an ingest that matches on the ID overwrites one measure with
    the other. Each conflict lists both identities, which one the database
    holds now, and which it held in the baseline."""
    def identity(county, letter):
        return (canonical_county(county), norm_letter(letter))

    def votes(value):
        return None if value in (None, "") else int(float(value))

    raws_by_year = collections.defaultdict(list)
    for raw in raws:
        raws_by_year[raw["year"]].append(raw)
    csv_by_year = collections.defaultdict(list)
    for row in csv_rows:
        csv_by_year[int(row["year"])].append(row)
    # A CSV year keyed on the group ID (2014) says nothing about ID reuse:
    # every member row "conflicts". Such years are skipped here.
    skipped = {year for year, rows in csv_by_year.items() if year in raws_by_year and detect_key_mode(
        [{"measure_id": r["measure_id"], "county": r["county"], "measure_letter": r["measure_letter"],
          "yes_votes": votes(r["yes_votes"]), "no_votes": votes(r["no_votes"]), "id": n}
         for n, r in enumerate(rows)], raws_by_year[year]) == "group"}
    from_csv = collections.defaultdict(set)
    for row in csv_rows:
        if int(row["year"]) not in skipped:
            from_csv[(int(row["year"]), str(row["measure_id"]))].add(identity(row["county"], row["measure_letter"]))
    from_raw = collections.defaultdict(set)
    for raw in raws:
        from_raw[(raw["year"], raw["id"])].add((raw["county"], raw["letter"]))
    stored = collections.defaultdict(list)
    for row in current:
        stored[(row["year"], str(row["measure_id"]))].append(row)
    before = {row["id"]: row for row in baseline or []}
    conflicts = []
    for key in sorted(set(from_csv) & set(from_raw)):
        identities = from_csv[key] | from_raw[key]
        if len(identities) < 2:
            continue
        rows = stored.get(key, [])
        conflicts.append({
            "year": key[0], "measure_id": key[1],
            "raw": sorted(" ".join(i) for i in from_raw[key]), "csv": sorted(" ".join(i) for i in from_csv[key]),
            "stored": [{"id": r["id"], "identity": " ".join(identity(r["county"], r["measure_letter"]))} for r in rows],
            "stored_in_baseline": [{"id": r["id"], "identity": " ".join(identity(before[r["id"]]["county"], before[r["id"]]["measure_letter"]))}
                                   for r in rows if r["id"] in before],
            "identities_not_stored": sorted(" ".join(i) for i in identities
                                            - {identity(r["county"], r["measure_letter"]) for r in rows}),
        })
    return conflicts


def csv_report(csv_rows: list[dict], current: list[dict], raw_by_year: dict[int, list[dict]],
               reconciled: set[int] = frozenset()) -> dict:
    """How well ``ceda_parsed.csv`` tracks raw where we hold raw, and how the
    database tracks the CSV in the years with no raw file.

    ``reconciled`` rows have a raw row from another year's file. They are
    still compared here, and counted, so a row that disagrees with the CSV
    cannot drop out of the total."""
    def key(year, measure_id, county, letter):
        return (int(year), str(measure_id), canonical_county(county), norm_letter(letter))

    csv_index = {key(r["year"], r["measure_id"], r["county"], r["measure_letter"]): r for r in csv_rows}

    def votes(row):
        return tuple(None if row[f] in (None, "") else int(float(row[f])) for f in ("yes_votes", "no_votes"))

    fidelity = collections.Counter()
    for year, raws in raw_by_year.items():
        for raw in raws:
            row = csv_index.get(key(raw["year"], raw["id"], raw["county"], raw["letter"]))
            if row is None:
                fidelity["raw_row_not_in_csv"] += 1
            elif votes(row) == (raw["yes"], raw["no"]) and clean_text(row["pass_fail"]) == raw["passfail"]:
                fidelity["agree"] += 1
            else:
                fidelity["disagree"] += 1
    held = set(raw_by_year)
    proxy = collections.defaultdict(collections.Counter)
    detail = []
    for row in current:
        if row["year"] in held:
            continue
        match = csv_index.get(key(row["year"], row["measure_id"], row["county"], row["measure_letter"]))
        counter = proxy[row["year"]]
        counter["db_rows"] += 1
        if row["id"] in reconciled:
            counter["also_checked_against_raw"] += 1
        if match is None:
            counter["not_in_csv"] += 1
            detail.append({"id": row["id"], "measure_id": row["measure_id"], "year": row["year"], "issue": "not_in_csv"})
            continue
        differing = []
        if votes(match) != (row["yes_votes"], row["no_votes"]):
            differing.append("votes")
        if clean_text(match["pass_fail"]) != clean_text(row["pass_fail"]):
            differing.append("pass_fail")
        if (match["election_date"] or "")[:10] != (row["election_date"] or ""):
            differing.append("election_date")
        # The CSV's own ``passed`` column is unreliable (it dropped zeros), so
        # the stored outcome is checked against the stored code instead.
        if row["passed"] != outcome_of(row["pass_fail"]):
            differing.append("passed_vs_pass_fail")
        if clean_text(match["title"]) != clean_text(row["title"]):
            differing.append("title")
        counter["agree" if not differing else "differs"] += 1
        if differing:
            detail.append({"id": row["id"], "measure_id": row["measure_id"], "year": row["year"], "issue": differing})
    csv_years = collections.Counter(int(r["year"]) for r in csv_rows)
    csv_ids = collections.defaultdict(set)
    for r in csv_rows:
        csv_ids[int(r["year"])].add(r["measure_id"])
    for year, counter in proxy.items():
        counter["csv_rows"] = csv_years.get(year, 0)
        counter["csv_distinct_ids"] = len(csv_ids.get(year, ()))
    return {"csv_rows": len(csv_rows), "csv_vs_raw_in_held_years": dict(fidelity),
            "db_vs_csv_in_unheld_years": {y: dict(c) for y, c in sorted(proxy.items())},
            "unheld_detail": detail}


def load_reviewed_categories(path: Path) -> set[str]:
    """The reviewed history categories, from ``local_measure_context.py``
    (trusted project code, loaded by path so ``python -I`` still works)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("local_measure_context", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {" ".join(value.split()).casefold()
            for value in module.LOCAL_MEASURE_CATEGORY_CROSSWALK.values() if value}


def cohort_report(all_rows: list[dict], raw_by_year: dict[int, list[dict]], categories: set[str],
                  constant_years: set[int], before_year: int = 2026) -> dict:
    """County history cohorts as the site computes them, and as raw gives them.

    ``stored`` follows ``attach_local_historical_context``: active rows that
    are not registrar rows, with ``passed`` 0 or 1, grouped by the stored
    county (compared case-insensitively, so ``SAN BERNADINO`` is its own
    county) and reviewed category. The two raw columns replace the CEDA rows
    of every held year with the raw rows of that year: ``raw_per_row`` uses
    each county's own ``PASSFAIL``, ``raw_combined`` uses ``passfail_sum``.
    ``constant_years`` (years stored under the wrong key) keep their stored
    rows in all three columns. Counties are those with registrar rows."""
    def squeeze(value):
        return " ".join(str(value or "").split()).casefold()

    def registrar(row):
        return str(row.get("data_source") or "").casefold().endswith("_county_registrar")

    counties = sorted({squeeze(row["county"]) for row in all_rows if registrar(row)})
    replaced = {year for year in raw_by_year if year not in constant_years}
    table = collections.defaultdict(lambda: {"stored": [0, 0], "raw_per_row": [0, 0], "raw_combined": [0, 0]})
    for row in all_rows:
        if registrar(row) or row.get("passed") not in (0, 1) or row.get("is_duplicate") or row.get("is_active") == 0:
            continue
        county, category = squeeze(row["county"]), squeeze(row["category_type"])
        try:
            year = int(row["year"])
        except (TypeError, ValueError):
            continue
        if county not in counties or category not in categories or year >= before_year:
            continue
        columns = ["stored"]
        if not (row.get("data_source") == "CEDA" and year in replaced):
            columns += ["raw_per_row", "raw_combined"]
        for column in columns:
            table[(county, category)][column][0] += row["passed"]
            table[(county, category)][column][1] += 1
    differing = []
    for year in sorted(replaced):
        for raw in raw_by_year[year]:
            county, category = raw["county"].casefold(), raw["type_name"].casefold()
            if county not in counties or category not in categories or year >= before_year:
                continue
            own, combined = outcome_of(raw["passfail"]), outcome_of(raw["passfail_sum"])
            for column, outcome in (("raw_per_row", own), ("raw_combined", combined)):
                if outcome in (0, 1):
                    table[(county, category)][column][0] += outcome
                    table[(county, category)][column][1] += 1
            if own != combined:
                differing.append({"year": year, "measure_id": raw["id"], "county": raw["county"],
                                  "category": raw["type_name"], "place": raw["place"], "letter": raw["letter"],
                                  "own": own, "combined": combined, "multi_co": raw["multi_co"], "req": raw["req"]})
    return {
        "counties": counties, "raw_years": sorted(replaced), "stored_years_kept": sorted(constant_years),
        "cohorts": {f"{county} | {category}": values for (county, category), values in sorted(table.items())},
        "own_and_combined_outcomes_differ": differing,
    }


_WORD = re.compile(r"[a-z]{5,}|\d[\d,.]*\d|\d")


def distinctive_overlap(summary: str, source: str) -> float:
    """Share of a summary's longer words and numbers that occur in ``source``."""
    words = set(_WORD.findall(clean_text(summary).casefold()))
    if not words:
        return 0.0
    pool = set(_WORD.findall(clean_text(source).casefold()))
    return len(words & pool) / len(words)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def run(args) -> dict:
    files = discover_raw_files(Path(args.downloads), Path(args.raw_dir))
    raw_by_file_year = {year: load_raw_file(path) for year, path in sorted(files.items())}
    # A row belongs to its own YEAR: the 2015 file carries one 2016 measure.
    raw_by_year: dict[int, list[dict]] = collections.defaultdict(list)
    for file_year, raws in raw_by_file_year.items():
        for raw in raws:
            raw_by_year[file_year if raw["year"] is None else raw["year"]].append(raw)
    stray = {year: raws for year, raws in raw_by_year.items() if year not in files}

    connection = open_readonly(Path(args.db))
    current = ceda_rows(connection)
    stamp_by_source = dict(connection.execute(
        "SELECT data_source, COUNT(*) FROM measures WHERE updated_at LIKE ? GROUP BY 1", (args.stamp + "%",)).fetchall())
    all_rows = [dict(row) for row in connection.execute("SELECT * FROM measures")]
    connection.close()
    db_by_year = collections.defaultdict(list)
    for row in current:
        db_by_year[row["year"]].append(row)

    years, entries, ledger = {}, {}, []
    for year in sorted(files):
        raws = raw_by_year.get(year, [])
        result = reconcile_year(year, db_by_year.get(year, []), raws)
        result["source_file"] = files[year].name
        result["rows_in_file"] = len(raw_by_file_year[year])
        result["group_violations"] = group_violations(raws)
        for entry in result.pop("entries"):
            entries[entry["id"]] = entry
            if entry["class"] != "match":
                ledger.append(entry)
        ledger.extend(result.pop("missing_from_db"))
        years[year] = result
    for year, raws in stray.items():  # e.g. the 2016 row inside the 2015 file
        ids = {raw["id"] for raw in raws}
        result = reconcile_year(year, [r for r in db_by_year.get(year, []) if str(r["measure_id"]) in ids], raws)
        for entry in result.pop("entries"):
            entries[entry["id"]] = entry
            if entry["class"] != "match":
                ledger.append(entry)
        ledger.extend(result.pop("missing_from_db"))
        years[f"{year} (row held in another year's file)"] = result

    stamped = [row for row in current if str(row.get("updated_at") or "").startswith(args.stamp)]
    compared = [e for e in entries.values() if "fields" in e]
    summary = {
        "db": str(args.db), "held_years": sorted(files), "years": years,
        "tool_sha256": sha256_of(Path(__file__)),
        "raw_files": {year: {"file": path.name, "sha256": sha256_of(path), "bytes": path.stat().st_size,
                             "rows": len(raw_by_file_year[year])} for year, path in sorted(files.items())},
        "repeated_ids": [item for data in years.values() for item in data["repeated_ids"]],
        "unloaded_fields": dict(collections.Counter(f for e in compared for f in e["unloaded"])),
        "match_rows_with_an_unloaded_field": sum(1 for e in compared if e["class"] == "match" and e["unloaded"]),
        "placeholder_title_rows": sum(1 for e in compared if e["placeholder_title"]),
        "format_only_by_placeholder_title_alone": sum(
            1 for e in compared if e["class"] == "format_only" and e["placeholder_title"]
            and [f for f, v in e["fields"].items() if v == FORMAT] == ["title"]),
        "totals": dict(collections.Counter(e["class"] for e in ledger) + collections.Counter(
            {"match": sum(1 for e in entries.values() if e["class"] == "match")})),
        "field_status": {field: dict(collections.Counter(
            e["fields"][field] for e in entries.values() if "fields" in e))
            for field in ("county", "letter", "election_date", "yes_votes", "no_votes", "total_votes", "percent_yes",
                          "pass_fail", "passed", "jurisdiction", "category_type", "category_topic",
                          "ballot_question", "title")},
        "stamp": {
            "value": args.stamp, "rows_by_source": stamp_by_source,
            "ceda_rows_by_year": dict(sorted(collections.Counter(r["year"] for r in stamped).items())),
            "ceda_class": dict(collections.Counter(entries[r["id"]]["class"] for r in stamped if r["id"] in entries)),
            "wrong_rows_outside_stamp": sum(1 for e in entries.values() if e["class"] == "wrong_row"
                                            and not str(e.get("updated_at") or "").startswith(args.stamp)),
        },
        "ceda_rows_without_raw_by_year": dict(sorted(collections.Counter(
            r["year"] for r in current if r["id"] not in entries).items())),
    }
    summary["passed_null_by_year"] = dict(sorted(collections.Counter(
        r["year"] for r in current if r["passed"] is None).items()))
    owners = collections.Counter(e["content_of"] for e in entries.values() if e["class"] == "wrong_row")
    by_measure = {(r["year"], str(r["measure_id"])): r for r in current}
    summary["wrong_row_sources_also_stored_correctly"] = sum(
        1 for e in entries.values() if e["class"] == "wrong_row"
        and (e["year"], e["content_of"]) in by_measure
        and entries.get(by_measure[(e["year"], e["content_of"])]["id"], {}).get("class") in ("match", "format_only", "differs"))
    summary["wrong_row_distinct_sources"] = len(owners)
    wrong = [e for e in entries.values() if e["class"] == "wrong_row"]
    summary["wrong_row_stored_outcome"] = dict(collections.Counter(
        "null" if e["stored"]["passed"] is None
        else "agrees_with_own" if e["stored"]["passed"] == e["own"]["outcome"] else "contradicts_own"
        for e in wrong))
    summary["wrong_rows_with_summary_text"] = sum(
        1 for r in current if entries.get(r["id"], {}).get("class") == "wrong_row" and clean_text(r.get("summary_text")))

    baseline = None
    if args.baseline_db:
        base = open_readonly(Path(args.baseline_db))
        baseline = ceda_rows(base)
        base.close()
    if args.csv:
        csv_rows = load_csv(Path(args.csv))
        conflicts = release_conflicts(csv_rows, [raw for raws in raw_by_year.values() for raw in raws],
                                      current, baseline)
        summary["release_conflicts"] = conflicts
        for conflict in conflicts:
            held_before = {item["id"]: item["identity"] for item in conflict["stored_in_baseline"]}
            for item in conflict["stored"]:
                entry = entries.get(item["id"])
                if entry is None:
                    continue
                entry["release_conflict"] = {k: conflict[k] for k in ("raw", "csv", "identities_not_stored")}
                if item["id"] in held_before and held_before[item["id"]] != item["identity"]:
                    # The row held another measure in the baseline: it was
                    # overwritten through the reused ID after the baseline.
                    entry["class_before_id_check"] = entry["class"]
                    entry["class"] = "id_reused"
                    entry["baseline_identity"] = held_before[item["id"]]
                    if entry not in ledger:
                        ledger.append(entry)
    summary["totals"] = dict(collections.Counter(e["class"] for e in entries.values())
                             + collections.Counter(e["class"] for e in ledger if e["class"] == "missing_from_db"))
    if args.context_module and Path(args.context_module).exists():
        constant = {year for year, data in years.items() if isinstance(year, int) and data["key_mode"] == "group"}
        summary["cohorts"] = cohort_report(all_rows, {y: r for y, r in raw_by_year.items() if y in files},
                                           load_reviewed_categories(Path(args.context_module)), constant)
    blocking = ("wrong_row", "wrong_key", "id_collision", "id_reused", "incomplete", "differs", "foreign",
                "missing_from_db", "missing_from_raw")
    # A waiver names one (year, ID) whose known defect is deferred by a
    # recorded decision. It is echoed in the output, never applied silently.
    waived = {tuple(item.split(":", 1)) for item in (args.waive or "").split(",") if ":" in item}
    is_waived = lambda e: (str(e["year"]), str(e["measure_id"])) in waived
    counts = collections.Counter(e["class"] for e in entries.values() if not is_waived(e))
    counts["missing_from_db"] = sum(1 for e in ledger if e["class"] == "missing_from_db" and not is_waived(e))
    summary["gate"] = {
        "blocking": {name: counts[name] for name in blocking if counts[name]},
        "repeated_ids": sum(1 for item in summary["repeated_ids"] if not item["resolved"] and not is_waived(item)),
        "release_conflicts_with_an_identity_not_stored": sum(
            1 for c in summary.get("release_conflicts", []) if c["identities_not_stored"] and not is_waived(c)),
        "group_violations": sum(len(data.get("group_violations") or []) for data in years.values()),
        "waived": sorted(":".join(item) for item in waived),
    }
    summary["gate"]["clean"] = not (summary["gate"]["blocking"] or summary["gate"]["repeated_ids"]
                                    or summary["gate"]["release_conflicts_with_an_identity_not_stored"]
                                    or summary["gate"]["group_violations"])
    if baseline is not None:
        summary["baseline"] = baseline_report(current, baseline, entries)
        old = {row["id"]: row for row in baseline}
        # Summaries written from a sibling's question, on rows since repaired.
        raw_lookup = {(raw["year"], raw["id"]): raw for raws in raw_by_year.values() for raw in raws}
        suspect = []
        checked = 0
        for row in current:
            before = old.get(row["id"])
            text = clean_text(row.get("summary_text"))
            if not text or before is None or not (before.get("update_count") or 0):
                continue
            raw = raw_lookup.get((row["year"], str(row["measure_id"])))
            own = raw["question"] if raw else clean_text(row.get("ballot_question")) or clean_text(row.get("title"))
            sibling = clean_text(before.get("ballot_question"))
            if not sibling or sibling == own:
                continue
            checked += 1
            own_score, sibling_score = distinctive_overlap(text, own), distinctive_overlap(text, sibling)
            if sibling_score - own_score >= 0.25:
                suspect.append({"id": row["id"], "measure_id": row["measure_id"], "year": row["year"],
                                "row_class": entries.get(row["id"], {}).get("class", "no_raw"),
                                "own": round(own_score, 2), "sibling": round(sibling_score, 2)})
        summary["summaries_from_sibling_question"] = {
            "rows_checked": checked, "suspect": len(suspect),
            "suspect_by_class": dict(collections.Counter(s["row_class"] for s in suspect)),
            "suspect_by_year": dict(sorted(collections.Counter(s["year"] for s in suspect).items())),
        }
        ledger.extend({"class": "summary_from_sibling", **s} for s in suspect)
    if args.csv:
        report = csv_report(csv_rows, current,
                            {y: r for y, r in raw_by_year.items() if y in files}, set(entries))
        ledger.extend({"class": "unheld_year_vs_csv", **d} for d in report.pop("unheld_detail"))
        summary["csv"] = report
    return {"summary": summary, "ledger": ledger}


def main(argv=None) -> int:
    here = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True, help="database to read (opened mode=ro)")
    parser.add_argument("--out", required=True, help="folder for summary.json and ledger.json")
    parser.add_argument("--downloads", default=str(here / "data" / "raw" / "ceda_downloads_20261111"))
    parser.add_argument("--raw-dir", default=str(here / "data" / "raw"))
    parser.add_argument("--baseline-db", help="older database, to date the defect (opened mode=ro)")
    parser.add_argument("--csv", help="ceda_parsed.csv, a stand-in for years with no raw file")
    parser.add_argument("--stamp", default="2026-04-12 17:50:43", help="updated_at prefix to profile")
    parser.add_argument("--context-module", default=str(here / "src" / "website" / "local_measure_context.py"),
                        help="local_measure_context.py, for the reviewed cohort categories")
    parser.add_argument("--gate", action="store_true",
                        help="exit 1 unless the reconciliation is clean (for use after the P1b.2 repair)")
    parser.add_argument("--waive", default="",
                        help="comma-separated YEAR:MEASURE_ID keys whose defect a recorded decision defers")
    args = parser.parse_args(argv)
    before = sha256_of(Path(args.db))
    result = run(args)
    result["summary"]["db_sha256_before"] = before
    result["summary"]["db_sha256_after"] = sha256_of(Path(args.db))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(result["summary"], indent=1, default=str) + "\n", encoding="utf-8")
    (out / "ledger.json").write_text(json.dumps(result["ledger"], indent=0, default=str) + "\n", encoding="utf-8")
    for year, data in result["summary"]["years"].items():
        print(year, data["file_rows"], data["db_rows"], data["id_matched"], data["own_vote_mismatch"],
              data["outcome_flips"], data["classes"])
    print("totals", result["summary"]["totals"])
    print("gate", result["summary"]["gate"])
    if before != result["summary"]["db_sha256_after"]:
        return 2
    return 1 if args.gate and not result["summary"]["gate"]["clean"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
