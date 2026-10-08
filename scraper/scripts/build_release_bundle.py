"""Build a fresh complete site from an explicit frozen workspace, without publishing.

Run the copy of this script inside the recovery workspace. All data/model
inputs come from that workspace. Application logs may be created there;
manifested inputs must remain unchanged.
"""
import argparse
from contextlib import closing
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ('.nojekyll', 'CNAME', 'robots.txt', 'favicon.svg', 'favicon.png', 'apple-touch-icon.png')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def clean_environment(model):
    environment = dict(os.environ)
    for key in list(environment):
        if any(token in key.upper() for token in ('API_KEY', 'SECRET', 'TOKEN', 'R2_', 'AWS_')):
            environment.pop(key)
    environment.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                       HF_HUB_DISABLE_TELEMETRY='1', PYTHON_DOTENV_DISABLED='1',
                       CALBALLOT_EMBEDDING_MODEL=str(model), PYTHONDONTWRITEBYTECODE='1')
    return environment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New build directory, outside the frozen workspace')
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Build output must be outside the frozen workspace')
    inputs = json.loads((ROOT / 'release-inputs.json').read_text(encoding='utf-8'))
    if not all(sha(ROOT / name) == value for name,value in inputs['sha256'].items()):
        raise ValueError('Frozen release input changed')
    output.mkdir(parents=True, exist_ok=False)
    site = output / 'site'
    site.mkdir()
    database = output / 'measures.db'
    with closing(sqlite3.connect((ROOT / 'scraper/data/ballot_measures.db').as_uri() + '?mode=ro', uri=True)) as source:
        with closing(sqlite3.connect(database)) as target:
            source.backup(target)
    database_before = sha(database)
    started = datetime.now().isoformat()
    environment = clean_environment(ROOT / 'model')
    commands = [
        [sys.executable, str(ROOT / 'scraper/scripts/generate_site.py'), '--db', str(database),
         '--output', str(site / 'index.html'), '--force', '--strict'],
        [sys.executable, str(ROOT / 'build_measure_pages.py'), '--site-dir', str(site)],
    ]
    with (output / 'build.log').open('w', encoding='utf-8') as log:
        for command in commands:
            result = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f'Release build failed with exit {result.returncode}; see build.log')
    for name in ASSETS:
        shutil.copyfile(ROOT / name, site / name)
    # Checking the unchanged input DB catches accidental enrichment writes even
    # if SQLite reports success and the HTML appears usable.
    if sha(database) != database_before:
        raise ValueError('The build mutated its measure database')
    if not all(sha(ROOT / name) == value for name,value in inputs['sha256'].items()):
        raise ValueError('The build mutated a frozen dependency')
    report = {'started_at_local': started, 'finished_at_local': datetime.now().isoformat(),
              'exit_code': 0, 'strict': True, 'input_manifest_sha256': sha(ROOT / 'release-inputs.json'),
              'candidate_db_sha256': sha(database), 'html_sha256': sha(site / 'index.html'),
              'json_sha256': sha(site / 'measures-data.json')}
    (output / 'build.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
