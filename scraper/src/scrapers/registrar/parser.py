"""Parse immutable registrar snapshots into normalized JSONL records.

Only stored bytes are consumed. HTML capture and role assignment are delegated
to the configured county extractor/interpreter; this module adds snapshot
validation, cross-snapshot lineage, field normalization, and deterministic
output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Iterable, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .county_config import COUNTY_CONFIGS, derive_election_type, get_county_config
from .contracts import (
    CapturedMeasuresPage,
    ExpectedDocument,
    MeasureRow,
    MeasuresPage,
    RegistrarInterpretationError,
)
from .storage import ArtifactRef, RawArtifactStore, make_store


SCHEMA_VERSION = 1
COUNTY_NAMES = {slug: config.county_name for slug, config in COUNTY_CONFIGS.items()}
NORMALIZED_DIR = Path(__file__).resolve().parents[3] / "data" / "registrar_normalized"

_ROLE_PRIORITY = {
    role: rank
    for rank, role in enumerate(
        (
            "resolution",
            "text",
            "analysis",
            "tax_rate_statement",
            "argument_for",
            "argument_against",
            "rebuttal_for",
            "rebuttal_against",
        )
    )
}
_THRESHOLDS = {
    "50% + 1": "50%",
    "50%+1": "50%",
    "50%": "50%",
    "55%": "55%",
    "2/3": "66.67%",
    "66.67%": "66.67%",
}


class RegistrarParseError(RuntimeError):
    """Base class for normalized registrar parse failures."""


class SnapshotNotFoundError(RegistrarParseError):
    """Raised when no requested complete snapshot exists."""


class SnapshotValidationError(RegistrarParseError):
    """Raised when a manifest and its verified artifacts disagree."""


class LineageConflictError(RegistrarParseError):
    """Raised when cross-snapshot identity cannot be resolved safely."""


@dataclass(frozen=True)
class ParsedSnapshot:
    snapshot_id: str
    manifest: dict
    page: MeasuresPage
    page_ref: ArtifactRef
    artifact_refs: dict[str, ArtifactRef]


@dataclass
class _Lineage:
    origin_snapshot_id: str
    origin_table_row: int
    origin_key_kind: str
    origin_key_value: str
    latest: MeasureRow
    document_urls: set[str] = field(default_factory=set)
    last_seen_snapshot_id: str = ""

    def observe(self, row: MeasureRow, snapshot_id: str) -> None:
        self.latest = row
        self.document_urls.update(_document_urls(row))
        self.last_seen_snapshot_id = snapshot_id


@dataclass(frozen=True)
class ParseReport:
    county: str
    election_date: str
    snapshot_id: str
    snapshots_replayed: int
    records: tuple[dict, ...]
    output_path: Optional[Path]

    @property
    def record_count(self) -> int:
        return len(self.records)


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def canonicalize_document_url(url: str) -> str:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        hostname = f"{hostname}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path)
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((scheme, hostname, path, query, ""))


def _document_urls(row: MeasureRow) -> set[str]:
    return {canonicalize_document_url(document.url) for document in row.documents}


def _normalized_threshold(raw: str) -> str:
    value = " ".join(raw.split())
    try:
        return _THRESHOLDS[value]
    except KeyError as exc:
        raise SnapshotValidationError(f"unsupported vote threshold {raw!r}") from exc


def _semantic_key(row: MeasureRow) -> tuple[str, str, str]:
    return (_norm(row.jurisdiction), _norm(row.description), _normalized_threshold(row.percentage_to_pass))


def _jurisdiction_description_key(row: MeasureRow) -> tuple[str, str]:
    return (_norm(row.jurisdiction), _norm(row.description))


def _jurisdiction_threshold_key(row: MeasureRow) -> tuple[str, str]:
    return (_norm(row.jurisdiction), _normalized_threshold(row.percentage_to_pass))


def _origin_key(
    row: MeasureRow,
    role_priority: tuple[str, ...] = (),
) -> tuple[str, str]:
    if row.documents:
        priority = (
            {role: rank for rank, role in enumerate(role_priority)}
            if role_priority
            else _ROLE_PRIORITY
        )
        document = min(
            row.documents,
            key=lambda item: (
                priority.get(item.role, 999),
                canonicalize_document_url(item.url),
            ),
        )
        return "document_url", canonicalize_document_url(document.url)
    return "semantic", json.dumps(_semantic_key(row), separators=(",", ":"), ensure_ascii=False)


def _identity_digest(county: str, election_date: str, lineage: _Lineage) -> str:
    payload = json.dumps(
        [county, election_date, lineage.origin_key_kind, lineage.origin_key_value],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def _measure_id(county: str, election_date: str, lineage: _Lineage) -> str:
    date_token = election_date.replace("-", "")
    return f"REG_{county.upper()}_{date_token}_{_identity_digest(county, election_date, lineage)}"


def _validate_scope(
    manifest: dict,
    county: str,
    election_date: str,
    snapshot_id: str,
) -> int:
    expected = {
        "county": county,
        "election_date": election_date,
        "snapshot_id": snapshot_id,
    }
    for field_name, expected_value in expected.items():
        if manifest.get(field_name) != expected_value:
            raise SnapshotValidationError(
                f"manifest {field_name} mismatch for {snapshot_id}: "
                f"expected {expected_value!r}, got {manifest.get(field_name)!r}"
            )
    schema_version = manifest.get("schema_version")
    if schema_version not in (1, 2):
        raise SnapshotValidationError(
            f"unsupported manifest schema_version {schema_version!r} in {snapshot_id}"
        )
    if not manifest.get("election_url"):
        raise SnapshotValidationError(f"manifest {snapshot_id} has no election_url")
    return schema_version


def _recorded_entries(snapshot_id: str, manifest: dict) -> list[dict]:
    entries = manifest.get("pdf_artifacts")
    if not isinstance(entries, list):
        raise SnapshotValidationError(
            f"manifest {snapshot_id} has no pdf_artifacts list"
        )
    return entries


def _audit_v2_capture(
    snapshot_id: str,
    manifest: dict,
    page: CapturedMeasuresPage,
) -> None:
    extracted = {
        (
            document.filename,
            document.table_row,
            document.measure_letter,
            document.column,
            document.label,
            document.url,
        )
        for document in page.expected_documents
    }
    entries = _recorded_entries(snapshot_id, manifest)
    try:
        recorded = {
            (
                entry["filename"],
                entry["table_row"],
                entry["measure_letter"],
                entry["column"],
                entry["label"],
                entry["source_url"],
            )
            for entry in entries
        }
    except (KeyError, TypeError) as exc:
        raise SnapshotValidationError(
            f"malformed v2 pdf_artifacts in {snapshot_id}"
        ) from exc
    if len(entries) != len(recorded):
        raise SnapshotValidationError(
            f"duplicate pdf_artifacts audit entries in {snapshot_id}"
        )
    if extracted != recorded:
        missing = sorted(extracted - recorded)
        extra = sorted(recorded - extracted)
        raise SnapshotValidationError(
            f"extractor/v2-manifest document mismatch in {snapshot_id}: "
            f"missing={missing}, extra={extra}"
        )


def _v1_role_key(document: ExpectedDocument) -> tuple:
    return (
        document.table_row,
        document.measure_letter,
        document.role,
        document.url,
    )


def _audit_and_rebind_v1(
    snapshot_id: str,
    manifest: dict,
    page: MeasuresPage,
) -> MeasuresPage:
    """Audit role-bearing v1 entries and restore their immutable filenames."""
    entries = _recorded_entries(snapshot_id, manifest)
    try:
        recorded_by_key = {
            (
                entry["table_row"],
                entry["measure_letter"],
                entry["role"],
                entry["source_url"],
            ): entry["filename"]
            for entry in entries
        }
    except (KeyError, TypeError) as exc:
        raise SnapshotValidationError(
            f"malformed v1 pdf_artifacts in {snapshot_id}"
        ) from exc
    if len(entries) != len(recorded_by_key):
        raise SnapshotValidationError(
            f"duplicate pdf_artifacts audit entries in {snapshot_id}"
        )

    extracted = {_v1_role_key(document) for document in page.expected_documents}
    recorded = set(recorded_by_key)
    if extracted != recorded:
        missing = sorted(extracted - recorded)
        extra = sorted(recorded - extracted)
        raise SnapshotValidationError(
            f"interpreter/v1-manifest document mismatch in {snapshot_id}: "
            f"missing={missing}, extra={extra}"
        )

    rows = tuple(
        replace(
            row,
            documents=tuple(
                replace(
                    document,
                    filename=recorded_by_key[_v1_role_key(document)],
                )
                for document in row.documents
            ),
        )
        for row in page.rows
    )
    return MeasuresPage(
        headers=page.headers,
        rows=rows,
        expected_documents=tuple(
            document for row in rows for document in row.documents
        ),
    )


def _audit_artifact_files(
    snapshot_id: str,
    manifest: dict,
    filenames: set[str],
    captured_document_count: int,
    refs: dict[str, ArtifactRef],
) -> None:
    missing_refs = sorted(filenames - refs.keys())
    if missing_refs:
        raise SnapshotValidationError(f"manifest {snapshot_id} lacks document artifacts {missing_refs}")
    unexpected_refs = sorted(set(refs) - filenames - {"page.html"})
    if unexpected_refs:
        raise SnapshotValidationError(f"manifest {snapshot_id} has unaudited artifacts {unexpected_refs}")

    counts = manifest.get("pdf_counts") or {}
    if (
        counts.get("expected") != captured_document_count
        or counts.get("saved") != captured_document_count
    ):
        raise SnapshotValidationError(
            f"PDF count mismatch in {snapshot_id}: "
            f"extractor={captured_document_count}, "
            f"manifest={counts!r}"
        )


def _load_snapshot(
    store: RawArtifactStore,
    county: str,
    election_date: str,
    snapshot_id: str,
    extractor: Callable[[bytes, str], CapturedMeasuresPage],
    interpreter: Callable[[CapturedMeasuresPage], MeasuresPage],
) -> ParsedSnapshot:
    manifest = store.get_manifest(county=county, election_date=election_date, snapshot_id=snapshot_id)
    schema_version = _validate_scope(manifest, county, election_date, snapshot_id)

    refs_list = store.list_artifacts(county=county, election_date=election_date, snapshot_id=snapshot_id)
    refs = {ref.filename: ref for ref in refs_list}
    if len(refs) != len(refs_list):
        raise SnapshotValidationError(f"duplicate artifact filenames in {snapshot_id}")
    try:
        page_ref = refs["page.html"]
    except KeyError as exc:
        raise SnapshotValidationError(f"snapshot {snapshot_id} has no page.html artifact") from exc

    verified: dict[str, bytes] = {}
    for ref in refs_list:
        verified[ref.filename] = store.get_artifact(ref)
    captured_page = extractor(verified["page.html"], manifest["election_url"])

    if manifest.get("table_row_count") != len(captured_page.rows):
        raise SnapshotValidationError(
            f"row count mismatch in {snapshot_id}: extractor={len(captured_page.rows)}, "
            f"manifest={manifest.get('table_row_count')!r}"
        )
    if tuple(manifest.get("table_headers") or ()) != captured_page.headers:
        raise SnapshotValidationError(
            f"table header mismatch in {snapshot_id}: extractor={captured_page.headers!r}, "
            f"manifest={manifest.get('table_headers')!r}"
        )
    if schema_version == 2:
        _audit_v2_capture(snapshot_id, manifest, captured_page)
    try:
        # Ordering invariant: all snapshots become role-bearing pages here,
        # before _link_snapshot() can compute an identity origin.
        page = interpreter(captured_page)
    except RegistrarInterpretationError as exc:
        raise SnapshotValidationError(
            f"document interpretation failed in {snapshot_id}: {exc}"
        ) from exc
    if schema_version == 1:
        page = _audit_and_rebind_v1(snapshot_id, manifest, page)

    filenames = {document.filename for document in page.expected_documents}
    _audit_artifact_files(
        snapshot_id,
        manifest,
        filenames,
        # A v2 captured artifact can expand to several semantic roles during
        # interpretation (San Mateo composite packets). Manifest counts audit
        # stored links/bytes, not the role-bearing normalized record count.
        len(captured_page.expected_documents),
        refs,
    )
    return ParsedSnapshot(snapshot_id, manifest, page, page_ref, refs)


def _unique_matches(
    rows: list[MeasureRow],
    lineages: list[_Lineage],
    unmatched_rows: set[int],
    unmatched_lineages: set[int],
    row_key: Callable[[MeasureRow], object],
    lineage_key: Callable[[_Lineage], object],
) -> list[tuple[int, int]]:
    row_groups: dict[object, list[int]] = {}
    lineage_groups: dict[object, list[int]] = {}
    for row_index in unmatched_rows:
        row_groups.setdefault(row_key(rows[row_index]), []).append(row_index)
    for lineage_index in unmatched_lineages:
        lineage_groups.setdefault(lineage_key(lineages[lineage_index]), []).append(lineage_index)
    return [
        (row_indexes[0], lineage_groups[key][0])
        for key, row_indexes in row_groups.items()
        if len(row_indexes) == 1 and len(lineage_groups.get(key, ())) == 1
    ]


def _link_snapshot(
    lineages: list[_Lineage],
    snapshot: ParsedSnapshot,
    lineage_overrides: Optional[dict[tuple[str, int], tuple[str, int]]] = None,
    origin_role_priority: tuple[str, ...] = (),
) -> dict[int, _Lineage]:
    rows = list(snapshot.page.rows)
    if not lineages:
        result = {}
        for index, row in enumerate(rows):
            kind, value = _origin_key(row, origin_role_priority)
            lineage = _Lineage(
                snapshot.snapshot_id,
                row.table_row,
                kind,
                value,
                row,
                _document_urls(row),
                snapshot.snapshot_id,
            )
            lineages.append(lineage)
            result[index] = lineage
        return result

    previous_snapshot_id = max(lineage.last_seen_snapshot_id for lineage in lineages)
    previous_active = {
        index
        for index, lineage in enumerate(lineages)
        if lineage.last_seen_snapshot_id == previous_snapshot_id
    }
    unmatched_rows = set(range(len(rows)))
    unmatched_lineages = set(range(len(lineages)))
    linked: dict[int, _Lineage] = {}

    def apply(pairs: Iterable[tuple[int, int]]) -> None:
        for row_index, lineage_index in pairs:
            if row_index not in unmatched_rows or lineage_index not in unmatched_lineages:
                continue
            lineage = lineages[lineage_index]
            lineage.observe(rows[row_index], snapshot.snapshot_id)
            linked[row_index] = lineage
            unmatched_rows.remove(row_index)
            unmatched_lineages.remove(lineage_index)

    override_pairs = []
    for row_index in sorted(unmatched_rows):
        target = (lineage_overrides or {}).get(
            (snapshot.snapshot_id, rows[row_index].table_row)
        )
        if target is None:
            continue
        candidates = [
            index
            for index in unmatched_lineages
            if (lineages[index].origin_snapshot_id, lineages[index].origin_table_row) == target
        ]
        if len(candidates) != 1:
            raise LineageConflictError(
                f"lineage override for row {rows[row_index].table_row} in "
                f"{snapshot.snapshot_id} resolves to {len(candidates)} origins"
            )
        override_pairs.append((row_index, candidates[0]))
    if len({lineage_index for _, lineage_index in override_pairs}) != len(override_pairs):
        raise LineageConflictError(f"multiple rows in {snapshot.snapshot_id} claim one override lineage")
    apply(override_pairs)

    # A uniquely-owned document URL is the strongest continuity evidence.
    # Shared packets are legitimate in San Mateo, so shared URLs are ignored;
    # a measure-specific analysis/argument URL can still identify one lineage.
    url_owners: dict[str, set[int]] = {}
    for lineage_index, lineage in enumerate(lineages):
        for url in lineage.document_urls:
            url_owners.setdefault(url, set()).add(lineage_index)
    url_pairs = []
    for row_index in sorted(unmatched_rows):
        urls = _document_urls(rows[row_index])
        candidates = sorted(
            {
                next(iter(url_owners[url]))
                for url in urls
                if len(url_owners.get(url, ())) == 1
                and next(iter(url_owners[url])) in unmatched_lineages
            }
        )
        if len(candidates) > 1:
            raise LineageConflictError(
                f"row {rows[row_index].table_row} in {snapshot.snapshot_id} "
                "has measure-specific document URLs owned by multiple lineages"
            )
        if candidates:
            url_pairs.append((row_index, candidates[0]))
    if len({lineage_index for _, lineage_index in url_pairs}) != len(url_pairs):
        raise LineageConflictError(f"multiple rows in {snapshot.snapshot_id} claim one URL lineage")
    apply(url_pairs)

    # A displayed letter is mutable and may be swapped or reused.  It can only
    # corroborate exact semantics; a unique letter that points at incompatible
    # content is a conflict, never an identity decision.
    letter_pairs = _unique_matches(
        rows,
        lineages,
        unmatched_rows,
        unmatched_lineages.intersection(previous_active),
        lambda row: row.letter.upper() if row.letter.upper() != "TBD" else None,
        lambda lineage: lineage.latest.letter.upper()
        if lineage.latest.letter.upper() != "TBD"
        else None,
    )
    for row_index, lineage_index in letter_pairs:
        if _semantic_key(rows[row_index]) != _semantic_key(lineages[lineage_index].latest):
            raise LineageConflictError(
                f"letter {rows[row_index].letter!r} contradicts semantic identity for "
                f"row {rows[row_index].table_row} in {snapshot.snapshot_id}"
            )
    apply(letter_pairs)
    apply(
        _unique_matches(
            rows,
            lineages,
            unmatched_rows,
            unmatched_lineages.intersection(previous_active),
            _semantic_key,
            lambda lineage: _semantic_key(lineage.latest),
        )
    )
    apply(
        _unique_matches(
            rows,
            lineages,
            unmatched_rows,
            unmatched_lineages.intersection(previous_active),
            _jurisdiction_description_key,
            lambda lineage: _jurisdiction_description_key(lineage.latest),
        )
    )
    unmatched_old_jurisdictions = {
        _norm(lineages[index].latest.jurisdiction)
        for index in unmatched_lineages.intersection(previous_active)
    }
    for row_index in sorted(unmatched_rows):
        row = rows[row_index]
        if _norm(row.jurisdiction) in unmatched_old_jurisdictions:
            raise LineageConflictError(
                f"ambiguous lineage for {row.jurisdiction!r} row {row.table_row} "
                f"in {snapshot.snapshot_id}"
            )
        kind, value = _origin_key(row, origin_role_priority)
        lineage = _Lineage(
            snapshot.snapshot_id,
            row.table_row,
            kind,
            value,
            row,
            _document_urls(row),
            snapshot.snapshot_id,
        )
        lineages.append(lineage)
        linked[row_index] = lineage

    return linked


def _document_record(document: ExpectedDocument, snapshot: ParsedSnapshot) -> dict:
    ref = snapshot.artifact_refs[document.filename]
    return {
        "role": document.role,
        "source_url": document.url,
        "snapshot_filename": document.filename,
        "sha256": ref.sha256,
        "size_bytes": ref.size_bytes,
        "content_type": ref.content_type,
    }


def _normalized_record(
    county: str,
    election_date: str,
    snapshot: ParsedSnapshot,
    row: MeasureRow,
    lineage: _Lineage,
) -> dict:
    config = get_county_config(county)
    county_name = config.county_name
    election_type, election_type_imputed = derive_election_type(election_date)
    measure_id = _measure_id(county, election_date, lineage)
    documents = [_document_record(document, snapshot) for document in row.documents]
    text_url = next((item["source_url"] for item in documents if item["role"] == "text"), None)
    origin_key_sha256 = hashlib.sha256(lineage.origin_key_value.encode("utf-8")).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "county_slug": county,
        "election_date": election_date,
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_row_count": len(snapshot.page.rows),
        "table_row": row.table_row,
        "scraped_at": snapshot.manifest.get("scraped_at"),
        "page_sha256": snapshot.page_ref.sha256,
        "lineage": {
            "origin_snapshot_id": lineage.origin_snapshot_id,
            "origin_table_row": lineage.origin_table_row,
            "origin_key_kind": lineage.origin_key_kind,
            "origin_key_value": lineage.origin_key_value,
            "origin_key_sha256": origin_key_sha256,
        },
        "measure": {
            "measure_id": measure_id,
            "measure_letter": row.letter,
            "year": int(election_date[:4]),
            "state": "CA",
            "county": county_name,
            "jurisdiction": row.jurisdiction,
            "title": f"{row.jurisdiction} — {row.description}",
            "description": row.description,
            "ballot_question": None,
            "yes_votes": None,
            "no_votes": None,
            "total_votes": None,
            "percent_yes": None,
            "percent_no": None,
            "passed": None,
            "pass_fail": None,
            "vote_threshold": _normalized_threshold(row.percentage_to_pass),
            "measure_type": "Measure",
            "topic_primary": None,
            "topic_secondary": None,
            "category_type": None,
            "category_topic": None,
            "data_source": config.data_source,
            "source_url": snapshot.manifest["election_url"],
            "pdf_url": text_url,
            "has_summary": False,
            "summary_title": None,
            "summary_text": None,
            "election_type": election_type,
            "election_type_imputed": election_type_imputed,
            "election_date": election_date,
            "is_active": True,
            "is_duplicate": False,
            "duplicate_type": None,
            "master_id": None,
        },
        "documents": documents,
    }


def default_output_path(county: str, election_date: str) -> Path:
    return NORMALIZED_DIR / f"{county}_{election_date}.jsonl"


def write_jsonl(records: Iterable[dict], output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f"{output_path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
    temporary.replace(output_path)


def parse_election(
    store: RawArtifactStore,
    *,
    county: str,
    election_date: str,
    snapshot_id: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> ParseReport:
    """Parse the selected complete snapshot and write deterministic JSONL.

    All earlier complete snapshots are replayed to keep identity stable across
    publication changes such as ``TBD`` becoming a letter.
    """
    county = county.lower()
    if county not in COUNTY_CONFIGS:
        raise RegistrarParseError(f"unsupported registrar county {county!r}")
    try:
        derive_election_type(election_date)
    except ValueError as exc:
        raise RegistrarParseError(str(exc)) from exc
    config = get_county_config(county)

    snapshots = store.list_snapshots(county=county, election_date=election_date)
    if not snapshots:
        raise SnapshotNotFoundError(f"no complete snapshots for {county}/{election_date}")
    selected = snapshot_id or snapshots[-1]
    if selected not in snapshots:
        raise SnapshotNotFoundError(
            f"complete snapshot {selected!r} not found for {county}/{election_date}; "
            f"available={snapshots}"
        )
    replay_ids = snapshots[: snapshots.index(selected) + 1]

    lineages: list[_Lineage] = []
    selected_snapshot: Optional[ParsedSnapshot] = None
    selected_links: dict[int, _Lineage] = {}
    for replay_id in replay_ids:
        parsed = _load_snapshot(
            store,
            county,
            election_date,
            replay_id,
            config.extractor,
            config.interpreter,
        )
        links = _link_snapshot(
            lineages,
            parsed,
            config.lineage_overrides,
            config.origin_role_priority,
        )
        if replay_id == selected:
            selected_snapshot = parsed
            selected_links = links

    assert selected_snapshot is not None
    records = tuple(
        _normalized_record(
            county,
            election_date,
            selected_snapshot,
            row,
            selected_links[row_index],
        )
        for row_index, row in enumerate(selected_snapshot.page.rows)
    )
    measure_ids = [record["measure"]["measure_id"] for record in records]
    if len(measure_ids) != len(set(measure_ids)):
        raise LineageConflictError(f"identity collision in selected snapshot {selected}")

    resolved_output = Path(output_path) if output_path is not None else default_output_path(county, election_date)
    write_jsonl(records, resolved_output)
    return ParseReport(
        county=county,
        election_date=election_date,
        snapshot_id=selected,
        snapshots_replayed=len(replay_ids),
        records=records,
        output_path=resolved_output,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse stored registrar snapshots into normalized JSONL")
    parser.add_argument("--county", required=True, choices=sorted(COUNTY_NAMES))
    parser.add_argument("--election-date", required=True, help="ISO election date, e.g. 2026-11-03")
    parser.add_argument("--snapshot-id", help="complete snapshot ID; defaults to latest")
    parser.add_argument("--env", default="dev", choices=("dev", "prod"), help="artifact-store environment")
    parser.add_argument("--output", type=Path, help="JSONL output path")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_argument_parser().parse_args(argv)
    report = parse_election(
        make_store(env=args.env),
        county=args.county,
        election_date=args.election_date,
        snapshot_id=args.snapshot_id,
        output_path=args.output,
    )
    print(
        f"parsed county={report.county} election={report.election_date} "
        f"snapshot={report.snapshot_id} replayed={report.snapshots_replayed} "
        f"records={report.record_count} output={report.output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
