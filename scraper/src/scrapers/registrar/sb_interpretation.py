"""Offline interpretation of captured San Bernardino measure documents.

The live scraper deliberately does not import this module.  It captures every
link in the identified measures table with structural metadata; parsers call
``interpret_measures_page`` later, against immutable snapshots, to assign
roles and enforce the county's strict document rules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .sb import CapturedMeasureRow, CapturedMeasuresPage


# Label-keyed cells: role comes from each link's own label, and a label may
# appear at most once per row. Unknown or duplicated labels are interpretation
# failures, never capture failures.
ANALYSIS_ROLES = {
    "impartial": "analysis",
    "tax rate statement": "tax_rate_statement",
}

ARGUMENT_ROLES = {
    "argument for": "argument_for",
    "rebuttal to argument for": "rebuttal_for",
    "argument against": "argument_against",
    "rebuttal to argument against": "rebuttal_against",
}

LABEL_ROLE_COLUMNS = {
    "analysis": ANALYSIS_ROLES,
    "arguments": ARGUMENT_ROLES,
}

# Single-link cells: role comes from the column because their labels are
# variable text (or, for Letter, the measure letter itself).
COLUMN_ROLES = {
    "letter": "notice",
    "jurisdiction": "resolution",
    "measure description": "text",
}


class SbInterpretationError(ValueError):
    """Captured SB structure cannot be assigned roles without guessing."""


@dataclass(frozen=True)
class ExpectedDocument:
    """One captured PDF after strict offline role assignment."""

    filename: str
    url: str
    role: str
    measure_letter: str
    table_row: int


@dataclass(frozen=True)
class MeasureRow:
    table_row: int
    letter: str
    jurisdiction: str
    description: str
    percentage_to_pass: str
    documents: tuple[ExpectedDocument, ...]


@dataclass(frozen=True)
class MeasuresPage:
    headers: tuple[str, ...]
    rows: tuple[MeasureRow, ...]
    expected_documents: tuple[ExpectedDocument, ...]


def _normalized_label(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _interpret_row(row: CapturedMeasureRow) -> MeasureRow:
    by_column: dict[str, list] = {}
    for document in row.documents:
        by_column.setdefault(document.column, []).append(document)

    interpreted: list[ExpectedDocument] = []
    for column, documents in by_column.items():
        if column in COLUMN_ROLES:
            if len(documents) > 1:
                raise SbInterpretationError(
                    f"{column!r} cell has {len(documents)} links (row {row.table_row}); "
                    "zero or one allowed — never silently drop a document"
                )
            roles = [COLUMN_ROLES[column]]
        elif column in LABEL_ROLE_COLUMNS:
            role_map = LABEL_ROLE_COLUMNS[column]
            seen_labels: set[str] = set()
            roles = []
            for document in documents:
                label = _normalized_label(document.label)
                role = role_map.get(label)
                if role is None:
                    raise SbInterpretationError(
                        f"unknown {column} link label {label!r} (row {row.table_row}); "
                        f"known: {sorted(role_map)}"
                    )
                if label in seen_labels:
                    raise SbInterpretationError(
                        f"duplicate {column} link label {label!r} "
                        f"(row {row.table_row})"
                    )
                seen_labels.add(label)
                roles.append(role)
        else:
            labels = [_normalized_label(document.label) for document in documents]
            raise SbInterpretationError(
                f"unrecognized document column {column!r} (row {row.table_row}); "
                f"labels={labels!r}; no role rule"
            )

        interpreted.extend(
            ExpectedDocument(
                filename=document.filename,
                url=document.url,
                role=role,
                measure_letter=document.measure_letter,
                table_row=document.table_row,
            )
            for document, role in zip(documents, roles)
        )

    return MeasureRow(
        table_row=row.table_row,
        letter=row.letter,
        jurisdiction=row.jurisdiction,
        description=row.description,
        percentage_to_pass=row.percentage_to_pass,
        documents=tuple(interpreted),
    )


def interpret_measures_page(page: CapturedMeasuresPage) -> MeasuresPage:
    """Assign document roles and enforce every SB interpretation rule."""
    rows = tuple(_interpret_row(row) for row in page.rows)
    documents = tuple(document for row in rows for document in row.documents)
    return MeasuresPage(page.headers, rows, documents)
