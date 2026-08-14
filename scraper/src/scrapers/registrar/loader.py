"""Load normalized registrar JSONL into the ballot-measure database.

Dry-run is the default.  Commit mode validates and plans the complete batch,
backs up the database, then applies the plan in one SQLite transaction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from ...config import DB_PATH
from ...database.models import BallotMeasure
from ...database.operations import Database
from .parser import COUNTY_NAMES, DATA_SOURCE, SCHEMA_VERSION


_IDENTITY_RE = re.compile(r"^REG_([A-Z0-9]+)_(\d{8})_([0-9A-F]{64})$")
_REQUIRED_MEASURE_FIELDS = {
    "measure_id",
    "measure_letter",
    "year",
    "state",
    "county",
    "jurisdiction",
    "title",
    "description",
    "vote_threshold",
    "measure_type",
    "data_source",
    "source_url",
    "pdf_url",
    "election_type",
    "election_date",
}
_OUTCOME_FIELDS = (
    "yes_votes",
    "no_votes",
    "total_votes",
    "percent_yes",
    "percent_no",
    "passed",
    "pass_fail",
)
_SOURCE_OWNED_FIELDS = (
    "measure_letter",
    "state",
    "county",
    "jurisdiction",
    "title",
    "description",
    "vote_threshold",
    "measure_type",
    "source_url",
    "pdf_url",
    "election_type",
    "election_type_imputed",
    "election_date",
    "is_active",
)


class RegistrarLoadError(RuntimeError):
    """Base class for registrar load failures."""


class NormalizedDataError(RegistrarLoadError):
    """Raised when JSONL is not one complete normalized snapshot."""


@dataclass(frozen=True)
class NormalizedBatch:
    records: tuple[dict, ...]
    county_slug: str
    county: str
    election_date: str
    snapshot_id: str
    page_sha256: str


@dataclass(frozen=True)
class _Action:
    kind: str
    measure_id: str
    target_id: Optional[int] = None
    measure: Optional[BallotMeasure] = None
    updates: Optional[dict] = None
    note: str = ""


@dataclass(frozen=True)
class _Plan:
    actions: tuple[_Action, ...]
    conflicts: tuple[str, ...]


@dataclass(frozen=True)
class LoadReport:
    jsonl_path: Path
    db_path: Path
    commit_requested: bool
    committed: bool
    inserted: int
    updated: int
    deactivated: int
    skipped: int
    conflicts: tuple[str, ...]
    actions: tuple[str, ...]
    backup_path: Optional[Path] = None

    @property
    def changed(self) -> int:
        return self.inserted + self.updated + self.deactivated


def _normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return " ".join(str(value).casefold().split())


def _normalize_date(value: object) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%B %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _readonly_connection(db_path: Path) -> sqlite3.Connection:
    resolved = Path(db_path).resolve()
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _check_database_schema(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(measures)")}
    required = set(BallotMeasure.__dataclass_fields__)
    missing = sorted(required - columns)
    if missing:
        raise RegistrarLoadError(f"database measures table lacks required columns: {missing}")
    non_integer_years = connection.execute(
        "SELECT COUNT(*) FROM measures WHERE year IS NOT NULL AND typeof(year) != 'integer'"
    ).fetchone()[0]
    if non_integer_years:
        raise RegistrarLoadError(
            f"database has {non_integer_years} non-integer year values; refusing pre-backup schema repair"
        )


def read_normalized_jsonl(path: Path) -> NormalizedBatch:
    path = Path(path)
    records: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    raise NormalizedDataError(f"blank line at {path}:{line_number}")
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise NormalizedDataError(f"invalid JSON at {path}:{line_number}: {exc}") from exc
                if not isinstance(record, dict):
                    raise NormalizedDataError(f"record at {path}:{line_number} is not an object")
                records.append(record)
    except OSError as exc:
        raise NormalizedDataError(f"cannot read normalized JSONL {path}: {exc}") from exc
    if not records:
        raise NormalizedDataError(f"normalized JSONL is empty: {path}")

    first = records[0]
    scope_fields = ("county_slug", "election_date", "snapshot_id", "snapshot_row_count", "page_sha256")
    for field_name in scope_fields:
        if field_name not in first:
            raise NormalizedDataError(f"first record lacks {field_name!r}")
    expected_scope = {field_name: first[field_name] for field_name in scope_fields}
    row_count = first["snapshot_row_count"]
    if not isinstance(row_count, int) or row_count <= 0 or row_count != len(records):
        raise NormalizedDataError(
            f"snapshot_row_count={row_count!r} does not match JSONL records={len(records)}"
        )

    county_slug = first["county_slug"]
    if county_slug not in COUNTY_NAMES:
        raise NormalizedDataError(f"unsupported county_slug {county_slug!r}")
    election_date = first["election_date"]
    if _normalize_date(election_date) != election_date:
        raise NormalizedDataError(f"election_date is not canonical ISO: {election_date!r}")
    expected_identity_prefix = f"REG_{county_slug.upper()}_{election_date.replace('-', '')}_"

    seen_rows: set[int] = set()
    seen_ids: set[str] = set()
    for index, record in enumerate(records, 1):
        if record.get("schema_version") != SCHEMA_VERSION:
            raise NormalizedDataError(
                f"record {index} has unsupported schema_version {record.get('schema_version')!r}"
            )
        for field_name, expected in expected_scope.items():
            if record.get(field_name) != expected:
                raise NormalizedDataError(
                    f"record {index} mixes {field_name}: expected {expected!r}, got {record.get(field_name)!r}"
                )
        table_row = record.get("table_row")
        if not isinstance(table_row, int) or table_row in seen_rows:
            raise NormalizedDataError(f"record {index} has invalid/duplicate table_row {table_row!r}")
        seen_rows.add(table_row)

        measure = record.get("measure")
        documents = record.get("documents")
        lineage = record.get("lineage")
        if not isinstance(measure, dict) or not isinstance(documents, list) or not isinstance(lineage, dict):
            raise NormalizedDataError(f"record {index} lacks measure/documents/lineage objects")
        required_lineage = {
            "origin_snapshot_id",
            "origin_table_row",
            "origin_key_kind",
            "origin_key_value",
            "origin_key_sha256",
        }
        if not required_lineage.issubset(lineage):
            raise NormalizedDataError(f"record {index} has incomplete lineage metadata")
        missing_fields = sorted(_REQUIRED_MEASURE_FIELDS - measure.keys())
        if missing_fields:
            raise NormalizedDataError(f"record {index} measure lacks fields {missing_fields}")
        measure_id = measure["measure_id"]
        identity_match = _IDENTITY_RE.fullmatch(str(measure_id))
        if not identity_match or not str(measure_id).startswith(expected_identity_prefix):
            raise NormalizedDataError(f"record {index} has invalid explicit measure_id {measure_id!r}")
        if measure_id in seen_ids:
            raise NormalizedDataError(f"duplicate explicit measure_id {measure_id!r}")
        seen_ids.add(measure_id)
        origin_value = lineage["origin_key_value"]
        origin_hash = hashlib.sha256(str(origin_value).encode("utf-8")).hexdigest()
        if lineage["origin_key_sha256"] != origin_hash:
            raise NormalizedDataError(f"record {index} origin key checksum mismatch")
        identity_payload = json.dumps(
            [county_slug, election_date, lineage["origin_key_kind"], origin_value],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        expected_digest = hashlib.sha256(identity_payload).hexdigest().upper()
        if identity_match.group(3) != expected_digest:
            raise NormalizedDataError(f"record {index} measure_id does not match its lineage origin")
        if measure.get("data_source") != DATA_SOURCE:
            raise NormalizedDataError(f"record {index} has unexpected data_source {measure.get('data_source')!r}")
        if measure.get("county") != COUNTY_NAMES[county_slug]:
            raise NormalizedDataError(f"record {index} has unexpected county {measure.get('county')!r}")
        if measure.get("election_date") != election_date or measure.get("year") != int(election_date[:4]):
            raise NormalizedDataError(f"record {index} has inconsistent election date/year")
        if any(measure.get(field_name) is not None for field_name in _OUTCOME_FIELDS):
            raise NormalizedDataError(f"record {index} unexpectedly contains election results")

        roles: set[str] = set()
        text_urls = []
        for document in documents:
            if not isinstance(document, dict):
                raise NormalizedDataError(f"record {index} contains a non-object document")
            required_document = {"role", "source_url", "snapshot_filename", "sha256", "size_bytes", "content_type"}
            if not required_document.issubset(document):
                raise NormalizedDataError(f"record {index} has malformed document metadata")
            role = document["role"]
            if role in roles:
                raise NormalizedDataError(f"record {index} repeats document role {role!r}")
            roles.add(role)
            if role == "text":
                text_urls.append(document["source_url"])
        expected_pdf = text_urls[0] if text_urls else None
        if measure.get("pdf_url") != expected_pdf:
            raise NormalizedDataError(f"record {index} pdf_url does not match its text-role document")

        # Constructing the model here is intentional: it proves the explicit
        # ID, not title regexes, drives the generated fingerprints.
        model = _model_from_record(measure)
        expected_fp = f"{measure['year']}|{measure_id}|{measure['county']}|{DATA_SOURCE}"
        if model.fingerprint != expected_fp:
            raise NormalizedDataError(f"record {index} produced unexpected fingerprint {model.fingerprint!r}")

    if seen_rows != set(range(1, row_count + 1)):
        raise NormalizedDataError(f"table rows are not contiguous 1..{row_count}: {sorted(seen_rows)}")

    return NormalizedBatch(
        records=tuple(records),
        county_slug=county_slug,
        county=COUNTY_NAMES[county_slug],
        election_date=election_date,
        snapshot_id=first["snapshot_id"],
        page_sha256=first["page_sha256"],
    )


def _model_from_record(measure_data: dict) -> BallotMeasure:
    valid_fields = set(BallotMeasure.__dataclass_fields__)
    values = {key: value for key, value in measure_data.items() if key in valid_fields}
    # These are deliberately empty so BallotMeasure generates keys from the
    # supplied explicit measure_id.  They never enter the title-regex path.
    values["fingerprint"] = ""
    values["measure_fingerprint"] = ""
    values["content_hash"] = ""
    return BallotMeasure(**values)


def _content_hash_for(existing: dict, updates: dict) -> str:
    merged = {**existing, **updates}
    model = BallotMeasure(
        measure_id=merged.get("measure_id"),
        measure_letter=merged.get("measure_letter"),
        year=merged.get("year"),
        county=merged.get("county"),
        data_source=merged.get("data_source"),
        title=merged.get("title"),
        description=merged.get("description"),
        ballot_question=merged.get("ballot_question"),
    )
    return model.content_hash


def _different(existing: dict, field_name: str, value: object) -> bool:
    old = existing.get(field_name)
    if field_name == "election_date":
        return _normalize_date(old) != _normalize_date(value)
    if field_name in {"is_active", "is_duplicate", "election_type_imputed"}:
        return int(old or 0) != int(bool(value))
    return old != value


def _strict_cross_source_candidates(
    connection: sqlite3.Connection,
    model: BallotMeasure,
) -> list[dict]:
    if not model.measure_letter or model.measure_letter.upper() == "TBD":
        return []
    rows = connection.execute(
        """
        SELECT * FROM measures
        WHERE upper(county) = upper(?)
          AND year = ?
          AND upper(measure_letter) = upper(?)
          AND data_source != ?
          AND COALESCE(is_duplicate, 0) = 0
        """,
        (model.county, model.year, model.measure_letter, DATA_SOURCE),
    ).fetchall()
    candidates = []
    for row in rows:
        candidate = dict(row)
        if _normalize_date(candidate.get("election_date")) != _normalize_date(model.election_date):
            continue
        old_jurisdiction = _normalize_text(candidate.get("jurisdiction"))
        new_jurisdiction = _normalize_text(model.jurisdiction)
        if old_jurisdiction and new_jurisdiction and old_jurisdiction != new_jurisdiction:
            continue
        candidates.append(candidate)
    return candidates


def _exact_updates(existing: dict, model: BallotMeasure) -> dict:
    incoming = model.to_dict()
    updates = {
        field_name: incoming.get(field_name)
        for field_name in _SOURCE_OWNED_FIELDS
        if _different(existing, field_name, incoming.get(field_name))
    }
    if updates:
        new_hash = _content_hash_for(existing, updates)
        if existing.get("content_hash") != new_hash:
            updates["content_hash"] = new_hash
    return updates


def _adoption_updates(existing: dict, model: BallotMeasure) -> dict:
    incoming = model.to_dict()
    authoritative = {
        "measure_id": model.measure_id,
        "fingerprint": model.fingerprint,
        "measure_fingerprint": model.measure_fingerprint,
        "year": model.year,
        "data_source": model.data_source,
        "is_active": 1,
        "is_duplicate": 0,
        "duplicate_type": None,
        "master_id": None,
    }
    for field_name in _SOURCE_OWNED_FIELDS:
        value = incoming.get(field_name)
        if value is not None and value != "":
            authoritative[field_name] = value
    authoritative["content_hash"] = _content_hash_for(existing, authoritative)
    return {
        field_name: value
        for field_name, value in authoritative.items()
        if _different(existing, field_name, value)
    }


def _plan_load(connection: sqlite3.Connection, batch: NormalizedBatch) -> _Plan:
    _check_database_schema(connection)
    actions: list[_Action] = []
    conflicts: list[str] = []
    present_ids: set[str] = set()

    for record in batch.records:
        model = _model_from_record(record["measure"])
        present_ids.add(str(model.measure_id))
        exact_row = connection.execute(
            "SELECT * FROM measures WHERE fingerprint = ?", (model.fingerprint,)
        ).fetchone()
        if exact_row:
            existing = dict(exact_row)
            if (
                existing.get("measure_id") != model.measure_id
                or existing.get("data_source") != DATA_SOURCE
                or _normalize_date(existing.get("election_date")) != batch.election_date
            ):
                conflicts.append(
                    f"fingerprint {model.fingerprint!r} belongs to incompatible row id={existing['id']}"
                )
                continue
            updates = _exact_updates(existing, model)
            if updates:
                actions.append(_Action("update", str(model.measure_id), existing["id"], model, updates, "exact registrar identity"))
            else:
                actions.append(_Action("skip", str(model.measure_id), existing["id"], model, {}, "no mapped changes"))
            continue

        same_ids = connection.execute(
            "SELECT * FROM measures WHERE measure_id = ?", (model.measure_id,)
        ).fetchall()
        if same_ids:
            ids = [row["id"] for row in same_ids]
            conflicts.append(
                f"explicit measure_id {model.measure_id!r} already exists under a different fingerprint: ids={ids}"
            )
            continue

        candidates = _strict_cross_source_candidates(connection, model)
        if len(candidates) > 1:
            conflicts.append(
                f"multiple cross-source candidates for {model.measure_id}: ids={[row['id'] for row in candidates]}"
            )
        elif len(candidates) == 1:
            existing = candidates[0]
            updates = _adoption_updates(existing, model)
            actions.append(
                _Action("update", str(model.measure_id), existing["id"], model, updates, f"adopt official source over {existing.get('data_source')}")
            )
        else:
            actions.append(_Action("insert", str(model.measure_id), None, model, None, "new official measure"))

    # A validated JSONL represents the whole selected snapshot.  Reconcile
    # registrar-owned rows in this exact county/election scope.
    scoped_rows = connection.execute(
        """
        SELECT * FROM measures
        WHERE data_source = ? AND upper(county) = upper(?) AND year = ?
        """,
        (DATA_SOURCE, batch.county, int(batch.election_date[:4])),
    ).fetchall()
    for row in scoped_rows:
        existing = dict(row)
        if _normalize_date(existing.get("election_date")) != batch.election_date:
            continue
        if existing.get("measure_id") not in present_ids and int(existing.get("is_active") or 0) == 1:
            actions.append(
                _Action(
                    "deactivate",
                    str(existing.get("measure_id")),
                    existing["id"],
                    None,
                    {"is_active": 0},
                    "absent from complete selected snapshot",
                )
            )

    return _Plan(tuple(actions), tuple(conflicts))


def _insert(connection: sqlite3.Connection, model: BallotMeasure) -> None:
    data = model.to_dict()
    data.pop("id", None)
    fields = list(data)
    placeholders = ", ".join("?" for _ in fields)
    connection.execute(
        f"INSERT INTO measures ({', '.join(fields)}) VALUES ({placeholders})",
        [data[field_name] for field_name in fields],
    )


def _update(connection: sqlite3.Connection, target_id: int, updates: dict) -> None:
    if not updates:
        return
    timestamp = datetime.now().isoformat(timespec="microseconds")
    assignments = [f"{field_name} = ?" for field_name in updates]
    assignments.extend(
        (
            "updated_at = ?",
            "last_seen_at = ?",
            "update_count = COALESCE(update_count, 0) + 1",
        )
    )
    values = list(updates.values()) + [timestamp, timestamp, target_id]
    cursor = connection.execute(
        f"UPDATE measures SET {', '.join(assignments)} WHERE id = ?",
        values,
    )
    if cursor.rowcount != 1:
        raise RegistrarLoadError(f"expected to update one row id={target_id}, updated {cursor.rowcount}")


def _report(
    jsonl_path: Path,
    db_path: Path,
    commit_requested: bool,
    committed: bool,
    plan: _Plan,
    backup_path: Optional[Path] = None,
) -> LoadReport:
    counts = {kind: sum(action.kind == kind for action in plan.actions) for kind in ("insert", "update", "deactivate", "skip")}
    action_lines = tuple(
        f"{action.kind}: {action.measure_id}"
        + (f" -> row {action.target_id}" if action.target_id is not None else "")
        + (f" ({action.note})" if action.note else "")
        for action in plan.actions
    )
    return LoadReport(
        jsonl_path=Path(jsonl_path),
        db_path=Path(db_path),
        commit_requested=commit_requested,
        committed=committed,
        inserted=counts["insert"],
        updated=counts["update"],
        deactivated=counts["deactivate"],
        skipped=counts["skip"],
        conflicts=plan.conflicts,
        actions=action_lines,
        backup_path=backup_path,
    )


def load_jsonl(
    jsonl_path: Path,
    *,
    db_path: Path = DB_PATH,
    commit: bool = False,
    backup_path: Optional[Path] = None,
) -> LoadReport:
    """Plan or atomically apply one complete normalized snapshot."""
    jsonl_path = Path(jsonl_path)
    db_path = Path(db_path)
    batch = read_normalized_jsonl(jsonl_path)

    with _readonly_connection(db_path) as read_connection:
        plan = _plan_load(read_connection, batch)
    if not commit or plan.conflicts or not any(action.kind != "skip" for action in plan.actions):
        return _report(jsonl_path, db_path, commit, False, plan)

    db = Database(db_path)
    if backup_path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = db_path.with_name(f"{db_path.stem}_registrar_backup_{stamp}{db_path.suffix}")
    backup_path = db.backup(Path(backup_path))
    db.close()

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.execute("BEGIN IMMEDIATE")
        locked_plan = _plan_load(connection, batch)
        if locked_plan.conflicts:
            connection.rollback()
            return _report(jsonl_path, db_path, commit, False, locked_plan, backup_path)
        for action in locked_plan.actions:
            if action.kind == "insert":
                assert action.measure is not None
                _insert(connection, action.measure)
            elif action.kind in {"update", "deactivate"}:
                assert action.target_id is not None and action.updates is not None
                _update(connection, action.target_id, action.updates)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return _report(jsonl_path, db_path, commit, True, locked_plan, backup_path)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load normalized registrar JSONL (dry-run by default)")
    parser.add_argument("jsonl", type=Path, help="normalized registrar JSONL")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="target SQLite database")
    parser.add_argument("--commit", action="store_true", help="back up and atomically mutate the target database")
    parser.add_argument("--backup", type=Path, help="explicit backup path (commit mode only)")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_argument_parser().parse_args(argv)
    report = load_jsonl(
        args.jsonl,
        db_path=args.db,
        commit=args.commit,
        backup_path=args.backup,
    )
    mode = "COMMITTED" if report.committed else "DRY-RUN/NO-WRITE"
    print(
        f"{mode} inserted={report.inserted} updated={report.updated} "
        f"deactivated={report.deactivated} skipped={report.skipped} conflicts={len(report.conflicts)}"
    )
    if report.backup_path:
        print(f"backup={report.backup_path}")
    for conflict in report.conflicts:
        print(f"CONFLICT: {conflict}")
    return 2 if report.conflicts else 0


if __name__ == "__main__":
    raise SystemExit(main())
