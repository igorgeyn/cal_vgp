"""Read-only F1 release gate for explicit production or rehearsal paths.

Seal immutable baseline/reviewed files first. Later verification reads the
actual --db/--site, allowing only justified timestamps within the supplied
load/build window. It never initializes Database or regenerates artifacts.
"""
from __future__ import annotations

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
from src.database.measure_documents import documents_for_website
from src.website.local_measure_context import get_reviewed_historical_category

DB_FIELDS = {
    'measure_letter', 'state', 'county', 'jurisdiction', 'title', 'description',
    'vote_threshold', 'measure_type', 'source_url', 'pdf_url', 'election_type',
    'election_type_imputed', 'election_date', 'is_active', 'content_hash',
    'updated_at', 'last_seen_at', 'update_count',
}
PUBLIC_FIELDS = {
    'official_documents', 'title', 'description', 'measure_text', 'local_measure_type',
    'local_measure_type_short', 'local_historical_context', 'jurisdiction', 'pdf_url',
    'content_hash', 'updated_at', 'last_seen_at', 'update_count',
}
FOOTER = r'Data last updated ([A-Za-z]+ \d{2}, \d{4})'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def indexed(rows, key='id'):
    result = {row[key]: row for row in rows}
    require(len(result) == len(rows), f'duplicate {key}')
    return result


def read_db(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def changed_fields(before, after):
    return {key for key in before.keys() | after.keys()
            if key not in before or key not in after or before[key] != after[key]}


def check_public_delta(before, after):
    """Reject unexpected registrar fields as strictly as historical fields."""
    require(before.keys() <= after.keys(), 'exported field removed')
    fields = changed_fields(before, after)
    registrar = str(before.get('data_source', '')).endswith('_County_Registrar')
    require(fields <= (PUBLIC_FIELDS if registrar else {'last_seen_at'}),
            f'unexpected public delta on {before["id"]}: {sorted(fields)}')
    return fields


def check_time(value, start, end):
    require(isinstance(value, str), 'timestamp must be a string')
    try:
        timestamp = datetime.fromisoformat(value)
        valid = start <= timestamp <= end
    except (ValueError, TypeError):
        valid = False
    require(valid, f'timestamp outside declared load/build window: {value}')


def check_row(expected, actual, time_fields, start, end):
    require(expected.keys() == actual.keys(), 'row fields differ')
    for field in expected:
        if field in time_fields:
            check_time(actual[field], start, end)
        else:
            require(expected[field] == actual[field], f'unexpected {field} change')


def seal(args):
    paths = {
        'baseline_db': args.baseline_db, 'baseline_site': args.baseline_site,
        'baseline_data': args.baseline_site.with_name('measures-data.json'),
        'reviewed_db': args.reviewed_db, 'reviewed_site': args.reviewed_site,
        'reviewed_data': args.reviewed_site.with_name('measures-data.json'),
    }
    paths.update({f'jsonl_{i}': path for i, path in enumerate(args.jsonl)})
    require(len({Path(p).resolve() for p in paths.values()}) == len(paths), 'baseline and reviewed inputs must be separate files')
    payload = {key: {'path': str(Path(path).resolve()), 'sha256': digest(path)} for key, path in paths.items()}
    with args.manifest.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, indent=2)


def verify(manifest_path, db_path, site_path, start, end, mirror=None):
    require(start <= end, 'invalid load/build window')
    manifest = read_json(manifest_path)
    for item in manifest.values():
        require(digest(item['path']) == item['sha256'], f'sealed input changed: {item["path"]}')
    paths = {key: Path(item['path']) for key, item in manifest.items()}
    actual_paths = [Path(db_path), Path(site_path), Path(site_path).with_name('measures-data.json')]
    # Catch accidentally checking sealed evidence instead of the actual load.
    require(not ({p.resolve() for p in actual_paths} & {p.resolve() for p in paths.values()}),
            'actual paths must differ from sealed baseline/reviewed inputs')
    if mirror:
        actual_paths += [Path(mirror), Path(mirror).with_name('measures-data.json')]
    require(len({p.resolve() for p in actual_paths}) == len(actual_paths),
            'actual database/site/mirror paths must be distinct')
    input_hashes = {str(p.resolve()): digest(p) for p in actual_paths}
    baseline = read_db(paths['baseline_db'])
    reviewed = read_db(paths['reviewed_db'])
    actual = read_db(db_path)
    try:
        before = indexed([dict(r) for r in baseline.execute('SELECT * FROM measures')])
        expected = indexed([dict(r) for r in reviewed.execute('SELECT * FROM measures')])
        current = indexed([dict(r) for r in actual.execute('SELECT * FROM measures')])
        require(before.keys() == expected.keys() == current.keys(), 'measure identities inserted/removed')
        allowed_times = {}
        for mid, row in expected.items():
            delta = changed_fields(before[mid], row)
            if delta:
                require(str(before[mid]['data_source']).endswith('_County_Registrar'), 'historical database row changed')
                require(delta <= DB_FIELDS, f'unexpected registrar DB fields: {delta - DB_FIELDS}')
            allowed_times[mid] = delta & {'updated_at', 'last_seen_at'}
            check_row(row, current[mid], allowed_times[mid], start, end)

        def tables(connection):
            return {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require(tables(reviewed) == tables(actual), 'database table set differs')
        for table in sorted(tables(reviewed)):
            quoted = '"' + table.replace('"', '""') + '"'
            expected_schema = [tuple(r) for r in reviewed.execute(f'PRAGMA table_info({quoted})')]
            require(expected_schema == [tuple(r) for r in actual.execute(f'PRAGMA table_info({quoted})')], 'database columns differ')
            if table == 'measures':
                continue
            wanted = [dict(r) for r in reviewed.execute(f'SELECT * FROM {quoted}')]
            found = [dict(r) for r in actual.execute(f'SELECT * FROM {quoted}')]
            if table in {'registrar_load_scopes', 'registrar_identities'}:
                stamp = 'loaded_at' if table == 'registrar_load_scopes' else 'registered_at'
                primary = [r[1] for r in sorted(expected_schema, key=lambda r: r[5]) if r[5]]
                key = lambda row: tuple(row[k] for k in primary)
                prior = {key(dict(r)): dict(r) for r in baseline.execute(f'SELECT * FROM {quoted}')} if table in tables(baseline) else {}
                want_map = {key(r): r for r in wanted}
                found_map = {key(r): r for r in found}
                require(want_map.keys() == found_map.keys(), 'registrar registry rows differ')
                for identity, row in want_map.items():
                    time_fields = {stamp} if identity not in prior or row[stamp] != prior[identity][stamp] else set()
                    check_row(row, found_map[identity], time_fields, start, end)
            else:
                canonical = lambda rows: sorted(json.dumps(r, sort_keys=True, default=str) for r in rows)
                require(canonical(wanted) == canonical(found), f'table differs: {table}')
        require(actual.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'SQLite integrity failure')
        require(not actual.execute('PRAGMA foreign_key_check').fetchall(), 'foreign key violation')

        old_public = indexed(read_json(paths['baseline_data']))
        reviewed_public = indexed(read_json(paths['reviewed_data']))
        public = indexed(read_json(Path(site_path).with_name('measures-data.json')))
        active_ids = {r[0] for r in actual.execute('SELECT id FROM active_measures')}
        require(old_public.keys() == reviewed_public.keys() == public.keys() == active_ids, 'active/export ID mismatch')
        deltas = Counter()
        for mid, row in reviewed_public.items():
            deltas.update(check_public_delta(old_public[mid], row))
            times = set(allowed_times[mid])
            if current[mid]['last_seen_at'] is None:
                times.add('last_seen_at')  # Existing null -> build time behavior only.
            check_row(row, public[mid], times, start, end)
            for field in allowed_times[mid]:
                require(public[mid][field] == current[mid][field], 'exported load timestamp differs from database')

        # Independently aggregate recorded outcomes using SQL, not the builder.
        context_changes = []
        for mid, row in public.items():
            category = get_reviewed_historical_category(current[mid]['description']) if str(row['data_source']).endswith('_County_Registrar') else None
            cohort = None
            if category and row.get('upcoming_scope') == 'local':
                cohort = actual.execute(
                    "SELECT COUNT(*), SUM(passed=1), MIN(year) FROM active_measures "
                    "WHERE lower(trim(county))=lower(trim(?)) AND lower(trim(category_type))=lower(?) "
                    "AND passed IN (0,1) AND year IS NOT NULL AND data_source NOT LIKE '%_County_Registrar'",
                    (current[mid]['county'], category),
                ).fetchone()
            ctx = row.get('local_historical_context')
            if cohort and cohort[0] >= 5:
                require(ctx is not None, 'eligible local context absent')
                require((ctx['category_type'], ctx['total'], ctx['passed'], ctx['since'], ctx['pass_rate']) ==
                        (category, cohort[0], cohort[1], cohort[2], round(100 * cohort[1] / cohort[0])), 'local context differs from decided SQL cohort')
            else:
                require(ctx is None, 'ineligible local context present')
            if old_public[mid].get('local_historical_context') != ctx:
                context_changes.append({'id': mid, 'before': old_public[mid].get('local_historical_context'), 'after': ctx})

        docs = [dict(r) for r in actual.execute('SELECT * FROM measure_documents')]
        wanted_docs = {}
        canonical_ids = {r['measure_id']: mid for mid, r in current.items()}
        for key, path in paths.items():
            if not key.startswith('jsonl_'):
                continue
            for line in path.read_text(encoding='utf-8').splitlines():
                record = json.loads(line)
                mid = canonical_ids[record['measure']['measure_id']]
                for d in record['documents']:
                    require((mid, d['role']) not in wanted_docs, 'duplicate normalized document role')
                    wanted_docs[(mid, d['role'])] = {
                        'measure_id': mid, 'role': d['role'], 'source_url': d['source_url'],
                        'snapshot_filename': d['snapshot_filename'], 'sha256': d['sha256'],
                        'size_bytes': d['size_bytes'], 'content_type': d['content_type'],
                        'snapshot_id': record['snapshot_id'], 'captured_at': record['scraped_at'],
                        'source_page_url': record['measure']['source_url'],
                    }
        require({(d['measure_id'], d['role']): d for d in docs} == wanted_docs, 'document role reconciliation failed')
        exported_docs = documents_for_website(actual)
        require({mid: row['official_documents'] for mid, row in public.items() if row.get('official_documents')} == exported_docs,
                'public document groups differ from database')
    finally:
        baseline.close()
        reviewed.close()
        actual.close()

    html = Path(site_path).read_text(encoding='utf-8')
    reference_html = paths['reviewed_site'].read_text(encoding='utf-8')
    baseline_html = paths['baseline_site'].read_text(encoding='utf-8')
    for name in ('financeData', 'insightsData', 'recommendations', 'topics'):
        pattern = r'\bconst ' + name + r' = (.*?);\s*\n'
        old_match, new_match = re.search(pattern, baseline_html), re.search(pattern, html)
        require(old_match is not None and new_match is not None, f'missing {name}')
        require(json.loads(old_match[1]) == json.loads(new_match[1]), f'{name} changed')
    dates = re.findall(FOOTER, html)
    require(len(dates) == 1 and dates[0] in {start.strftime('%B %d, %Y'), end.strftime('%B %d, %Y')}, 'unexpected build date')
    require(re.sub(FOOTER, 'Data last updated <build date>', html) == re.sub(FOOTER, 'Data last updated <build date>', reference_html),
            'HTML differs beyond build date')
    if mirror:
        require(digest(site_path) == digest(mirror), 'HTML mirror differs')
        require(digest(Path(site_path).with_name('measures-data.json')) == digest(Path(mirror).with_name('measures-data.json')), 'JSON mirror differs')
    require(input_hashes == {path: digest(path) for path in input_hashes}, 'actual input changed during verification')
    for item in manifest.values():
        require(digest(item['path']) == item['sha256'], f'sealed input changed during verification: {item["path"]}')
    return {'verified': True, 'actual_paths_sha256': input_hashes, 'active_measures': len(public),
            'document_roles': len(docs), 'displayed_links': sum(len(d) for d in exported_docs.values()),
            'measures_with_documents': len(exported_docs), 'public_changed_fields': dict(deltas),
            'context_changes': context_changes, 'mirror_checked': mirror is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    seal_parser = sub.add_parser('seal')
    for field in ('baseline-db', 'baseline-site', 'reviewed-db', 'reviewed-site'):
        seal_parser.add_argument('--' + field, type=Path, required=True)
    seal_parser.add_argument('--jsonl', type=Path, action='append', required=True)
    seal_parser.add_argument('--manifest', type=Path, required=True)
    check_parser = sub.add_parser('check')
    for field in ('manifest', 'db', 'site', 'report'):
        check_parser.add_argument('--' + field, type=Path, required=True)
    check_parser.add_argument('--mirror', type=Path)
    for field in ('started-at', 'finished-at'):
        check_parser.add_argument('--' + field, type=datetime.fromisoformat, required=True,
                                  help='Local ISO time from the load/build process clock')
    args = parser.parse_args()
    if args.command == 'seal':
        seal(args)
    else:
        require(not args.report.exists(), 'report already exists')
        report = verify(args.manifest, args.db, args.site, args.started_at, args.finished_at, args.mirror)
        with args.report.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2)
        print(json.dumps({k: v for k, v in report.items() if k != 'context_changes'}, indent=2))


if __name__ == '__main__':
    main()
