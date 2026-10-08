"""Offline source, identity, isolation, atomicity, and public projection gates."""
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from src.database.operations import Database
from src.database import statewide_ballot as slate
from src.website.generator import WebsiteGenerator


FIXTURE = Path(__file__).parent / "fixtures" / "statewide" / "20260913"
REVIEW = FIXTURE / "review-corrections.json"
NUMBERS = [1, 2, 3, 4, 5, 37, 38, 39, 40, 41, 42, 43, 44, 45]


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "copy.db"
    db = Database(path)
    conn = db.connect()
    # Production contains a legacy column outside today's dataclass schema.
    conn.execute("ALTER TABLE measures ADD COLUMN summary TEXT")
    rows = json.loads((FIXTURE / "before.json").read_text(encoding="utf-8"))
    for row in rows:
        conn.execute(f"INSERT INTO measures ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", list(row.values()))
    conn.execute("INSERT INTO measures (id,year,county,title,data_source,fingerprint,briefing_text) VALUES (20000,2024,'SAN MATEO','Historical sentinel','CEDA','sentinel','Preserve editorial content')")
    for row_id, year, canonical in ((20001, 2022, "PROP_1"), (20002, 2024, "PROP_1"), (20003, 2014, "PROP_2")):
        conn.execute("INSERT INTO measures (id,year,county,measure_id,title,data_source,fingerprint) VALUES (?,?,'Statewide',?,'Historical proposition','CA_SOS',?)", (row_id,year,canonical,str(row_id)))
    conn.commit()
    db.close()
    return slate.create_working_copy(path, tmp_path / "owned")


def run(path, apply=False, review=REVIEW):
    return slate.reconcile(review, db_path=path, scratch_root=path.parent, apply=apply)


def test_captured_list_and_pages_agree_and_exclude_notes_and_2028():
    review = slate.read_review(REVIEW)
    assert [e["proposition_number"] for e in review["entries"]] == NUMBERS
    assert len(review["dispositions"]) == 22
    assert {e["existing_id"] for e in review["entries"] if e["existing_id"]} == {2, 10956, 10960}
    assert all("Supporters" not in e["description"] and "Opponents" not in e["description"] for e in review["entries"])


@pytest.mark.parametrize("change", ["duplicate", "wrong-link", "missing-date", "unnumbered"])
def test_parser_rejects_source_drift(change):
    html = (FIXTURE / "sources" / "qualified.html").read_text(encoding="utf-8")
    if change == "duplicate":
        html = html.replace('<h2>November 7, 2028', '<p>Proposition 1<a href="https://voterguide.sos.ca.gov/propositions/1/index.htm">Authorizes Bonds. Legislative Statute.</a></p><h2>November 7, 2028')
    elif change == "wrong-link":
        html = html.replace('/propositions/1/index.htm', '/propositions/2/index.htm')
    elif change == "missing-date":
        html = html.replace('November 3, 2026, Statewide Ballot Measures', 'Future Statewide Ballot Measures')
    else:
        html = html.replace('Proposition 1</font>', 'Measure One</font>')
    with pytest.raises(ValueError):
        slate.parse_qualified(html)


def test_check_has_no_writes_and_missing_or_production_db_is_rejected(database, monkeypatch):
    before = database.read_bytes()
    result = run(database)
    assert (result["matched"], result["inserted"], result["withdrawn"], result["writes"]) == (3, 11, 1, 0)
    assert database.read_bytes() == before
    with pytest.raises(ValueError, match="existing file"):
        run(database.parent / 'missing.db')
    monkeypatch.setattr(slate, 'PRODUCTION_DB', database)
    with pytest.raises(ValueError, match="Production"):
        run(database, True)
    assert database.read_bytes() == before


def test_wrong_scratch_root_and_hardlink_to_production_rejected(database, monkeypatch):
    with pytest.raises(ValueError, match="scratch root"):
        slate.reconcile(REVIEW, db_path=database, scratch_root=database.parent / 'elsewhere', apply=True)
    alias = database.parent / 'alias.db'
    alias.hardlink_to(database)
    monkeypatch.setattr(slate, 'PRODUCTION_DB', database)
    with pytest.raises(ValueError, match="Production"):
        run(alias, True)


def test_scoped_changes_preserve_keys_editorial_history_and_replay_bytes(database):
    with connect(database) as conn:
        before = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM measures")}
    result = run(database, True)
    assert result['inserted'] == 11
    with connect(database) as conn:
        after = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM measures")}
        entries = [dict(r) for r in conn.execute("SELECT * FROM statewide_ballot_entries WHERE ballot_status='qualified' ORDER BY proposition_number")]
        assert [e['proposition_number'] for e in entries] == NUMBERS
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert len(json.loads(conn.execute("SELECT before_json FROM statewide_ballot_reviews").fetchone()[0])) == 22
    assert len(after) == len(before) + 11
    for row_id, row in before.items():
        changed = {k for k in row if row[k] != after[row_id][k]}
        allowed = {'updated_at', 'update_count'}
        if row_id == 1:
            assert changed == allowed
            assert after[row_id]['is_active'] == 1
            assert after[row_id]['election_date'] is None
        elif row_id in (2, 10956, 10960):
            assert changed <= allowed | {'election_date', 'election_type', 'election_type_imputed'}
            assert after[row_id]['election_date'] == '2026-11-03'
        else:
            assert changed == set()
    unchanged_bytes = database.read_bytes()
    assert run(database, True)['status'] == 'unchanged'
    assert database.read_bytes() == unchanged_bytes


@pytest.mark.parametrize('applied', [False, True])
def test_preimage_or_replay_drift_rejected_without_more_writes(database, applied):
    if applied:
        run(database, True)
    with connect(database) as conn:
        conn.execute("UPDATE measures SET title='Concurrent edit' WHERE id=2")
    before = database.read_bytes()
    with pytest.raises(ValueError, match="preimages changed|has drifted"):
        run(database, True)
    assert database.read_bytes() == before


def test_mid_transaction_failure_rolls_back_rows_and_new_schema(database):
    with connect(database) as conn:
        conn.execute("CREATE TRIGGER reject_correction BEFORE UPDATE ON measures WHEN OLD.id=10956 BEGIN SELECT RAISE(ABORT,'sentinel rollback'); END")
        before = [tuple(r) for r in conn.execute('SELECT * FROM measures ORDER BY id')]
    with pytest.raises(sqlite3.IntegrityError, match='sentinel rollback'):
        run(database, True)
    with connect(database) as conn:
        assert [tuple(r) for r in conn.execute('SELECT * FROM measures ORDER BY id')] == before
        assert not slate.table_exists(conn, 'statewide_ballot_entries')
        assert not slate.table_exists(conn, 'statewide_ballot_reviews')


def test_evidence_mutation_rejected_before_db_write(database, tmp_path):
    dest = tmp_path / 'review'
    shutil.copytree(FIXTURE, dest)
    with (dest / 'sources' / 'prop-3.html').open('a', encoding='utf-8') as file:
        file.write('changed')
    before = database.read_bytes()
    with pytest.raises(ValueError, match='Evidence hash mismatch'):
        run(database, True, dest / 'review-corrections.json')
    assert database.read_bytes() == before


@pytest.mark.parametrize('prepared', [False, True])
def test_public_assignment_reaches_both_build_paths(database, tmp_path, monkeypatch, prepared):
    run(database, True)
    db = Database(database)
    generator = WebsiteGenerator(db, tmp_path / 'site' / 'index.html')
    monkeypatch.setattr(generator, '_load_finance_data', lambda: {})
    monkeypatch.setattr(generator, '_load_insights_data', lambda: {})
    monkeypatch.setattr(generator, '_load_recommendations', lambda: {})
    if prepared:
        measures = [m.to_dict() for m in db.get_all_active_measures()]
        generator.generate_prepared(measures, {}, [], {})
    else:
        generator.generate()
    exported = json.loads((tmp_path / 'site' / 'measures-data.json').read_text(encoding='utf-8'))
    numbered = sorted((m for m in exported if m.get('proposition_number')), key=lambda m:m['proposition_number'])
    assert [m['proposition_number'] for m in numbered] == NUMBERS
    assert next(m for m in exported if m['id'] == 1)['ballot_status'] == 'withdrawn'
    assert all(m['official_description'] for m in numbered)
    prop3 = next(m for m in numbered if m['proposition_number'] == 3)
    assert prop3['id'] == 10960 and prop3['measure_id'] == 'INIT_1993'
    assert prop3['source_url'] == 'https://voterguide.sos.ca.gov/propositions/3/index.htm'
    assert prop3['official_title'].startswith('Provides Permanent Funding')
    db.close()


def test_public_projection_rejects_wrong_id_and_preserves_withdrawal(database):
    run(database, True)
    with connect(database) as conn:
        measures = slate.cohort(conn)
        result = slate.attach_statewide_ballot_fields(conn, measures)
        withdrawn = next(m for m in result if m['id'] == 1)
        assert withdrawn['ballot_status'] == 'withdrawn'
        assert withdrawn['withdrawn_on'] == '2026-06-25'
        assert withdrawn['election_date'] is None
        row = next(m for m in measures if m['id'] == 10960)
        with pytest.raises(ValueError, match='matching integer and canonical'):
            slate.attach_statewide_ballot_fields(conn, [{**row, 'id': None}])
        with pytest.raises(ValueError, match='matching integer and canonical'):
            slate.attach_statewide_ballot_fields(conn, [{**row, 'measure_id': 'OTHER'}])


def test_voter_guide_and_legislative_session_links_follow_verified_assignment(database):
    run(database, True)
    with connect(database) as conn:
        row = dict(conn.execute('SELECT * FROM measures WHERE id=2').fetchone())
        row['external_links'] = [
            {'source': 'Official Voter Guide', 'url': 'https://voterguide.sos.ca.gov/', 'confidence': 'medium'},
            {'source': 'CA Legislature (Senate Constitutional Amendment)', 'url': 'https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202520260SCA1'},
        ]
        result = slate.attach_statewide_ballot_fields(conn, [row])[0]
        assert result['external_links'][0]['url'].endswith('/propositions/5/index.htm')
        assert result['external_links'][1]['url'].endswith('202320240SCA1')
        assert row['external_links'][1]['url'].endswith('202520260SCA1')


def test_baseline_cannot_be_used_even_with_broad_scratch_root(database):
    baseline = database.parent.parent / 'copy.db'
    before = baseline.read_bytes()
    with pytest.raises(ValueError, match='owned working copy'):
        slate.reconcile(REVIEW, db_path=baseline, scratch_root=baseline.parent, apply=True)
    with pytest.raises(FileExistsError):
        slate.create_working_copy(baseline, baseline.parent)
    assert baseline.read_bytes() == before


def test_replaced_working_file_rejected(database):
    database.rename(database.with_suffix('.saved'))
    shutil.copy2(database.with_suffix('.saved'), database)
    with pytest.raises(ValueError, match='ownership mismatch'):
        run(database, True)


def test_working_file_hardlinked_as_backup_rejected(database):
    database.with_suffix('.backup').hardlink_to(database)
    with pytest.raises(ValueError, match='ownership mismatch'):
        run(database, True)


@pytest.mark.parametrize('mutation', ['swap', 'metadata'])
def test_review_cannot_approve_its_own_identity_changes(database, tmp_path, mutation):
    dest = tmp_path / 'review-mutated'
    shutil.copytree(FIXTURE, dest)
    path = dest / 'review-corrections.json'
    review = json.loads(path.read_text(encoding='utf-8'))
    if mutation == 'swap':
        a, b = review['entries'][2:4]
        for key in ('existing_id', 'canonical_id', 'identity_evidence'):
            a[key], b[key] = b[key], a[key]
    else:
        review['reviewed_at'] = '2030-01-01T00:00:00Z'
    path.write_text(json.dumps(review), encoding='utf-8')
    before = database.read_bytes()
    with pytest.raises(ValueError, match='approved'):
        run(database, True, path)
    assert database.read_bytes() == before


def test_new_keys_do_not_reuse_historical_keys_and_links_parse_number(database):
    from src.utils.external_links import extract_prop_number
    run(database, True)
    with connect(database) as conn:
        historical = [dict(r) for r in conn.execute('SELECT * FROM measures WHERE year < 2026')]
        entries = [dict(r) for r in conn.execute('SELECT * FROM statewide_ballot_entries WHERE ballot_status="qualified"')]
        for entry in entries:
            if entry['canonical_id'].startswith('PROP_'):
                assert entry['canonical_id'].endswith('_2026')
                assert entry['canonical_id'] not in {r['measure_id'] for r in historical}
                assert extract_prop_number({'measure_id': entry['canonical_id']}) == str(entry['proposition_number'])


def test_static_pages_prefer_official_content_and_preserve_withdrawn_route(database):
    import importlib.util
    module_path = Path(__file__).resolve().parents[2] / 'build_measure_pages.py'
    spec = importlib.util.spec_from_file_location('measure_pages', module_path)
    pages = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pages)
    from bs4 import BeautifulSoup
    run(database, True)
    with connect(database) as conn:
        rows = slate.attach_statewide_ballot_fields(conn, slate.cohort(conn))
    for row in rows:
        if not row.get('ballot_status'):
            continue
        row['summary_text'] = 'Incorrect legacy explanation sentinel'
        soup = BeautifulSoup(pages.build_page(row), 'html.parser')
        text = soup.get_text(' ', strip=True)
        assert 'Incorrect legacy explanation sentinel' not in text
        assert row.get('official_description') or row.get('status_reason')
        assert (row.get('official_description') or row['status_reason']) in text
        assert soup.select_one('.cta')['href'] == f"/#m={row['id']}"
        if row['ballot_status'] == 'withdrawn':
            assert 'Withdrawn' in text and 'Upcoming' not in text
            assert soup.select_one('link[rel="canonical"]')['href'].endswith('/measures/1.html')
