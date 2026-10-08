"""Known county mislabelling is corrected by reviewed bytes, not a role heuristic."""
import hashlib
from pathlib import Path
import sqlite3

import pytest

from src.database.measure_documents import (SCHEMA, documents_for_website,
    SB_Z_ARGUMENT_SHA256, SB_Z_ARGUMENT_URL, SB_Z_ROLE_NOTE)


def source_database(sha=SB_Z_ARGUMENT_SHA256, url=SB_Z_ARGUMENT_URL):
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE measures(id INTEGER PRIMARY KEY,is_active INTEGER,is_duplicate INTEGER)')
    conn.execute('INSERT INTO measures VALUES(12419,1,0)')
    conn.execute(SCHEMA)
    for role in ('analysis', 'argument_for'):
        conn.execute('INSERT INTO measure_documents VALUES(?,?,?,?,?,?,?,?,?,?)',
                     (12419,role,url,'a.pdf',sha,100,'application/pdf','snapshot','2026-09-07','https://example.gov'))
    return conn


def test_reviewed_argument_cannot_be_presented_as_impartial_analysis():
    conn = source_database()
    before = conn.execute('SELECT * FROM measure_documents').fetchall()
    doc, = documents_for_website(conn)[12419]
    assert doc['roles'] == ['argument_for']
    assert doc['labels'] == ['Argument in favor']
    assert doc['source_roles'] == ['analysis', 'argument_for']
    assert doc['role_review_note'] == SB_Z_ROLE_NOTE
    assert conn.execute('SELECT * FROM measure_documents').fetchall() == before
    conn.close()


def test_updated_pdf_at_reviewed_url_requires_reinspection():
    conn = source_database(sha='f'*64)
    with pytest.raises(ValueError, match='inspect its content'):
        documents_for_website(conn)
    conn.close()


def test_legitimate_combined_packet_keeps_both_roles():
    conn = source_database(url='https://example.gov/combined-packet.pdf')
    doc, = documents_for_website(conn)[12419]
    assert doc['roles'] == ['analysis', 'argument_for']
    assert 'role_review_note' not in doc
    conn.close()


def test_pinned_official_source_pdf_is_retained_for_independent_review():
    path = Path(__file__).parent / 'fixtures/document_roles/sb-z-argument-for.pdf'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == SB_Z_ARGUMENT_SHA256
