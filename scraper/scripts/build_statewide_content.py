"""Build the reviewed statewide content projection from pinned offline evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.website.statewide_content import ELECTION, NUMBERS, parse_guide, parse_finance, parse_top_contributors, source_body


def build_package(evidence):
    evidence = Path(evidence)
    manifest = json.loads((evidence / 'capture.json').read_text(encoding='utf-8'))
    review = json.loads((evidence / 'review.json').read_text(encoding='utf-8'))
    if review['election_date'] != ELECTION or [e['proposition_number'] for e in review['entries']] != list(NUMBERS):
        raise ValueError('Unexpected reviewed slate')
    def source(name):
        raw = (evidence / 'sources' / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest[name]['sha256'] or manifest[name]['status'] != 200:
            raise ValueError('Evidence bytes/status changed: ' + name)
        return raw
    for name in manifest:
        source(name)
    from src.database.statewide_ballot import parse_qualified
    slate = parse_qualified(source('qualified.html'))
    if [(e['proposition_number'], e['official_title'], e['source_url']) for e in review['entries']] != [
            (e['proposition_number'], e['official_title'], e['source_url']) for e in slate]:
        raise ValueError('Review does not match captured qualified list')
    donors = parse_top_contributors(source('fppc.html'))
    entries = []
    for e in review['entries']:
        n = e['proposition_number']
        source_body(source(f'prop-{n}-arguments-rebuttals.html'), n)
        parsed = parse_guide(*[source(f'prop-{n}-{part}.html') for part in ('index', 'title-summary', 'analysis')], n)
        sources = {role: manifest[f'prop-{n}-{part}.html'] for role, part in (
            ('overview', 'index'), ('summary', 'title-summary'), ('analysis', 'analysis'),
            ('arguments', 'arguments-rebuttals'), ('finance', 'finance'))}
        sources['contributors'] = manifest['fppc.html']
        for role, part in [('overview', 'index'), ('summary', 'title-summary'),
                           ('analysis', 'analysis'), ('arguments', 'arguments-rebuttals')]:
            if sources[role]['final_url'] != f'https://voterguide.sos.ca.gov/propositions/{n}/{part}.htm':
                raise ValueError('Source URL/election mismatch')
        entries.append({**e, **parsed, 'sources': sources,
                        'finance': parse_finance(source(f'prop-{n}-finance.html'), n),
                        'top_contributors': donors.get(n)})
    future = []
    soup = BeautifulSoup(source('qualified.html'), 'html.parser')
    for heading in soup.find_all('h2'):
        label = heading.get_text(' ', strip=True)
        if '2028, Statewide Ballot Measures' not in label:
            continue
        election = datetime.strptime(label.split(', Statewide')[0], '%B %d, %Y').date().isoformat()
        for node in heading.next_siblings:
            if getattr(node, 'name', None) in ('h2', 'hr'):
                break
            if getattr(node, 'find_all', None):
                for a in node.find_all('a', href=True):
                    if a['href'].startswith('https://elections.cdn.sos.ca.gov/ballot-measures/pdf/'):
                        future.append(dict(election_date=election, label=a.get_text(' ', strip=True), url=a['href']))
    return dict(schema_version=1, election_date=ELECTION, future_ballots=future,
                qualified_url=manifest['qualified.html']['final_url'],
                qualified_source=manifest['qualified.html'], entries=entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build_package(args.evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Built {len(result["entries"])} source-backed statewide guides')


if __name__ == '__main__':
    main()
