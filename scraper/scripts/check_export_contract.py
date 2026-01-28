#!/usr/bin/env python3
"""
Export contract check: verifies exported CSV/JSON columns match the canonical list.
Run after any change to export_data.py to catch column drift.
"""
import csv
import json
import sys
from pathlib import Path

# Canonical export columns (CSV includes computed summary_length)
CSV_COLUMNS = [
    "measure_id", "year", "county", "jurisdiction", "title",
    "summary_title", "summary_text", "summary_length",
    "passed", "pass_fail", "yes_votes", "no_votes", "total_votes",
    "percent_yes", "percent_no", "topic_primary", "topic_secondary",
    "measure_type", "data_source", "has_summary", "election_date",
    "election_type", "source_url", "ballot_question", "description"
]

JSON_COLUMNS = [
    "measure_id", "year", "county", "jurisdiction", "title",
    "summary_title", "summary_text",
    "passed", "pass_fail", "yes_votes", "no_votes", "total_votes",
    "percent_yes", "percent_no", "topic_primary", "topic_secondary",
    "measure_type", "data_source", "has_summary", "election_date",
    "source_url"
]

def check_csv(path: Path) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
    if header != CSV_COLUMNS:
        print(f"FAIL CSV: expected {len(CSV_COLUMNS)} columns, got {len(header)}")
        print(f"  Expected: {CSV_COLUMNS}")
        print(f"  Got:      {header}")
        missing = set(CSV_COLUMNS) - set(header)
        extra = set(header) - set(CSV_COLUMNS)
        if missing:
            print(f"  Missing: {missing}")
        if extra:
            print(f"  Extra:   {extra}")
        return False
    print(f"OK CSV: {len(header)} columns match contract")
    return True

def check_json(path: Path) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        print("FAIL JSON: empty file")
        return False
    keys = list(data[0].keys())
    if keys != JSON_COLUMNS:
        print(f"FAIL JSON: expected {len(JSON_COLUMNS)} keys, got {len(keys)}")
        print(f"  Expected: {JSON_COLUMNS}")
        print(f"  Got:      {keys}")
        return False
    print(f"OK JSON: {len(keys)} keys match contract")
    return True

def main():
    exports_dir = Path(__file__).parent.parent / "data" / "exports"
    csv_files = sorted(exports_dir.glob("ballot_measures_*.csv"))
    json_files = sorted(exports_dir.glob("ballot_measures_*.json"))

    ok = True
    if csv_files:
        ok = check_csv(csv_files[-1]) and ok
    else:
        print("WARN: no CSV export found")

    if json_files:
        ok = check_json(json_files[-1]) and ok
    else:
        print("WARN: no JSON export found")

    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
