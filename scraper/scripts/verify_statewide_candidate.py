#!/usr/bin/env python3
"""Verify a statewide insertion candidate against immutable local baselines.

This gate accepts the reviewed additions/withdrawal; the sealed F1 registrar
release gate intentionally does not. No database initialization or writes.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.database.statewide_ballot import read_review, digest, LEGISLATION_URLS
from src.database.measure_documents import documents_for_website, SB_Z_ARGUMENT_URL, SB_Z_ARGUMENT_SHA256, SB_Z_ROLE_NOTE


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def connect(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def row_multiset(conn, table):
    # Hash BLOB-containing FTS rows without putting their contents in reports.
    return Counter(hashlib.sha256(repr(tuple(r)).encode()).hexdigest()
                   for r in conn.execute('SELECT * FROM "' + table.replace('"', '""') + '"'))


def verify(*, baseline_db, baseline_site, candidate_db, candidate_site, review_path,
           build_metadata, production_hashes):
    review = read_review(review_path)
    build = json.loads(Path(build_metadata).read_text(encoding='utf-8'))
    require(build['exit_code'] == 0, 'Real CLI build did not exit successfully')
    start, end = (datetime.fromisoformat(build[k]) for k in ('started_at_local', 'finished_at_local'))
    inputs = json.loads(Path(production_hashes).read_text(encoding='utf-8'))
    require(all(sha(p) == h for p, h in inputs.items()), 'Production input changed')
    before_conn, after_conn = connect(baseline_db), connect(candidate_db)
    try:
        require(after_conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'SQLite integrity failure')
        require(not after_conn.execute('PRAGMA foreign_key_check').fetchall(), 'Foreign key failure')
        before = {r['id']: dict(r) for r in before_conn.execute('SELECT * FROM measures')}
        after = {r['id']: dict(r) for r in after_conn.execute('SELECT * FROM measures')}
        assignments = [dict(r) for r in after_conn.execute('SELECT * FROM statewide_ballot_entries ORDER BY proposition_number')]
        qualified = [r for r in assignments if r['ballot_status'] == 'qualified']
        require(len(assignments) == len(review['entries']) + 1, 'Unexpected assignment count')
        require([r['proposition_number'] for r in qualified] == [e['proposition_number'] for e in review['entries']], 'Numbered slate differs')
        new_ids = set(after) - set(before)
        require(set(before) <= set(after), 'Existing rows were deleted')
        require(len(new_ids) == sum(e['existing_id'] is None for e in review['entries']), 'Wrong insertion count')
        for entry, assignment in zip(review['entries'], qualified):
            row = after[assignment['measure_id']]
            require(assignment['review_sha256'] == digest(review), 'Assignment belongs to another review')
            require(assignment['canonical_id'] == row['measure_id'] == entry['canonical_id'], 'Canonical ID differs')
            if entry['existing_id'] is not None:
                require(row['id'] == entry['existing_id'], 'Matched integer ID changed')
            else:
                require(row['id'] in new_ids and row['title'] == entry['official_title'] and row['description'] == entry['description'], 'Inserted content differs')
                require(not row['has_summary'] and row['summary_text'] is None, 'Official description mislabeled as generated summary')
            require(row['year'] == 2026 and row['county'] == 'Statewide' and row['data_source'] == 'CA_SOS', 'Source ownership differs')
            require(row['election_date'] == assignment['election_date'] == review['election_date'], 'Wrong date')
            require(row['is_active'] == 1 and row['is_duplicate'] == 0 and row['passed'] is None, 'Wrong qualified status')
            require(assignment['official_title'] == entry['official_title'] and assignment['source_url'] == entry['source_url'], 'Official presentation differs')
        active = {r['id'] for r in after.values() if r['data_source'] == 'CA_SOS' and r['year'] == 2026 and r['is_active'] and not r['is_duplicate']}
        withdrawn_id = review['withdrawal']['id']
        require(active == {r['measure_id'] for r in qualified} | {withdrawn_id}, 'Extra or missing public statewide measure')
        require(after[withdrawn_id]['is_active'] == 1 and after[withdrawn_id]['election_date'] is None, 'Withdrawal lost or assigned guessed date')
        changes = []
        matched = {e['existing_id'] for e in review['entries'] if e['existing_id'] is not None}
        for row_id, old in before.items():
            differences = {k: {'before': old[k], 'after': after[row_id][k]} for k in old if old[k] != after[row_id][k]}
            allowed = set()
            if row_id in matched:
                allowed = {'election_date', 'election_type', 'election_type_imputed', 'updated_at', 'update_count'}
            elif row_id == withdrawn_id:
                allowed = {'updated_at', 'update_count'}
            require(set(differences) <= allowed, f'Unexpected row/field changes: {row_id}, {set(differences) - allowed}')
            if differences:
                changes.append({'id': row_id, 'fields': differences})
        tables = [r[0] for r in before_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        old_schema = {r['name']: tuple(r) for r in before_conn.execute('SELECT type,name,tbl_name,sql FROM sqlite_master')}
        new_schema = {r['name']: tuple(r) for r in after_conn.execute('SELECT type,name,tbl_name,sql FROM sqlite_master')}
        require(all(new_schema.get(k) == v for k,v in old_schema.items()), 'Existing schema/index/trigger changed')
        added_schema = set(new_schema) - set(old_schema)
        require(added_schema == {'statewide_ballot_entries', 'statewide_ballot_reviews',
                                'sqlite_autoindex_statewide_ballot_entries_1',
                                'sqlite_autoindex_statewide_ballot_reviews_1'}, 'Unexpected schema additions')
        old_sequences = dict(before_conn.execute('SELECT name,seq FROM sqlite_sequence'))
        new_sequences = dict(after_conn.execute('SELECT name,seq FROM sqlite_sequence'))
        require(new_sequences == {**old_sequences, 'measures': old_sequences['measures'] + len(new_ids)}, 'Sequence drift')
        require(sorted(new_ids) == list(range(old_sequences['measures'] + 1, new_sequences['measures'] + 1)), 'Unexpected inserted IDs')
        preserved_tables = []
        for table in tables:
            if table == 'measures' or table == 'sqlite_sequence' or table.startswith('measure_search'):
                continue
            require(row_multiset(before_conn, table) == row_multiset(after_conn, table), f'Unrelated table changed: {table}')
            preserved_tables.append(table)
        old_search, new_search = row_multiset(before_conn, 'measure_search'), row_multiset(after_conn, 'measure_search')
        require(not old_search - new_search and sum((new_search - old_search).values()) == len(new_ids), 'FTS lost existing rows or added wrong count')
        expected_search = Counter()
        for row_id in new_ids:
            row = after[row_id]
            values = tuple(row[k] for k in ('fingerprint', 'title', 'description', 'ballot_question', 'summary_title', 'summary_text', 'county'))
            expected_search[hashlib.sha256(repr(values).encode()).hexdigest()] += 1
        require(new_search - old_search == expected_search, 'FTS additions do not match inserted rows')
        docs = documents_for_website(after_conn)
        require(docs == documents_for_website(before_conn), 'Registrar document projection changed')
        public = {m['id']: m for m in json.loads(Path(candidate_site).with_name('measures-data.json').read_text(encoding='utf-8'))}
        old_public = {m['id']: m for m in json.loads(Path(baseline_site).with_name('measures-data.json').read_text(encoding='utf-8'))}
        require(set(public) == set(old_public) | new_ids, 'Export ID set differs')
        public_changes = Counter()
        document_role_corrections = []
        timestamp_regenerations = 0
        for row_id in set(public) & set(old_public):
            old, new = old_public[row_id], public[row_id]
            fields = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
            if 'last_seen_at' in fields and before[row_id]['last_seen_at'] is None:
                require(start <= datetime.fromisoformat(new['last_seen_at']) <= end, 'Regenerated timestamp outside build window')
                fields.remove('last_seen_at')
                timestamp_regenerations += 1
            allowed = {'election_date', 'election_type', 'election_type_imputed', 'updated_at', 'update_count',
                       'ballot_status', 'proposition_number', 'official_title', 'official_description',
                       'official_source_captured_at', 'status_reason', 'withdrawn_on', 'withdrawn_from_election',
                       'source_url', 'external_links'} if row_id in matched | {withdrawn_id} else set()
            if row_id == 12419 and 'official_documents' in fields:
                # Exactly one independently inspected public-role correction.
                # No URL, SHA, raw role association or unrelated document changes.
                def by_document(groups):
                    return {(d['source_url'], d['sha256']): d for d in groups}
                old_docs, new_docs = (by_document(r['official_documents']) for r in (old, new))
                require(old_docs.keys() == new_docs.keys(), 'Measure Z document membership changed')
                key = (SB_Z_ARGUMENT_URL, SB_Z_ARGUMENT_SHA256)
                require(old_docs[key]['roles'] == ['analysis', 'argument_for'], 'Unexpected role-correction preimage')
                expected_doc = {**old_docs[key], 'roles': ['argument_for'], 'labels': ['Argument in favor'],
                                'source_roles': ['analysis', 'argument_for'], 'role_review_note': SB_Z_ROLE_NOTE,
                                'role_reviewed_at': '2026-10-08'}
                require(new_docs == {**old_docs, key: expected_doc}, 'Unreviewed county document change')
                allowed.add('official_documents')
                document_role_corrections.append({'id': row_id, 'source_url': key[0], 'sha256': key[1]})
            require(fields <= allowed, f'Unexpected public changes: {row_id}, {fields - allowed}')
            public_changes.update(fields)
        for assignment in qualified:
            row = public[assignment['measure_id']]
            require(all(row.get(k) == assignment[k] for k in ('proposition_number', 'ballot_status', 'official_title', 'official_description', 'source_url', 'election_date')), 'Public assignment lost')
            entry = next(e for e in review['entries'] if e['proposition_number'] == row['proposition_number'])
            require(row['official_description'] == entry['description'], 'Official description lost or changed')
            if row['id'] in new_ids:
                require(row['measure_id'] == f"PROP_{row['proposition_number']}_2026", 'New key lacks year')
                require(not any(r['measure_id'] == row['measure_id'] for r in before.values()), 'New canonical key collides')
                require(row['source_url'] == after[row['id']]['source_url'], 'New source link changed')
            for link in row.get('external_links', []):
                if link['source'] == 'Official Voter Guide':
                    require(link['url'] == assignment['source_url'], 'Generic voter guide survived')
                if link['source'] == 'CA SOS Eligible Measures':
                    raise ValueError('Superseded eligible initiative link survived')
                if link['source'].startswith('CA Legislature ('):
                    require(link['url'] == LEGISLATION_URLS[(assignment['election_date'], assignment['proposition_number'])], 'Wrong legislative session')
        withdrawn = public[withdrawn_id]
        require(withdrawn['ballot_status'] == 'withdrawn' and withdrawn['election_date'] is None, 'Public withdrawal status wrong')
        require(withdrawn['status_reason'] == review['withdrawal']['status_reason'] and withdrawn['withdrawn_on'] == '2026-06-25', 'Withdrawal evidence missing')
        require(withdrawn['withdrawn_from_election'] == '2026-11-03' and not withdrawn.get('proposition_number'), 'Withdrawal appears assigned')
        require([l['source'] for l in withdrawn['external_links']] == ['CA SOS withdrawal record'], 'Withdrawal has misleading source links')
        require({i: m['official_documents'] for i, m in public.items() if m.get('official_documents')} == docs, 'Public document groups changed')
        def topic_counts(rows):
            return Counter(r['topic_primary'] or r['category_topic'] for r in rows.values()
                           if r['is_active'] and not r['is_duplicate'] and (r['topic_primary'] or r['category_topic']))
        old_topics, new_topics = topic_counts(before), topic_counts(after)
        topic_delta = {t: new_topics[t] - old_topics[t] for t in old_topics.keys() | new_topics.keys() if new_topics[t] != old_topics[t]}
    finally:
        before_conn.close()
        after_conn.close()
    old_html, html = (Path(p).read_text(encoding='utf-8') for p in (baseline_site, candidate_site))
    embedded = {}
    for name in ('financeData', 'insightsData', 'recommendations', 'topics'):
        pattern = r'\bconst ' + name + r' = (.*?);\s*\n'
        old_match, new_match = re.search(pattern, old_html), re.search(pattern, html)
        require(old_match and new_match, f'Missing embedded payload: {name}')
        old_payload, new_payload = json.loads(old_match[1]), json.loads(new_match[1])
        if name == 'topics':
            expected = [{**t, 'count': t['count'] + topic_delta.get(t['topic'], 0)} for t in old_payload]
            require(expected == new_payload, 'Topic counts changed beyond the reviewed cohort correction')
        else:
            require(old_payload == new_payload, f'Embedded {name} changed')
        embedded[name] = digest(json.loads(new_match[1]))
    require(all(sha(p) == h for p, h in inputs.items()), 'Production input changed during verification')
    return {'verified': True, 'review_sha256': digest(review), 'active_measures': len(public),
            'statewide_propositions': len(qualified), 'new_ids': sorted(new_ids), 'withdrawn_id': withdrawn_id,
            'row_field_diff': changes, 'unrelated_tables_preserved': preserved_tables,
            'existing_search_rows_preserved': sum(old_search.values()), 'new_search_rows': len(new_ids),
            'existing_schema_preserved': True, 'added_schema': sorted(added_schema),
            'sqlite_sequences_verified': True, 'withdrawn_publicly_accessible': True,
            'public_changed_fields': dict(public_changes), 'regenerated_null_timestamps': timestamp_regenerations,
            'measures_with_documents': len(docs), 'document_links': sum(map(len, docs.values())),
            'document_role_corrections': document_role_corrections,
            'embedded_payload_sha256': embedded, 'production_inputs_unchanged': True,
            'topic_count_delta': topic_delta,
            'candidate_db_sha256': sha(candidate_db), 'candidate_html_sha256': sha(candidate_site),
            'candidate_json_sha256': sha(Path(candidate_site).with_name('measures-data.json'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('baseline-db', 'baseline-site', 'candidate-db', 'candidate-site', 'review-path', 'build-metadata', 'production-hashes', 'output'):
        parser.add_argument('--' + flag, type=Path, required=True)
    args = vars(parser.parse_args())
    output = args.pop('output')
    report = verify(**args)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('row_field_diff', 'embedded_payload_sha256')}, indent=2))


if __name__ == '__main__':
    main()
