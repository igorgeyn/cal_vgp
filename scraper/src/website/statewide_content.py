"""Source-bound statewide voter-guide projection; no database writes or network I/O."""
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import hashlib
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString

ELECTION = '2026-11-03'
NUMBERS = (1, 2, 3, 4, 5, 37, 38, 39, 40, 41, 42, 43, 44, 45)
DATA = Path(__file__).with_name('data') / 'statewide_2026.json'

STYLE = """
.statewide-source-note { color: #536166; font-size: .82rem; line-height: 1.5; max-width: 56rem; margin-top: .45rem; }
.statewide-future { margin: 1.2rem .5rem; padding: .8rem 1rem; border-top: 1px solid #d6d1bf; font-size: .85rem; }
.statewide-future summary { cursor: pointer; font-weight: 600; }
.statewide-future li { margin: .7rem 0 .7rem 1rem; }
.statewide-future a { color: #245b68; text-decoration: underline; }
.hero-section .measure-card.statewide-card { min-height: 240px; border-left: 3px solid #967228; background: #fbfaf6; }
.hero-section .statewide-card .card-title { font-size: 1.05rem; line-height: 1.4; }
.hero-section .measure-card.statewide-card .card-summary { font-size: .88rem; line-height: 1.6; font-style: normal; color: #3e4c51; -webkit-line-clamp: 4; }
.hero-section .statewide-card .card-meta { font-size: .75rem; line-height: 1.5; color: #536166; }
.measure-card.statewide-card:focus-visible { outline: 3px solid #245b68; outline-offset: 3px; }
.statewide-guide { color: var(--text-primary, #202b2d); font-size: .94rem; line-height: 1.65; }
.measure-detail-modal .statewide-guide h3, .statewide-guide h3 { font-size: 1.08rem; margin: 1.4rem 0 .65rem; text-transform: none; letter-spacing: normal; }
.statewide-guide h4 { font-size: .94rem; margin: 0 0 .5rem; }
.statewide-guide p { margin: .5rem 0 .85rem; }
.statewide-guide a { color: #245b68; text-decoration: underline; text-underline-offset: .15em; overflow-wrap: anywhere; }
.statewide-guide .sg-note { font-size: .82rem; color: #536166; line-height: 1.55; }
.statewide-guide .sg-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; margin: .85rem 0; }
.statewide-guide .sg-panel { border: 1px solid #d6d1bf; border-radius: 8px; padding: 1rem; background: #fbfaf6; min-width: 0; }
.statewide-guide .sg-amount { font-size: 1.35rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.statewide-guide blockquote { margin: .6rem 0; padding: 0 0 0 .8rem; border-left: 3px solid #c1ad70; font-style: normal; }
.statewide-guide details { border-top: 1px solid #d6d1bf; padding: .75rem 0; }
.statewide-guide summary { cursor: pointer; font-weight: 600; line-height: 1.5; overflow-wrap: anywhere; }
.statewide-guide ul { padding-left: 1.3rem; margin: .6rem 0; }
.statewide-guide li { margin: .4rem 0; }
.statewide-guide .sg-record { display: flex; justify-content: space-between; align-items: baseline; gap: .75rem; border-bottom: 1px solid #e4e0d5; padding: .65rem 0; }
.statewide-guide .sg-record > :first-child { min-width: 0; overflow-wrap: anywhere; }
.statewide-guide .sg-record > :last-child { flex-shrink: 0; font-variant-numeric: tabular-nums; }
.statewide-guide .sg-source-issue { color: #79420d; font-size: .82rem; }
.statewide-guide .sg-contributor-block { display: block; margin: .2rem 0; }
.statewide-guide a:focus-visible, .statewide-guide summary:focus-visible { outline: 3px solid #245b68; outline-offset: 3px; }
@media (max-width: 580px) {
  .header .view-controls { flex-wrap: wrap; max-width: 100%; }
  .pagination-container .pagination-controls { flex-wrap: wrap; max-width: 100%; justify-content: center; }
  .hero-section .hero-carousel { display: grid; grid-template-columns: 1fr 1fr; }
  .hero-section .hero-carousel .carousel-track-container { grid-column: 1 / -1; grid-row: 1; }
  .hero-section .hero-carousel .carousel-prev { grid-column: 1; grid-row: 2; justify-self: end; }
  .hero-section .hero-carousel .carousel-next { grid-column: 2; grid-row: 2; justify-self: start; }
  .statewide-guide .sg-columns { grid-template-columns: 1fr; }
  .statewide-guide .sg-record { display: block; }
  .statewide-guide .sg-record > :last-child { display: block; margin-top: .3rem; }
}
"""


def link(url, label):
    parsed = urlparse(url or '')
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Unsafe statewide source link')
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(label)}</a>'


def bullet_list(values):
    return '<ul>' + ''.join(f'<li>{escape(v)}</li>' for v in values) + '</ul>'


def render_future_ballots(package):
    items = package.get('future_ballots', [])
    if not items:
        return ''
    out = '<details class="statewide-future"><summary>Looking ahead: statewide measures assigned to 2028</summary><ul>'
    for item in items:
        date = datetime.strptime(item['election_date'], '%Y-%m-%d').strftime('%B %d, %Y')
        out += f'<li><strong>{date}:</strong> {link(item["url"], item["label"])}</li>'
    return out + '</ul><p>These later assignments are listed separately from the November 2026 propositions. ' + link(package['qualified_url'], 'See the SOS qualified list') + '.</p></details>'


def render_sections(guide):
    """One escaped renderer for the explorer and individual pages."""
    sources = guide['sources']
    source_note = (f'<p class="sg-note">Official voter guide · source captured '
                   f'{escape(sources["overview"]["captured_at"][:10])}. '
                   f'{link(guide["source_url"], "Read the official overview")}</p>')
    main = '<div class="statewide-guide">'
    main += '<h3>What your vote means</h3><div class="sg-columns">'
    for heading, value in [('A YES vote', guide['yes_meaning']), ('A NO vote', guide['no_meaning'])]:
        main += f'<div class="sg-panel"><h4>{heading}</h4><p>{escape(value)}</p></div>'
    main += '</div>' + source_note
    main += ('<details><summary>Official title and summary</summary>'
             + bullet_list(guide['official_summary'])
             + '<p class="sg-note">Prepared by the Attorney General. '
             + link(sources['summary']['final_url'], 'Read the official title and summary') + '</p></details>')
    main += '<h3>Official documents</h3><ul>'
    main += ''.join(f'<li>{link(d["url"], d["label"])}</li>' for d in guide['documents'])
    main += '</ul></div>'

    research = '<div class="statewide-guide"><h3>Fiscal impact</h3>'
    research += bullet_list(guide['fiscal_estimate'])
    research += '<p class="sg-note">Legislative Analyst’s estimate, published in the official voter guide. ' + link(sources['analysis']['final_url'], 'Read the complete analysis') + '</p>'
    for section in guide['analysis']:
        research += f'<details><summary>{escape(section["heading"])} — Legislative Analyst</summary>'
        research += ''.join(f'<p>{escape(p)}</p>' for p in section['paragraphs'])
        research += '<p class="sg-note">Figures and full document formatting are available in the ' + link(sources['analysis']['final_url'], 'official analysis') + '.</p></details>'
    research += '<h3>Arguments in the voter guide</h3><p class="sg-note">These are the authors’ advocacy statements, not impartial analysis or CalBallot endorsements. Official agencies have not checked these arguments for accuracy.</p><div class="sg-columns">'
    for heading, field in [('Argument for', 'argument_for'), ('Argument against', 'argument_against')]:
        research += f'<div class="sg-panel"><h4>{heading}</h4><blockquote>{escape(guide[field])}</blockquote></div>'
    research += '</div><p>' + link(sources['arguments']['final_url'], 'Read the full arguments, authors and rebuttals') + '</p>'
    research += '<h3>Supporters and opponents listed in the guide</h3><div class="sg-columns">'
    for heading, field in [('Supporters', 'supporters'), ('Opponents', 'opponents')]:
        research += f'<div class="sg-panel"><h4>{heading}</h4>{bullet_list(guide[field])}</div>'
    research += '</div><p class="sg-note">These are the submitted lists in the official overview, not exhaustive lists of endorsements. “None submitted” does not mean no opposition exists.</p>' + source_note + '</div>'

    finance = '<div class="statewide-guide"><h3>2026 reported campaign contributions</h3>'
    finance += '<p class="sg-note">SOS-reported contributions to primarily formed committees. These are contributions, not spending. Some committees work on several measures or transfer money to other committees; do not add these figures across measures or treat them as unique donor dollars.</p><div class="sg-columns">'
    for side, heading in [('support', 'In support'), ('oppose', 'In opposition')]:
        info = guide['finance'][side]
        finance += f'<div class="sg-panel"><h4>{heading}</h4>'
        if info['total'] is not None:
            finance += f'<p class="sg-amount">{escape(info["total"])}</p><p class="sg-note">Reported through {escape(info["as_of"])} · {len(info["committees"])} committee(s)</p>'
        else:
            finance += f'<p>No committees identified by the SOS as of {escape(info["as_of"])}.</p><p class="sg-note">This is not a finding of zero contributions or spending.</p>'
        finance += '</div>'
    finance += '</div><p class="sg-note">' + link(sources['finance']['final_url'], 'SOS contribution totals and reporting scope') + f' · captured {escape(sources["finance"]["captured_at"][:10])}.</p>'
    for side, heading in [('support', 'Supporting committees'), ('oppose', 'Opposing committees')]:
        info = guide['finance'][side]
        if not info['committees']:
            continue
        finance += f'<details><summary>{heading} ({len(info["committees"])})</summary>'
        for c in info['committees']:
            finance += '<div class="sg-record"><span>' + link(c['url'], c['name']) + f' <span class="sg-note">(ID {escape(c["id"])})</span></span><strong>{escape(c["amount"])}</strong></div>'
        if info.get('source_row_difference_cents'):
            delta = info['source_row_difference_cents'] / 100
            finance += f'<p class="sg-source-issue">The source’s committee rows differ from its published total by ${abs(delta):,.2f}. The total above is the SOS-published figure.</p>'
        finance += '</details>'
    top = guide.get('top_contributors')
    finance += '<h3>Top contributors by committee</h3>'
    if top:
        finance += f'<p class="sg-note">FPPC list updated {escape(top["source_updated_at"])}. These lists cover qualifying committees, not every donor or all campaign money. They are not a breakdown of the SOS totals above: the sources have different reporting coverage, and even one FPPC donor amount can exceed a displayed SOS total. An asterisk (*) marks money for a committee involved in multiple measures; it cannot be allocated to this measure alone. Lists below are not added together.</p>'
        for c in top['committees']:
            heading = 'Supporting' if c['side'] == 'support' else 'Opposing'
            finance += f'<details><summary>{heading}: {escape(c["name"])}</summary>'
            for donor in c['donors']:
                name = ''
                for block in donor['contributor_blocks']:
                    css = 'sg-contributor-block sg-note' if block['attribution'] else 'sg-contributor-block'
                    name += f'<span class="{css}">'
                    for part in block['parts']:
                        name += (link(part['url'], part['text']) if part.get('url')
                                 else '<br>' if part['text'] == '\n' else escape(part['text']))
                    name += '</span>'
                if donor['grouped_names']:
                    name += '<span class="sg-contributor-block sg-note">FPPC includes multiple names in this row; the amount is not split between them here.</span>'
                amount = escape(donor['amount']) if not donor['source_issue'] else 'Amount needs verification'
                finance += f'<div class="sg-record"><span>{name} <span class="sg-note">{escape(donor["state"])}</span></span><strong>{amount}</strong></div>'
                if donor['source_issue']:
                    finance += f'<p class="sg-source-issue">{escape(donor["source_issue"])} The source displays {escape(donor["amount"])}.</p>'
            finance += '</details>'
    else:
        finance += '<p>The captured FPPC top-contributor list has no entry for this proposition. That does not establish that it has no donors.</p>'
    finance += '<p>' + link(sources['contributors']['final_url'], 'Open the FPPC lists and methodology') + '</p><p class="sg-note">This is a reporting snapshot. A contribution timeline, donor concentration and sector breakdown have not been calculated for these 2026 records. Earlier elections’ receipt totals use CalBallot’s separate historical finance dataset.</p></div>'
    return {'main': main, 'research': research, 'finance': finance}


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def source_body(raw, number):
    soup = BeautifulSoup(raw, 'html.parser')
    prop = soup.select_one('#propNum')
    body = soup.select_one('#mainCont')
    if not prop or text(prop) != str(number) or not body:
        raise ValueError(f'Wrong or missing proposition identity: {number}')
    if 'California General Election November 3, 2026' not in text(soup):
        raise ValueError('Wrong voter-guide election')
    return soup, body


def parse_guide(overview_raw, title_raw, analysis_raw, number):
    """Extract labelled fields only inside this proposition's official content."""
    overview, body = source_body(overview_raw, number)
    _, summary_body = source_body(title_raw, number)
    _, analysis_body = source_body(analysis_raw, number)
    headings = body.select('.summaryHeadings')
    if len(headings) != 1:
        raise ValueError('Missing or duplicate guide summary')
    summary = headings[0].parent.find_next_sibling('p')
    labels = [text(n).rstrip(':') for n in summary.select('strong')]
    if labels != ['Fiscal Impact', 'Supporters', 'Opponents']:
        raise ValueError(f'Unexpected overview fields: {labels}')
    parts = re.split(r'\b(Fiscal Impact|Supporters|Opponents)\s*:\s*', text(summary))
    if len(parts) != 7:
        raise ValueError('Ambiguous overview field boundaries')
    fields = {parts[i]: parts[i + 1].strip() for i in (1, 3, 5)}
    votes = {}
    for marker in body.select('.yesNoProCon'):
        label = text(marker)
        if label not in ('YES', 'NO', 'PRO', 'CON') or label in votes:
            raise ValueError('Duplicate or unknown vote/argument label')
        paragraph = text(marker.parent)
        paragraph = paragraph[len(label):].strip()
        paragraph = re.sub(r'^A (?:YES|NO) vote on this measure means:\s*', '', paragraph)
        votes[label] = paragraph
    if set(votes) != {'YES', 'NO', 'PRO', 'CON'} or not all(votes.values()):
        raise ValueError('Incomplete vote/argument overview')
    official_list = summary_body.select_one('ul.blts')
    if not official_list:
        raise ValueError('Missing official title/summary bullets')
    bullets = [text(li) for li in official_list.find_all('li', recursive=False)]
    fiscal_heading = next((h for h in summary_body.find_all('h3')
                           if text(h).startswith('SUMMARY OF LEGISLATIVE ANALYST')), None)
    fiscal_list = fiscal_heading.find_next_sibling('ul') if fiscal_heading else None
    if not fiscal_list:
        raise ValueError('Missing official fiscal estimate')
    fiscal_bullets = [text(li) for li in fiscal_list.find_all('li', recursive=False)]
    route = next((text(h) for h in body.select('.summaryHeadings h3')
                  if text(h).startswith('Put on the Ballot by ')), None)
    if route not in ('Put on the Ballot by the Legislature', 'Put on the Ballot by Petition Signatures'):
        raise ValueError('Unknown qualification method')
    sections = []
    for h in analysis_body.find_all('h3'):
        heading = text(h)
        if heading not in ('BACKGROUND', 'PROPOSAL', 'FISCAL EFFECTS'):
            continue
        paragraphs = []
        for sibling in h.next_siblings:
            if getattr(sibling, 'name', None) in ('h2', 'h3', 'hr'):
                break
            if getattr(sibling, 'name', None) in ('p', 'ul'):
                value = text(sibling)
                if value and not value.startswith('Visit ') and 'bckToTp' not in sibling.get('class', []):
                    paragraphs.append(value)
        sections.append({'heading': heading.title(), 'paragraphs': paragraphs})
    if {s['heading'] for s in sections} != {'Background', 'Proposal', 'Fiscal Effects'}:
        raise ValueError('Incomplete Legislative Analyst sections')
    base = f'https://voterguide.sos.ca.gov/propositions/{number}/index.htm'
    nav = overview.select_one('#propNav')
    current = next((li for li in nav.find_all('li', recursive=False)
                    if li.find('a', href=f'/propositions/{number}/index.htm')), None)
    if not current:
        raise ValueError('Missing proposition navigation')
    links = []
    for a in current.select('a[href]'):
        label = text(a)
        url = urljoin(base, a['href'])
        if label in ('Official Title and Summary', 'Analysis', 'Arguments and Rebuttals',
                     'Text of Proposed Law (PDF)', 'Print (PDF)'):
            if urlparse(url).hostname not in ('voterguide.sos.ca.gov', 'vig.cdn.sos.ca.gov'):
                raise ValueError('Unexpected official document host')
            links.append({'label': label, 'url': url})
    if len(links) != 5:
        raise ValueError('Incomplete official document links')
    return dict(summary=parts[0].strip(), fiscal_impact=fields['Fiscal Impact'],
                supporters=[s.strip() for s in fields['Supporters'].split(';')],
                opponents=[s.strip() for s in fields['Opponents'].split(';')],
                yes_meaning=votes['YES'], no_meaning=votes['NO'],
                argument_for=votes['PRO'], argument_against=votes['CON'],
                official_summary=bullets, fiscal_estimate=fiscal_bullets,
                qualification_method=route, analysis=sections, documents=links)


def money_cents(value):
    value = value.rstrip('*').strip()
    # Currency whitespace is harmless; malformed grouping is not.
    value = re.sub(r'^\$\s+', '$', value)
    if not re.fullmatch(r'\$(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{1,2})?', value):
        raise ValueError('Malformed source amount: ' + value)
    return int(Decimal(value[1:].replace(',', '')) * 100)


def parse_finance(raw, number):
    """Keep SOS-published totals/committee rows distinct from historical receipts."""
    soup = BeautifulSoup(raw, 'html.parser')
    h1 = soup.find('h1')
    if not h1 or not re.match(rf'^Proposition {number}\s*-', text(h1)):
        raise ValueError('Wrong finance proposition')
    root = soup.select_one('#main-content-normal')
    result = {}
    for label, key in [('In Support of this measure:', 'support'), ('In Opposition to this measure:', 'oppose')]:
        headings = [h for h in root.find_all('h2') if text(h) == label]
        if len(headings) != 1:
            raise ValueError('Missing finance side')
        nodes = []
        for node in headings[0].next_siblings:
            if getattr(node, 'name', None) == 'h2':
                break
            if getattr(node, 'name', None):
                nodes.append(node)
        combined = ' '.join(text(n) for n in nodes)
        dates = set(re.findall(r'(?:Through|as of)\s+(\d{2}/\d{2}/\d{4})', combined))
        if len(dates) != 1:
            raise ValueError('Missing or conflicting finance reporting dates')
        as_of = datetime.strptime(dates.pop(), '%m/%d/%Y').date().isoformat()
        tables = [n for n in nodes if n.name == 'table']
        if not tables:
            if 'No committees identified as of' not in combined:
                raise ValueError('Unrecognized finance absence')
            result[key] = dict(status='no_committees_identified', as_of=as_of,
                               total=None, committees=[])
            continue
        if len(tables) != 1:
            raise ValueError('Ambiguous committee table')
        table = tables[0]
        match = re.search(r'Total amount of reported contributions to this measure:\s*(\$[\d,.]+)', text(table))
        if not match:
            raise ValueError('Missing reported finance total')
        total = match[1]
        committees = []
        for tr in table.find_all('tr'):
            cells = tr.find_all('td', recursive=False)
            if len(cells) != 3:
                continue
            identity = text(cells[0])
            if identity.startswith('Committee ID'):
                continue
            if not re.fullmatch(r'\d{6,8}', identity):
                raise ValueError('Unrecognized committee identity')
            url = cells[0].find('a', href=True)['href']
            if urlparse(url).hostname != 'cal-access.sos.ca.gov':
                raise ValueError('Unexpected committee link')
            amount = text(cells[2])
            money_cents(amount)
            committees.append(dict(id=identity, name=text(cells[1]), amount=amount, url=url))
        if not committees or len({c['id'] for c in committees}) != len(committees):
            raise ValueError('Missing/duplicate committee rows')
        difference = sum(money_cents(c['amount']) for c in committees) - money_cents(total)
        result[key] = dict(status='reported', as_of=as_of, total=total, committees=committees,
                           source_row_difference_cents=difference)
    return result


def parse_top_contributors(raw):
    """FPPC lists remain per committee; never sum pass-through/multi-measure money."""
    soup = BeautifulSoup(raw, 'html.parser')
    if text(soup.find('h1')) != 'November 2026 General Election':
        raise ValueError('Wrong FPPC election')
    modified = re.search(r'Last Modified:\s*([A-Za-z]+ \d{1,2}, \d{4})', text(soup))
    if not modified:
        raise ValueError('Missing FPPC date')
    result = {}
    for button in soup.select('button[aria-controls]'):
        # Preserve, but recognize, the source's typo "Propostion 3".
        match = re.fullmatch(r'Prop(?:osition|ostion)\s+(\d+)', text(button))
        if not match:
            continue
        n = int(match[1])
        if n not in NUMBERS or n in result:
            raise ValueError('Unexpected/duplicate FPPC proposition')
        panel = soup.find(id=button['aria-controls'])
        body = panel.select_one('.panel-body')
        side = None
        committee = None
        groups = []
        for node in body.children:
            if not getattr(node, 'name', None):
                continue
            value = text(node)
            if node.name in ('h5', 'p') and value in ('Supporting', 'Opposing'):
                side = 'support' if value == 'Supporting' else 'oppose'
                committee = None
            elif node.name == 'h5' and value:
                raise ValueError(f'Unrecognized FPPC side heading: {value}')
            elif node.name in ('p', 'div') and not node.find('table') and value and not value.startswith('No committee'):
                link = node.find('a', href=True)
                committee = dict(name=value, url=link['href'] if link else None)
            elif node.find('table') or node.name == 'table':
                if side is None or committee is None:
                    raise ValueError(f'Unattached FPPC table for proposition {n}')
                table = node if node.name == 'table' else node.find('table')
                headers = [text(th) for th in table.select('thead th')]
                if headers != ['Number', 'Contributor', 'State', 'Total Contributions']:
                    raise ValueError(f'Unexpected FPPC columns: {headers}')
                donors = []
                for row in table.select('tbody tr'):
                    cells = row.find_all('td', recursive=False)
                    if len(cells) != 4:
                        continue  # The source's total row is deliberately not imported.
                    rank, name, state, amount = map(text, cells)
                    if not rank.isdigit() or not name:
                        raise ValueError('Malformed FPPC donor row')
                    try:
                        money_cents(amount)
                        issue = None
                    except ValueError:
                        issue = 'The source amount has an apparent formatting error; verify it in the official filing.'
                    blocks = contributor_blocks(cells[1])
                    name = ' / '.join(''.join(p['text'] for p in b['parts']).strip()
                                      for b in blocks if not b['attribution'])
                    donors.append(dict(rank=int(rank), name=name, state=state, amount=amount,
                                       contributor_blocks=blocks, source_issue=issue,
                                       grouped_names=sum(max(1, sum(bool(p.get('url')) for p in b['parts']))
                                                         for b in blocks if not b['attribution']) > 1,
                                       shared_campaign='*' in amount))
                if not donors:
                    raise ValueError('Empty FPPC donor table')
                groups.append({**committee, 'side': side, 'donors': donors})
                committee = None
        result[n] = dict(source_updated_at=datetime.strptime(modified[1], '%B %d, %Y').date().isoformat(),
                         source_anchor=button['aria-controls'], committees=groups)
    return result


def contributor_blocks(cell):
    """Keep each source link attached to its own name, with attribution separate.

    Some source rows group multiple contributor entities. Preserve all names,
    links, paragraph order and their one shared row amount; never assign the
    complete cell's text or money to just its first linked entity.
    """
    blocks = []
    for node in cell.find_all('p', recursive=False) or [cell]:
        parts = []
        def walk(parent):
            for child in parent.children:
                if isinstance(child, NavigableString):
                    value = re.sub(r'\s+', ' ', str(child))
                    if value.strip():
                        parts.append({'text': value})
                elif child.name == 'a':
                    parts.append({'text': text(child), 'url': child.get('href')})
                elif child.name == 'br':
                    parts.append({'text': '\n'})
                else:
                    walk(child)
        walk(node)
        if parts:
            blocks.append({'attribution': text(node).startswith('Top Donor'), 'parts': parts})
    if not blocks or all(b['attribution'] for b in blocks):
        raise ValueError('Missing FPPC contributor name')
    return blocks


def load_package():
    package = json.loads(DATA.read_text(encoding='utf-8'))
    if package.get('election_date') != ELECTION or package.get('schema_version') != 1:
        raise ValueError('Unsupported statewide content package')
    entries = package['entries']
    if [e['proposition_number'] for e in entries] != list(NUMBERS):
        raise ValueError('Statewide content does not cover the reviewed slate')
    for e in entries:
        if type(e['id']) is not int or not e['canonical_id'] or not e['topic']:
            raise ValueError('Incomplete reviewed statewide identity')
        if e['source_url'] != f"https://voterguide.sos.ca.gov/propositions/{e['proposition_number']}/index.htm":
            raise ValueError('Content source does not match proposition')
        if not all(e.get(k) for k in ('summary', 'yes_meaning', 'no_meaning', 'official_summary',
                                     'fiscal_estimate', 'argument_for', 'argument_against', 'sources')):
            raise ValueError('Incomplete reviewed statewide content')
    return package


def attach_statewide_content(measures, package=None):
    """Project into the exact accepted identities, retaining raw editorial fields."""
    if not any(m.get('ballot_status') == 'qualified' and m.get('election_date') == ELECTION for m in measures):
        return measures
    package = package or load_package()
    by_id = {e['id']: e for e in package['entries']}
    result = []
    for m in measures:
        if m.get('ballot_status') != 'qualified' or m.get('election_date') != ELECTION:
            result.append(m)
            continue
        entry = by_id.get(m.get('id'))
        if not entry or (m.get('measure_id'), m.get('proposition_number'), m.get('source_url')) != (
                entry['canonical_id'], entry['proposition_number'], entry['source_url']):
            raise ValueError(f'Statewide content identity mismatch: {m.get("id")}')
        projected = {**m, 'statewide_guide': deepcopy(entry),
                     'display_topic': entry['topic'], 'source_display': 'CA Secretary of State',
                     'official_description': entry['summary'],
                     'official_source_captured_at': entry['sources']['overview']['captured_at']}
        projected['statewide_sections'] = render_sections(entry)
        # Reviewed official links replace guessed links to earlier proposition
        # numbers/elections. Preserve independently verified legislative links.
        links = [l for l in m.get('external_links', []) if l.get('source', '').startswith('CA Legislature (')]
        links += [{'source': 'CA SOS - Qualified Measures', 'url': package['qualified_url'], 'confidence': 'high'},
                  {'source': 'Official Voter Guide', 'url': entry['source_url'], 'confidence': 'high'}]
        projected['external_links'] = links
        result.append(projected)
    return result
