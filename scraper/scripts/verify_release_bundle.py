"""Verify complete page/asset/document contracts of a generated site, offline."""
import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.document_links = []
        self.in_documents = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'section' and attrs.get('class') == 'official-documents':
            self.in_documents = True
        for attribute in ('href', 'src'):
            if attrs.get(attribute):
                self.urls.append(attrs[attribute])
        if self.in_documents and tag == 'a':
            self.document_links.append(attrs.get('href'))

    def handle_endtag(self, tag):
        if tag == 'section':
            self.in_documents = False


def verify(site):
    site = Path(site).resolve()
    rows = json.loads((site / 'measures-data.json').read_text(encoding='utf-8'))
    ids = [r['id'] for r in rows]
    id_set = set(ids)
    if any(type(i) is not int or i < 1 for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('Invalid public IDs')
    expected_paths = {f'measures/{i}.html' for i in ids}
    actual_paths = {p.relative_to(site).as_posix() for p in (site / 'measures').glob('*.html')}
    if expected_paths != actual_paths:
        raise ValueError('Page inventory does not match the export')
    for asset in ('.nojekyll', 'CNAME', 'robots.txt', 'favicon.svg', 'favicon.png', 'apple-touch-icon.png'):
        if not (site / asset).is_file():
            raise ValueError(f'Required static asset missing: {asset}')
    domain = (site / 'CNAME').read_text().strip()
    base_url = f'https://{domain}/'
    expected_sitemap = {base_url, base_url + 'use-calballot/'} | {base_url + path for path in expected_paths}
    sitemap_urls = [n.text for n in ET.parse(site / 'sitemap.xml').findall('.//{*}loc')]
    if len(sitemap_urls) != len(expected_sitemap) or set(sitemap_urls) != expected_sitemap:
        raise ValueError('Sitemap differs from the complete public page set')
    by_path = {f'measures/{r["id"]}.html': r for r in rows}
    external = Counter()
    internal = 0
    document_groups = 0
    inventory = {}
    checked_local_paths = set()
    for path in sorted(site.rglob('*')):
        if not path.is_file():
            continue
        data = path.read_bytes()
        relative = path.relative_to(site).as_posix()
        inventory[relative] = hashlib.sha256(data).hexdigest()
        if path.suffix != '.html':
            continue
        parser = Links()
        parser.feed(data.decode('utf-8'))
        if relative in by_path:
            row = by_path[relative]
            expected = [d['source_url'] for d in row.get('official_documents', [])]
            if parser.document_links != expected:
                raise ValueError(f'Official document grouping differs: {relative}')
            document_groups += len(expected)
            if f'/#m={row["id"]}' not in parser.urls:
                raise ValueError(f'Explorer route missing: {relative}')
        for url in parser.urls:
            parsed = urlsplit(urljoin(base_url + relative, url))
            if parsed.scheme in ('mailto', 'tel', 'data'):
                continue
            if parsed.scheme not in ('http', 'https'):
                raise ValueError(f'Unsafe link in {relative}: {url}')
            if parsed.hostname != domain:
                external[url] += 1
                continue
            if parsed.fragment.startswith('m='):
                if int(parsed.fragment[2:]) not in id_set:
                    raise ValueError(f'Broken explorer ID: {url}')
            local_path = unquote(parsed.path.lstrip('/'))
            if local_path in checked_local_paths:
                internal += 1
                continue
            target = (site / local_path).resolve()
            if not target.is_relative_to(site):
                raise ValueError(f'Local link escapes site: {url}')
            if target.is_dir():
                target = target / 'index.html'
            if not target.is_file():
                raise ValueError(f'Broken local link from {relative}: {url}')
            checked_local_paths.add(local_path)
            internal += 1
    return {'verified': True, 'public_records': len(rows), 'individual_pages': len(actual_paths),
            'sitemap_urls': len(sitemap_urls), 'official_document_links': document_groups,
            'local_links_checked': internal, 'distinct_external_urls': len(external),
            'external_network_checked': False, 'file_sha256': inventory}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.site_dir)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'file_sha256'}, indent=2))


if __name__ == '__main__':
    main()
