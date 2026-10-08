"""Promote a hash-pinned statewide candidate in one exclusive SQLite transaction.

The scratch reconciler remains scratch-only. This separate, bounded cutover
requires an unchanged baseline, a reviewed candidate, and a fresh backup path.
It updates four existing rows, inserts eleven, and copies the two review tables.
The complete logical database must then equal the candidate before commit.
Public files are deployed separately as one Git revision after this check.
"""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.database.statewide_ballot import SCHEMA


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def logical_state(conn):
    """Compare schema, all rows and every indexed token/document/column/offset.

    FTS5 segment packing depends on when an index is read within a transaction.
    Compare its complete vocabulary instead of binary segment layout; preserve
    document sizes/configuration exactly. This also checks the actual index,
    unlike SELECT * on an external-content FTS table, which reads measures.
    """
    schema = sorted(conn.execute('SELECT type,name,tbl_name,sql FROM sqlite_master'))
    tables = {}
    for kind, name, _, _ in schema:
        if kind == 'table' and name not in ('measure_search_data', 'measure_search_idx'):
            tables[name] = Counter(hashlib.sha256(repr(tuple(row)).encode()).hexdigest()
                                   for row in conn.execute('SELECT * FROM ' + quoted(name)))
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.release_index_vocab USING fts5vocab(main, measure_search, instance)")
    index = hashlib.sha256()
    for row in conn.execute('SELECT term,doc,col,offset FROM temp.release_index_vocab ORDER BY term,doc,col,offset'):
        index.update(repr(tuple(row)).encode() + b'\n')
    tables['measure_search_index_tokens'] = index.hexdigest()
    return schema, tables


def checked_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
        raise ValueError('Symlink/junction paths are not allowed')
    if not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError('Expected an existing, singly linked database')
    if any(Path(str(path) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise ValueError('SQLite sidecars require explicit investigation, not deletion')
    return path.resolve()


def promote(*, baseline_db, candidate_db, target_db, baseline_sha256,
            candidate_sha256, backup, apply=False):
    baseline, candidate, target = map(checked_path, (baseline_db, candidate_db, target_db))
    if len({baseline, candidate, target}) != 3:
        raise ValueError('Baseline, candidate and target must be distinct')
    if sha(baseline) != baseline_sha256 or sha(candidate) != candidate_sha256:
        raise ValueError('Pinned baseline or candidate hash changed')
    backup = Path(backup).absolute()
    if backup.exists() or not backup.parent.is_dir():
        raise ValueError('Backup must be a new file in an existing directory')
    if any(p.is_symlink() or p.is_junction() for p in (backup, *backup.parents)):
        raise ValueError('Unsafe backup path')

    with closing(sqlite3.connect(candidate.as_uri() + '?mode=ro', uri=True)) as source:
        source.execute('BEGIN')
        if source.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise ValueError('Candidate integrity failure')
        if source.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Candidate foreign key failure')
        expected = logical_state(source)
        with closing(sqlite3.connect(baseline.as_uri() + '?mode=ro', uri=True)) as old:
            old.execute('BEGIN')
            before = logical_state(old)
            columns = [r[1] for r in old.execute('PRAGMA table_info(measures)')]
            old_rows = {r[0]: tuple(r) for r in old.execute('SELECT * FROM measures')}
        if columns[0] != 'id':
            raise ValueError('Unexpected measures column order')
        new_rows = {r[0]: tuple(r) for r in source.execute('SELECT * FROM measures')}
        inserted = sorted(new_rows.keys() - old_rows.keys())
        changed = sorted(i for i in old_rows.keys() & new_rows.keys() if old_rows[i] != new_rows[i])
        if old_rows.keys() - new_rows.keys() or len(inserted) != 11 or changed != [1, 2, 10956, 10960]:
            raise ValueError('Candidate is not the reviewed bounded statewide correction')
        for row_id in changed:
            fields = {k for k, a, b in zip(columns, old_rows[row_id], new_rows[row_id]) if a != b}
            allowed = {'updated_at', 'update_count'}
            if row_id != 1:
                allowed |= {'election_date', 'election_type', 'election_type_imputed'}
            if fields - allowed:
                raise ValueError('Unexpected existing-row mutation')

        # mode=rw never creates a missing target. No timeout: existing writers
        # or readers block the maintenance step instead of being interrupted.
        with closing(sqlite3.connect(target.as_uri() + '?mode=rw', uri=True, timeout=0)) as dest:
            dest.execute('PRAGMA foreign_keys=ON')
            if dest.execute('PRAGMA journal_mode').fetchone() != ('delete',):
                raise ValueError('Cutover requires the reviewed DELETE journal mode')
            dest.execute('BEGIN EXCLUSIVE')
            try:
                # The check and every write share the same SQLite writer lock.
                # A stale preflight cannot overwrite a concurrent writer.
                if sha(target) != baseline_sha256 or logical_state(dest) != before:
                    raise ValueError('Target has drifted from the complete baseline')
                report = {'status': 'checked', 'inserted_ids': inserted, 'updated_ids': changed,
                          'baseline_sha256': baseline_sha256, 'candidate_sha256': candidate_sha256,
                          'writer_exclusion': 'SQLite BEGIN EXCLUSIVE', 'logical_candidate_match': False}
                if not apply:
                    return report
                # No dirty pages yet; DELETE journal mode + the exclusive lock
                # makes this a consistent exact-byte backup, without a rename
                # gap or any removal of SQLite journal files.
                with backup.open('xb') as handle:
                    handle.write(target.read_bytes())
                    handle.flush()
                    import os
                    os.fsync(handle.fileno())
                if sha(backup) != baseline_sha256:
                    raise ValueError('Fresh backup failed verification')
                for statement in SCHEMA:
                    dest.execute(statement)
                for row_id in changed:
                    indices = [i for i, (a, b) in enumerate(zip(old_rows[row_id], new_rows[row_id])) if a != b]
                    assignments = ','.join(quoted(columns[i]) + '=?' for i in indices)
                    dest.execute('UPDATE measures SET ' + assignments + ' WHERE id=?',
                                 [new_rows[row_id][i] for i in indices] + [row_id])
                insert = 'INSERT INTO measures (' + ','.join(map(quoted, columns)) + ') VALUES (' + ','.join('?' for _ in columns) + ')'
                dest.executemany(insert, [new_rows[i] for i in inserted])
                for table in ('statewide_ballot_entries', 'statewide_ballot_reviews'):
                    rows = source.execute('SELECT * FROM ' + table).fetchall()
                    dest.executemany('INSERT INTO ' + table + ' VALUES (' + ','.join('?' for _ in rows[0]) + ')', rows)
                if dest.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                    raise ValueError('Promoted database integrity failure')
                if dest.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('Promoted database foreign key failure')
                if logical_state(dest) != expected:
                    raise ValueError('Complete promoted database differs from candidate')
                if sha(candidate) != candidate_sha256 or sha(baseline) != baseline_sha256:
                    raise ValueError('Pinned inputs changed during cutover')
                dest.commit()
                return {**report, 'status': 'applied', 'logical_candidate_match': True,
                        'backup': str(backup), 'backup_sha256': sha(backup),
                        'production_sha256': sha(target)}
            finally:
                dest.rollback()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-db', 'candidate-db', 'target-db', 'backup', 'report'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('baseline-sha256', 'candidate-sha256'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--apply', action='store_true')
    args = vars(parser.parse_args())
    output = args.pop('report')
    if output.exists():
        parser.error('Report path must be new')
    report = promote(**args)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
