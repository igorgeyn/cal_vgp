"""Shared capture and interpretation contracts for registrar adapters.

County modules own DOM structure and label semantics. These immutable records
are the narrow interface between county capture, offline interpretation, and
the shared snapshot parser. Field names are persisted compatibility contracts;
``table_row`` and ``headers`` intentionally remain even for non-table sources.
"""
from __future__ import annotations

from dataclasses import dataclass


class RegistrarInterpretationError(ValueError):
    """Captured document semantics cannot be assigned without guessing."""


@dataclass(frozen=True)
class CapturedDocument:
    """One advertised document link before semantic role assignment."""

    filename: str
    url: str
    column: str
    label: str
    measure_letter: str
    table_row: int


@dataclass(frozen=True)
class CapturedMeasureRow:
    table_row: int
    letter: str
    jurisdiction: str
    description: str
    percentage_to_pass: str
    documents: tuple[CapturedDocument, ...]


@dataclass(frozen=True)
class CapturedMeasuresPage:
    headers: tuple[str, ...]
    rows: tuple[CapturedMeasureRow, ...]
    expected_documents: tuple[CapturedDocument, ...]


@dataclass(frozen=True)
class ExpectedDocument:
    """One captured document after strict offline role assignment."""

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
