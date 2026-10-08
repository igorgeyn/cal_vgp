"""Expand deduplicated county evidence to a new LocalArtifactStore directory."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def materialize(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    index = json.loads((source / 'index.json').read_text(encoding='utf-8'))
    if index['schema_version'] != 1 or destination.exists():
        raise ValueError('Use a supported source index and a new destination')
    targets = {}
    for name, expected in index['files'].items():
        path = PurePosixPath(name)
        if path.is_absolute() or '\\' in name or ':' in name or '..' in path.parts:
            raise ValueError('Unsafe evidence path')
        digest = expected['sha256']
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Invalid evidence digest')
        target = (destination / name).resolve()
        if not target.is_relative_to(destination):
            raise ValueError('Evidence target escapes destination')
        targets[name] = target
    verified = set()
    for expected in index['files'].values():
        digest = expected['sha256']
        blob = source / 'objects' / digest
        if digest not in verified:
            if blob.stat().st_size != expected['bytes'] or sha(blob) != digest:
                raise ValueError('Evidence blob does not match its index')
            verified.add(digest)
    destination.mkdir(parents=True)
    for name, target in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / 'objects' / index['files'][name]['sha256'], target)
    return {'verified': True, 'files_materialized': len(targets), 'unique_objects': len(verified)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.source, args.destination), indent=2))


if __name__ == '__main__':
    main()
