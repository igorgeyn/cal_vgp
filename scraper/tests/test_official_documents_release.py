"""Adversarial checks for the production release gate's comparison boundaries."""
from datetime import datetime
import json
import shutil
import sqlite3
from types import SimpleNamespace

import pytest

from scripts.verify_official_documents_release import check_public_delta, check_row, seal, verify
from src.database.measure_documents import documents_for_website
from src.scrapers.registrar.loader import load_jsonl
from tests.test_registrar_loader import _database, _record, _write


@pytest.mark.parametrize('field', ['passed', 'summary_text', 'new_unreviewed_field', 'measure_id', 'historical_context'])
def test_registrar_delta_rejects_unreviewed_fields(field):
    before = {'id': 1, 'data_source': 'SB_County_Registrar', 'passed': None}
    with pytest.raises(ValueError, match='unexpected public delta'):
        check_public_delta(before, {**before, field: 'unexpected'})


def test_removed_null_field_is_not_mistaken_for_equality():
    before = {'id': 1, 'data_source': 'SB_County_Registrar', 'summary_text': None}
    with pytest.raises(ValueError, match='field removed'):
        check_public_delta(before, {k: v for k, v in before.items() if k != 'summary_text'})


@pytest.mark.parametrize('stamp', ['2026-09-07T10:00:00', '2026-09-08T11:00:01', None, 'invalid'])
def test_timestamp_exception_is_bounded(stamp):
    with pytest.raises(ValueError, match='timestamp'):
        check_row({'last_seen_at': 'old'}, {'last_seen_at': stamp}, {'last_seen_at'},
                  datetime(2026, 9, 8, 10), datetime(2026, 9, 8, 11))


def test_only_explicit_timestamp_field_can_differ():
    expected = {'last_seen_at': 'old', 'captured_at': '2026-09-07T17:24:37+00:00'}
    actual = {**expected, 'last_seen_at': '2026-09-08T10:30:00'}
    check_row(expected, actual, {'last_seen_at'}, datetime(2026, 9, 8, 10), datetime(2026, 9, 8, 11))
    with pytest.raises(ValueError, match='captured_at'):
        check_row(expected, {**actual, 'captured_at': '2026-09-08T10:30:00'}, {'last_seen_at'},
                  datetime(2026, 9, 8, 10), datetime(2026, 9, 8, 11))


@pytest.fixture
def release_bundle(tmp_path):
    baseline, reviewed, actual = [tmp_path / name for name in ('baseline', 'reviewed', 'actual')]
    for directory in (baseline, reviewed, actual):
        directory.mkdir()
    old = _record()
    db = _database(baseline / 'measures.db')
    load_jsonl(_write(tmp_path / 'old.jsonl', [old]), db_path=db, commit=True)

    def export(directory):
        with sqlite3.connect(directory / 'measures.db') as conn:
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute('SELECT * FROM active_measures')]
            docs = documents_for_website(conn)
        for row in rows:
            row['official_documents'] = docs[row['id']]
        (directory / 'measures-data.json').write_text(json.dumps(rows))
        (directory / 'index.html').write_text(
            '\n'.join(f'const {name} = {{}};' for name in ('financeData', 'insightsData', 'recommendations', 'topics'))
            + '\nData last updated ' + datetime.now().strftime('%B %d, %Y'))

    export(baseline)
    latest = {**old, 'snapshot_id': '20260821T035115Z', 'scraped_at': '2026-08-21T03:51:15+00:00',
              'measure': {**old['measure'], 'title': 'Revised county description', 'description': 'Revised tax proposal'}}
    jsonl = _write(tmp_path / 'latest.jsonl', [latest])
    start = datetime.now()
    for directory in (reviewed, actual):
        shutil.copyfile(db, directory / 'measures.db')
        load_jsonl(jsonl, db_path=directory / 'measures.db', commit=True)
        export(directory)
    end = datetime.now()
    manifest = tmp_path / 'sealed.json'
    seal(SimpleNamespace(baseline_db=db, baseline_site=baseline/'index.html',
                         reviewed_db=reviewed/'measures.db', reviewed_site=reviewed/'index.html',
                         jsonl=[jsonl], manifest=manifest))
    return manifest, actual, reviewed, start, end


def test_independent_release_files_pass_with_fresh_load_timestamps(release_bundle):
    manifest, actual, reviewed, start, end = release_bundle
    report = verify(manifest, actual/'measures.db', actual/'index.html', start, end)
    assert report['verified'] and report['document_roles'] == 1
    assert report['actual_paths_sha256'].keys() == {
        str((actual/name).resolve()) for name in ('measures.db', 'index.html', 'measures-data.json')}


@pytest.mark.parametrize('corruption', ['outcome', 'capture_date', 'extra_field', 'html', 'old_timestamp'])
def test_actual_output_corruption_is_rejected(release_bundle, corruption):
    manifest, actual, reviewed, start, end = release_bundle
    if corruption in ('outcome', 'capture_date', 'old_timestamp'):
        sql = {
            'outcome': 'UPDATE measures SET passed=1',
            'capture_date': "UPDATE measure_documents SET captured_at='2026-08-22T00:00:00+00:00'",
            'old_timestamp': "UPDATE measures SET updated_at='2000-01-01T00:00:00'",
        }[corruption]
        with sqlite3.connect(actual/'measures.db') as conn:
            conn.execute(sql)
    elif corruption == 'extra_field':
        path = actual/'measures-data.json'
        rows = json.loads(path.read_text())
        rows[0]['unreviewed_field'] = True
        path.write_text(json.dumps(rows))
    else:
        with (actual/'index.html').open('a') as stream:
            stream.write('unexpected change')
    with pytest.raises(ValueError):
        verify(manifest, actual/'measures.db', actual/'index.html', start, end)


def test_pointing_to_rehearsal_instead_of_actual_output_fails(release_bundle):
    manifest, actual, reviewed, start, end = release_bundle
    with pytest.raises(ValueError, match='actual paths must differ'):
        verify(manifest, reviewed/'measures.db', reviewed/'index.html', start, end)


def test_changed_sealed_reference_fails(release_bundle):
    manifest, actual, reviewed, start, end = release_bundle
    (reviewed/'index.html').write_text('tampered reference')
    with pytest.raises(ValueError, match='sealed input changed'):
        verify(manifest, actual/'measures.db', actual/'index.html', start, end)


def test_mirror_must_be_an_independent_file(release_bundle):
    manifest, actual, reviewed, start, end = release_bundle
    with pytest.raises(ValueError, match='paths must be distinct'):
        verify(manifest, actual/'measures.db', actual/'index.html', start, end, actual/'index.html')
