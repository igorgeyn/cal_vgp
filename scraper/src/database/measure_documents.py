"""Current official document-role associations; raw snapshots retain history."""
from __future__ import annotations

import re
import sqlite3
from urllib.parse import urlsplit


SCHEMA = """
CREATE TABLE IF NOT EXISTS measure_documents (
    measure_id INTEGER NOT NULL REFERENCES measures(id),
    role TEXT NOT NULL,
    source_url TEXT NOT NULL,
    snapshot_filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    content_type TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    captured_at TEXT,
    source_page_url TEXT NOT NULL,
    PRIMARY KEY (measure_id, role)
)
"""

FIELDS = (
    "role", "source_url", "snapshot_filename", "sha256", "size_bytes",
    "content_type", "snapshot_id", "captured_at", "source_page_url",
)

# A new observation of identical bytes/link metadata is a provenance refresh,
# not a document change. Archive filenames are also capture bookkeeping.
CONTENT_FIELDS = ("role", "source_url", "sha256", "size_bytes", "content_type")
PUBLIC_FIELDS = ("source_url", "sha256", "size_bytes", "content_type", "captured_at", "source_page_url")

ROLE_LABELS = {
    "text": "Full ballot text",
    "analysis": "Impartial analysis",
    "tax_rate_statement": "Tax rate statement",
    "argument_for": "Argument in favor",
    "argument_against": "Argument against",
    "rebuttal_for": "Rebuttal to argument in favor",
    "rebuttal_against": "Rebuttal to argument against",
    "resolution": "Resolution",
    "notice": "Notice of election",
    "packet": "Measure packet",
}


def has_documents_table(connection: sqlite3.Connection) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'measure_documents'"
    ).fetchone() is not None


def validate_document(document: dict) -> None:
    """Reject malformed metadata before it can become a public link."""
    for field in ("role", "source_url", "snapshot_filename", "sha256", "content_type"):
        if not isinstance(document.get(field), str) or not document[field].strip():
            raise ValueError(f"document lacks nonempty {field}")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", document["role"]):
        raise ValueError("invalid document role")
    url = document["source_url"]
    parsed = urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or any(ord(c) < 32 for c in url)):
        raise ValueError("document source_url must be an absolute HTTP(S) URL")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", document["sha256"]):
        raise ValueError("invalid document sha256")
    size = document.get("size_bytes")
    if type(size) is not int or size < 0:
        raise ValueError("invalid document size_bytes")


def document_rows(record: dict) -> tuple[dict, ...]:
    return tuple(
        {
            **{field: document[field] for field in FIELDS[:6]},
            "snapshot_id": record["snapshot_id"],
            "captured_at": record.get("scraped_at"),
            "source_page_url": record["measure"]["source_url"],
        }
        for document in record["documents"]
    )


def read_document_rows(connection: sqlite3.Connection, measure_id: int) -> tuple[dict, ...]:
    if not has_documents_table(connection):
        return ()
    rows = connection.execute(
        f"SELECT {', '.join(FIELDS)} FROM measure_documents WHERE measure_id = ? ORDER BY role",
        (measure_id,),
    ).fetchall()
    return tuple(dict(zip(FIELDS, row)) for row in rows)


def documents_for_website(connection: sqlite3.Connection) -> dict[int, list[dict]]:
    """Group composite documents per measure, without merging different bytes."""
    if not has_documents_table(connection):
        return {}
    grouped: dict[int, dict[tuple[str, str], dict]] = {}
    cursor = connection.execute(
        "SELECT d.* FROM measure_documents d JOIN measures m ON m.id = d.measure_id "
        "WHERE m.is_active = 1 AND COALESCE(m.is_duplicate, 0) = 0 "
        "ORDER BY d.measure_id, d.role"
    )
    columns = [column[0] for column in cursor.description]
    for values in cursor:
        row = dict(zip(columns, values))
        # Validate again so hand-edited data cannot bypass the public link guard.
        validate_document(row)
        documents = grouped.setdefault(row["measure_id"], {})
        key = (row["source_url"], row["sha256"])
        if key not in documents:
            documents[key] = {field: row[field] for field in PUBLIC_FIELDS}
            documents[key]["roles"] = []
        documents[key]["roles"].append(row["role"])
    result = {}
    priority = {role: index for index, role in enumerate(ROLE_LABELS)}
    for measure_id, documents in grouped.items():
        for document in documents.values():
            document["roles"].sort(key=lambda role: (priority.get(role, 999), role))
            document["labels"] = [
                ROLE_LABELS.get(role, role.replace("_", " ").capitalize())
                for role in document["roles"]
            ]
        result[measure_id] = sorted(
            documents.values(),
            key=lambda doc: (priority.get(doc["roles"][0], 999), doc["source_url"], doc["sha256"]),
        )
    return result
