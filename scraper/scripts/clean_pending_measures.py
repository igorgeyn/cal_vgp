#!/usr/bin/env python3
"""
Clean up pending (2026+) CA SOS measures with placeholder titles or AI refusal summaries.
"""
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "ballot_measures.db"

REFUSAL_SUBSTRINGS = [
    "can't provide",
    "cannot provide",
    "cannot summarize",
    "i cannot summarize",
    "i cannot provide a summary",
    "can't help with that",
    "cannot help with that",
    "don't have any information",
    "do not have any information",
    "i don't have information",
    "no details about its content",
    "ballot text appears to be incomplete",
    "no substantive information",
    "only showing",
    "i'd be happy to provide",
    "if you could provide",
    "please share the details",
    "no information available",
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_refusal(text: str) -> bool:
    lower = (text or "").lower()
    return any(fragment in lower for fragment in REFUSAL_SUBSTRINGS)


def is_bad_title(title: str) -> bool:
    cleaned = normalize_text(title)
    if not cleaned:
        return True
    lower = cleaned.lower()
    if lower in {"unknown", "untitled measure"}:
        return True
    if lower.startswith(("please note", "summary date", "circulation deadline", "signatures required")):
        return True
    if re.fullmatch(r"[\(\)\[\]\d\s|:/\.-]+", cleaned):
        return True
    return len(cleaned) < 6


def humanize_measure_id(measure_id: str) -> str:
    if not measure_id:
        return ""
    if measure_id.startswith("INIT_"):
        return f"Initiative {measure_id.split('_', 1)[1]}"
    return measure_id.replace("_", " ")


def main() -> int:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute(
        """
        SELECT id, measure_id, title, summary_title, summary_text, has_summary
        FROM measures
        WHERE is_active = 1
          AND data_source = 'CA_SOS'
          AND year >= 2026
        """
    )

    updates = 0
    for row in cursor:
        update_fields = {}

        if is_bad_title(row["title"]):
            fallback = humanize_measure_id(row["measure_id"])
            if fallback:
                update_fields["title"] = fallback

        if row["summary_text"] and is_refusal(row["summary_text"]):
            update_fields["summary_text"] = None
            update_fields["summary_title"] = None
            update_fields["has_summary"] = 0

        if update_fields:
            set_clause = ", ".join(f"{col} = ?" for col in update_fields)
            params = list(update_fields.values()) + [row["id"]]
            conn.execute(f"UPDATE measures SET {set_clause} WHERE id = ?", params)
            updates += 1

    conn.commit()
    conn.close()

    print(f"Updated {updates} pending CA SOS records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
