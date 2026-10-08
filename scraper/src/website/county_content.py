"""Reviewed county questions and explanations, bound to immutable source bytes.

This projection owns display fields only. Registrar data and existing editorial
fields remain intact. A changed identity or dependent PDF stops generation until
the content is reviewed again; a newer capture of identical bytes is harmless.
"""
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

DATA = Path(__file__).with_name('data') / 'county_2026.json'
ELECTION = '2026-11-03'
SOURCE_HOSTS = {'sb': 'uploads.rov.sbcounty.gov', 'smc': 'smcacre.gov'}
LISTING_URLS = {'sb': 'https://elections.sbcounty.gov/elections/2026/1103/measures/',
                'smc': 'https://smcacre.gov/elections/november-3-2026-statewide-general-election'}
FINANCE_URLS = {'sb': 'https://elections.sbcounty.gov/Elected-Officials-Candidates/',
                'smc': 'https://smcacre.gov/elections/campaign-finance-information'}
IDENTITY = ('id', 'measure_id', 'county', 'jurisdiction', 'election_date', 'measure_letter', 'vote_threshold')

STYLE = """
.county-guide { font-size: .94rem; line-height: 1.65; color: #283b40; }
.county-guide h3 { font-size: 1.05rem; margin: 1.3rem 0 .6rem; }
.county-guide p { margin: .6rem 0; }
.county-guide a { color: #245b68; text-decoration: underline; text-underline-offset: .15em; overflow-wrap: anywhere; }
.county-guide a:focus-visible { outline: 3px solid #245b68; outline-offset: 3px; }
.county-guide .cg-note { font-size: .82rem; color: #536166; }
.county-guide blockquote { margin: .7rem 0; padding-left: 1rem; border-left: 3px solid #c1ad70; font-style: normal; }
.county-guide details { border-top: 1px solid #d6d1bf; padding: .85rem 0; }
.county-guide summary { cursor: pointer; font-weight: 600; }
.county-guide ul { padding-left: 1.3rem; }
.county-guide li { margin: .6rem 0; }
.local-measure-card .local-card-explanation { font-size: .85rem; line-height: 1.5; color: #3e4c51; margin: .65rem 0; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.local-measure-card .local-card-content-label { font-size: .7rem; color: #536166; margin: .6rem 0 0; }
"""


def load_package():
    package = json.loads(DATA.read_text(encoding='utf-8'))
    validate_package(package)
    return package


def validate_package(package):
    if package.get('schema_version') != 1 or package.get('election_date') != ELECTION:
        raise ValueError('Unsupported county content package')
    seen = set()
    for e in package['entries']:
        mid = e.get('id')
        if type(mid) is not int or mid in seen or e.get('election_date') != ELECTION:
            raise ValueError('Invalid or duplicate county content identity')
        seen.add(mid)
        if e.get('county_slug') not in SOURCE_HOSTS or not all(e.get(k) for k in ('measure_id', 'county', 'jurisdiction')):
            raise ValueError('Incomplete county identity')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', e.get('reviewed_at', '')):
            raise ValueError('Missing county content review date')
        if not e.get('question') or not e.get('explanation') or not e.get('sources'):
            raise ValueError('Incomplete county content')
        for source in e['sources']:
            parsed = urlsplit(source['url'])
            if (parsed.scheme != 'https' or parsed.hostname != SOURCE_HOSTS[e['county_slug']]
                    or parsed.username or parsed.password or parsed.fragment
                    or any(ord(c) < 33 for c in source['url']) or '\\' in source['url']):
                raise ValueError('Invalid county source URL')
            if not re.fullmatch(r'[0-9a-f]{64}', source['sha256']):
                raise ValueError('Invalid county source hash')
            if not source.get('pages') or any(type(p) is not int or p < 1 for p in source['pages']):
                raise ValueError('Missing PDF page citation')
            if source['role'] not in ('text', 'resolution', 'analysis', 'tax_rate_statement'):
                raise ValueError('Advocacy cannot support a county explanation')
            if source.get('verified_role') not in ('ballot_question', 'measure_text', 'impartial_analysis', 'tax_rate_statement'):
                raise ValueError('County source content role not reviewed')
        refs = [e['question_source'], *e['explanation_sources']]
        if not e['explanation_sources'] or any(type(i) is not int or not 0 <= i < len(e['sources']) for i in refs):
            raise ValueError('Invalid county content source references')
        if e['sources'][e['question_source']]['verified_role'] != 'ballot_question':
            raise ValueError('Question must cite reviewed ballot wording')


def source_links(entry, refs):
    links = []
    for i in dict.fromkeys(refs):
        source = entry['sources'][i]
        pages = ', '.join(map(str, source['pages']))
        label = f"{source['label']} (PDF {'page' if len(source['pages']) == 1 else 'pages'} {pages})"
        links.append(f'<a href="{escape(source["url"], quote=True)}#page={source["pages"][0]}">{escape(label)}</a>')
    return '; '.join(links)


def render_sections(entry, history=None):
    threshold = {'50%': 'Majority', '55%': '55%', '66.67%': 'Two-thirds'}.get(entry.get('vote_threshold'), 'Not listed')
    question = (
        '<section class="county-guide" aria-label="County ballot guide">'
        f'<p class="cg-note">Approval requirement: <strong>{escape(threshold)}</strong> '
        f'(<a href="{LISTING_URLS[entry["county_slug"]]}">county listing</a>).</p>'
        '<h3>Official ballot question</h3>'
        f'<blockquote>{escape(entry["question"])}</blockquote>'
        f'<p class="cg-note">{source_links(entry, [entry["question_source"]])}. '
        'Wording transcribed from the official filing; line breaks and spacing normalized.</p>'
    )
    if entry.get('notes'):
        question += '<ul class="cg-note">' + ''.join(f'<li>{escape(n)}</li>' for n in entry['notes']) + '</ul>'
    question += (
        '<details><summary>About this explanation and its sources</summary>'
        '<p>CalBallot explanation: AI-assisted, checked against the cited official documents. '
        'It is separate from the official ballot question and from campaign arguments.</p>'
        f'<p>{source_links(entry, entry["explanation_sources"])}</p>'
        f'<p class="cg-note">Content reviewed {escape(entry["reviewed_at"])}. '
        f'Source files checked {escape(entry.get("source_checked_at", entry["reviewed_at"]))}. '
        'Links open the county’s current files, which may change after review.</p></details>'
    )
    if history and history.get('records'):
        question += render_history(history)
    return question + '</section>'


def render_finance(entry):
    return (
        '<section class="county-guide"><h3>Campaign finance</h3>'
        '<p>CalBallot has not yet linked campaign-finance filings to this local measure. '
        'No contribution or spending total is reported here.</p>'
        f'<p><a href="{FINANCE_URLS[entry["county_slug"]]}">{escape(entry["county"])} County campaign-finance resources</a></p>'
        '<p class="cg-note">Use the November 2026 election, jurisdiction and measure name to search. '
        'City or regional committees may file with a different office; the county resource is a starting point, '
        'not a complete measure-specific filing list.</p></section>'
    )


def render_history(history):
    records = history['records']
    items = []
    for row in records:
        if type(row['id']) is not int or row['id'] < 1:
            raise ValueError('Invalid historical record link')
        label = f"{row['year']} · {row['jurisdiction']} · {row['designation']}"
        outcome = 'Passed' if row['passed'] == 1 else 'Failed'
        title = row.get('title') or ''
        preview = title[:150].rsplit(' ', 1)[0] + '…' if len(title) > 150 else title
        items.append(f'<li><a href="/measures/{row["id"]}.html">{escape(label)}</a> — {outcome}'
                     f'<p class="cg-note">{escape(preview)}</p></li>')
    return (
        '<details class="county-history"><summary>Explore the historical comparison</summary>'
        f'<p>{history["passed"]} of {history["total"]} recorded {escape(history["category_type"])} '
        f'measures in {escape(history["county_label"])} passed between {history["since"]} and {history["through"]}.</p>'
        '<p class="cg-note">Same county and broad measure type. These measures may have different '
        'purposes and voting rules. Historical outcomes are not a forecast.</p>'
        '<p>Recent records from this comparison:</p><ul>' + ''.join(items) + '</ul></details>'
    )


def attach_county_content(measures, package=None):
    rows = list(measures)
    if not any(str(m.get('measure_id', '')).startswith(('REG_SB_20261103_', 'REG_SMC_20261103_')) for m in rows):
        return rows
    package = load_package() if package is None else package
    validate_package(package)
    by_id = {e['id']: e for e in package['entries']}
    by_key = {e['measure_id']: e['id'] for e in package['entries']}
    result = []
    for m in rows:
        e = by_id.get(m.get('id'))
        if e is None:
            if m.get('measure_id') in by_key:
                raise ValueError(f'County content identity mismatch: {m.get("id")}')
            result.append(m)
            continue
        # Empty designation is meaningful for the regional transit district.
        if any((m.get(k) or '') != (e.get(k) or '') for k in IDENTITY):
            raise ValueError(f'County content identity mismatch: {m.get("id")}')
        docs = m.get('official_documents') or []
        for source in e['sources']:
            if not any(d.get('source_url') == source['url'] and d.get('sha256') == source['sha256']
                       and source['role'] in d.get('roles', []) for d in docs):
                raise ValueError(f'County content requires source re-review: {m["id"]} / {source["label"]}')
        projected = {**m, 'county_guide': deepcopy(e), 'county_explanation': e['explanation']}
        projected['county_sections'] = render_sections(e, m.get('local_historical_context'))
        projected['county_finance'] = render_finance(e)
        result.append(projected)
    return result
