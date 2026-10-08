"""Recovery must reject incomplete/corrupt bundles and unsafe destinations."""
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / 'scripts' / f'{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


recovery = module('recovery_bundle')
pages = module('verify_release_bundle')
sources = module('materialize_recovery_sources')


def test_private_recovery_round_trip_and_no_overwrite(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'test.db').write_bytes(b'preserved bytes')
    archive = tmp_path / 'backup.zip'
    report = recovery.pack(source, archive)
    restored = tmp_path / 'restored'
    assert recovery.restore(archive, restored, report['archive_sha256'])['verified']
    assert (restored / 'test.db').read_bytes() == b'preserved bytes'
    with pytest.raises(FileExistsError):
        recovery.restore(archive, restored, report['archive_sha256'])
    with pytest.raises(ValueError, match='checksum'):
        recovery.restore(archive, tmp_path / 'bad', '0' * 64)


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'C:/escape', 'a\\b', 'trailing. /x'])
def test_unsafe_archive_paths_rejected_before_writes(tmp_path, name):
    # Windows' ZIP writer normalizes backslashes before saving the header.
    if '\\' in name:
        with pytest.raises(ValueError, match='Unsafe'):
            recovery.safe_name(name)
        return
    archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr(name, b'bad')
    with pytest.raises(ValueError, match='Unsafe'):
        recovery.restore(archive, tmp_path / 'restore', recovery.sha(archive))
    assert not (tmp_path / 'restore').exists()


def test_credentials_are_not_sealed(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / '.env').write_text('TOKEN=must-not-be-archived')
    with pytest.raises(ValueError, match='comments only'):
        recovery.pack(source, tmp_path / 'backup.zip')


def test_site_gate_catches_missing_assets_before_link_checks(tmp_path):
    (tmp_path / 'measures-data.json').write_text(json.dumps([{'id': 7}]))
    (tmp_path / 'measures').mkdir()
    (tmp_path / 'measures/7.html').write_text('<html></html>')
    with pytest.raises(ValueError, match='static asset missing'):
        pages.verify(tmp_path)


@pytest.mark.parametrize('corrupt', [False, True])
def test_deduplicated_sources_restore_exact_bytes_or_fail_before_writes(tmp_path, corrupt):
    source = tmp_path / 'source'
    (source / 'objects').mkdir(parents=True)
    payload = b'%PDF-official-source'
    digest = recovery.hashlib.sha256(payload).hexdigest()
    (source / 'objects' / digest).write_bytes(b'corrupt' if corrupt else payload)
    index = {'schema_version': 1, 'files': {name: {'sha256': digest, 'bytes': len(payload)}
             for name in ('prod/sb/2026-11-03/first/a.pdf', 'prod/sb/2026-11-03/second/a.pdf')}}
    (source / 'index.json').write_text(json.dumps(index))
    destination = tmp_path / 'restored'
    if corrupt:
        with pytest.raises(ValueError, match='blob'):
            sources.materialize(source, destination)
        assert not destination.exists()
    else:
        assert sources.materialize(source, destination)['unique_objects'] == 1
        assert all((destination / name).read_bytes() == payload for name in index['files'])
