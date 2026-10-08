"""Exercise the release cutover's concurrency, preimage and rollback boundary."""
import importlib.util
from pathlib import Path
import shutil
import sqlite3

import pytest

from src.database import statewide_ballot as slate
from tests.test_statewide_ballot import database, REVIEW

spec = importlib.util.spec_from_file_location('promotion', Path(__file__).parents[1] / 'scripts/promote_statewide_release.py')
promotion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promotion)


@pytest.fixture
def cutover(database, tmp_path):
    baseline = database
    candidate = slate.create_working_copy(baseline, tmp_path / 'candidate')
    slate.reconcile(REVIEW, db_path=candidate, scratch_root=tmp_path, apply=True)
    target = tmp_path / 'production.db'
    shutil.copyfile(baseline, target)
    return dict(baseline_db=baseline, candidate_db=candidate, target_db=target,
                baseline_sha256=promotion.sha(baseline), candidate_sha256=promotion.sha(candidate),
                backup=tmp_path / 'backup.db')


def test_exact_candidate_promoted_and_baseline_backed_up(cutover):
    before = cutover['target_db'].read_bytes()
    assert promotion.promote(**cutover)['status'] == 'checked'
    assert cutover['target_db'].read_bytes() == before
    assert not cutover['backup'].exists()
    assert promotion.promote(**cutover, apply=True)['logical_candidate_match']
    assert cutover['backup'].read_bytes() == before
    with sqlite3.connect(cutover['target_db']) as actual, sqlite3.connect(cutover['candidate_db']) as expected:
        assert promotion.logical_state(actual) == promotion.logical_state(expected)


def test_concurrent_reader_blocks_without_changes(cutover):
    before = cutover['target_db'].read_bytes()
    conn = sqlite3.connect(cutover['target_db'])
    try:
        conn.execute('BEGIN')
        conn.execute('SELECT * FROM measures').fetchone()
        with pytest.raises(sqlite3.OperationalError, match='locked'):
            promotion.promote(**cutover, apply=True)
        assert cutover['target_db'].read_bytes() == before
        assert not cutover['backup'].exists()
    finally:
        conn.close()


def test_unrelated_production_edit_is_not_overwritten(cutover):
    with sqlite3.connect(cutover['target_db']) as conn:
        conn.execute("UPDATE measures SET briefing_text='New human work' WHERE id=20000")
    before = cutover['target_db'].read_bytes()
    with pytest.raises(ValueError, match='drifted'):
        promotion.promote(**cutover, apply=True)
    assert cutover['target_db'].read_bytes() == before
    assert not cutover['backup'].exists()


def test_unexpected_candidate_change_rolls_back_every_write(cutover):
    # Even an incorrectly re-pinned candidate cannot sneak in an unrelated edit.
    with sqlite3.connect(cutover['candidate_db']) as conn:
        conn.execute("UPDATE measures SET title='Unreviewed edit' WHERE id=20000")
    cutover['candidate_sha256'] = promotion.sha(cutover['candidate_db'])
    before = cutover['target_db'].read_bytes()
    with pytest.raises(ValueError, match='bounded'):
        promotion.promote(**cutover, apply=True)
    assert cutover['target_db'].read_bytes() == before


def test_failure_after_inserts_rolls_back_schema_rows_and_sequence(cutover, monkeypatch):
    real_state = promotion.logical_state
    calls = []
    def fail_final(conn):
        result = real_state(conn)
        calls.append(None)
        if len(calls) == 4:
            raise RuntimeError('Simulated final verification failure')
        return result
    before = cutover['target_db'].read_bytes()
    monkeypatch.setattr(promotion, 'logical_state', fail_final)
    with pytest.raises(RuntimeError, match='verification failure'):
        promotion.promote(**cutover, apply=True)
    assert cutover['target_db'].read_bytes() == before
    assert cutover['backup'].read_bytes() == before


def test_actual_search_index_difference_is_not_hidden_by_external_content(cutover):
    # This small fixture has no FTS insert trigger. Populate one index entry in
    # each database explicitly, with equal document sizes but a different token.
    for key in ('baseline_db', 'target_db', 'candidate_db'):
        with sqlite3.connect(cutover[key]) as conn:
            title = 'Unexpected sentinel' if key == 'candidate_db' else 'Historical sentinel'
            conn.execute('INSERT INTO measure_search(rowid,title,county) VALUES(20000,?,?)', (title, 'SAN MATEO'))
            assert conn.execute('SELECT title FROM measure_search WHERE rowid=20000').fetchone()[0] == 'Historical sentinel'
    cutover['baseline_sha256'] = promotion.sha(cutover['baseline_db'])
    cutover['candidate_sha256'] = promotion.sha(cutover['candidate_db'])
    before = cutover['target_db'].read_bytes()
    with pytest.raises(ValueError, match='differs from candidate'):
        promotion.promote(**cutover, apply=True)
    assert cutover['target_db'].read_bytes() == before


@pytest.mark.parametrize('suffix', ['-wal', '-shm', '-journal'])
def test_sidecars_preserved_and_refused(cutover, suffix):
    sidecar = Path(str(cutover['target_db']) + suffix)
    sidecar.write_bytes(b'Investigate me')
    with pytest.raises(ValueError, match='sidecars'):
        promotion.promote(**cutover, apply=True)
    assert sidecar.read_bytes() == b'Investigate me'
