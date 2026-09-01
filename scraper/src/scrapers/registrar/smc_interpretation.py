"""Strict offline role assignment for captured San Mateo documents."""
from __future__ import annotations

import re

from .contracts import (
    CapturedMeasureRow,
    CapturedMeasuresPage,
    ExpectedDocument,
    MeasureRow,
    MeasuresPage,
    RegistrarInterpretationError,
)


# A tuple is deliberate: composite packets are stored once but expanded into
# one normalized document record per role. This preserves the shared role
# schema and makes tax-statement presence directly queryable.
LABEL_ROLES: dict[str, tuple[str, ...]] = {
    "resolution": ("resolution",),
    "resolution and full text": ("resolution", "text"),
    "resolution, full text and tax rate statement": (
        "resolution",
        "text",
        "tax_rate_statement",
    ),
    "impartial analysis": ("analysis",),
    "primary argument in favor": ("argument_for",),
    "rebuttal to argument in favor": ("rebuttal_for",),
    "primary argument against": ("argument_against",),
    "rebuttal to argument against": ("rebuttal_against",),
}


class SmcInterpretationError(RegistrarInterpretationError):
    """Captured San Mateo labels cannot be assigned without guessing."""


def _normalized_label(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _interpret_row(row: CapturedMeasureRow) -> MeasureRow:
    seen_labels: set[str] = set()
    seen_roles: set[str] = set()
    interpreted: list[ExpectedDocument] = []
    for document in row.documents:
        label = _normalized_label(document.label)
        roles = LABEL_ROLES.get(label)
        if roles is None:
            raise SmcInterpretationError(
                f"unknown document label {label!r} (row {row.table_row}); "
                f"known: {sorted(LABEL_ROLES)}"
            )
        if label in seen_labels:
            raise SmcInterpretationError(
                f"duplicate document label {label!r} (row {row.table_row})"
            )
        duplicate_roles = seen_roles.intersection(roles)
        if duplicate_roles:
            raise SmcInterpretationError(
                f"document label {label!r} repeats role(s) "
                f"{sorted(duplicate_roles)} (row {row.table_row})"
            )
        seen_labels.add(label)
        seen_roles.update(roles)
        interpreted.extend(
            ExpectedDocument(
                filename=document.filename,
                url=document.url,
                role=role,
                measure_letter=document.measure_letter,
                table_row=document.table_row,
            )
            for role in roles
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
    rows = tuple(_interpret_row(row) for row in page.rows)
    documents = tuple(document for row in rows for document in row.documents)
    return MeasuresPage(page.headers, rows, documents)
