"""Seal or restore a private, allowlisted CalBallot recovery directory.

No network operations. Restore always targets a new directory and verifies
every file, not just the SQLite row count. Keep credentials outside the bundle.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

MANIFEST = 'recovery-manifest.json'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '\\' in name or ':' in name
            or any(p in ('', '.', '..') or p != p.rstrip('. ') for p in name.split('/'))):
        raise ValueError(f'Unsafe archive path: {name}')
    return path


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Recovery input must not contain symlinks')
        if not path.is_file() or path.name == MANIFEST:
            continue
        name = path.relative_to(root).as_posix()
        safe_name(name)
        if '.git' in path.parts or path.suffix.lower() in ('.pem', '.key', '.pfx'):
            raise ValueError(f'Credential/repository metadata excluded: {name}')
        if path.name == '.env' and any(line.strip() and not line.lstrip().startswith('#')
                                     for line in path.read_text().splitlines()):
            raise ValueError('Recovery .env must contain comments only')
        result[name] = {'sha256': sha(path), 'bytes': path.stat().st_size}
    return result


def pack(root, archive):
    root, archive = Path(root).resolve(), Path(archive).resolve()
    if archive.is_relative_to(root) or archive.exists() or (root / MANIFEST).exists():
        raise ValueError('Use an unsealed directory and a new archive outside it')
    files = inventory(root)
    manifest = {'schema_version': 1, 'status': 'prepared_candidate_not_published', 'files': files}
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for name in [*files, MANIFEST]:
            z.write(root / name, name)
    return {'archive_sha256': sha(archive), 'archive_bytes': archive.stat().st_size,
            'manifest_sha256': sha(root / MANIFEST), 'files': len(files)}


def restore(archive, destination, expected_sha256):
    archive, destination = Path(archive).resolve(), Path(destination).resolve()
    if sha(archive) != expected_sha256:
        raise ValueError('Archive checksum mismatch')
    if destination.exists():
        raise FileExistsError('Restore destination must be new')
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len({n.casefold() for n in names}) != len(names):
            raise ValueError('Duplicate/colliding archive paths')
        for info in z.infolist():
            safe_name(info.filename)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Archive symlink rejected')
        manifest = json.loads(z.read(MANIFEST))
        if manifest['schema_version'] != 1 or set(names) != set(manifest['files']) | {MANIFEST}:
            raise ValueError('Archive contents differ from manifest')
        destination.mkdir(parents=True)
        for name in names:
            target = (destination / name).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('Restore target escapes destination')
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(name) as source, target.open('xb') as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
    actual = inventory(destination)
    if actual != manifest['files']:
        raise ValueError('Restored files differ from manifest')
    return {'verified': True, 'files': len(actual), 'archive_sha256': expected_sha256}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    seal = commands.add_parser('pack')
    seal.add_argument('--directory', required=True, type=Path)
    seal.add_argument('--archive', required=True, type=Path)
    unseal = commands.add_parser('restore')
    unseal.add_argument('--archive', required=True, type=Path)
    unseal.add_argument('--destination', required=True, type=Path)
    unseal.add_argument('--sha256', required=True)
    args = parser.parse_args()
    report = (pack(args.directory, args.archive) if args.command == 'pack'
              else restore(args.archive, args.destination, args.sha256))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
