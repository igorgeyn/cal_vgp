#!/usr/bin/env python3
"""Generate static per-measure stub pages + sitemap.xml for SEO.

Reads measures-data.json (written by the site generator) and emits:
  measures/<id>.html  - lightweight, indexable content page per measure
  sitemap.xml         - homepage + all measure pages

Design notes:
- These are REAL content pages, not redirects. A meta-refresh or instant JS
  redirect would make search engines index the redirect target (the SPA
  homepage) instead of the 12k measure pages, defeating the purpose. Each
  page shows the measure's core facts and links into the explorer at /#m=<id>.
- Page ids are the app's stable per-measure `id` (same key the #m= permalinks
  use). If the database is ever rebuilt from scratch and ids reassigned,
  regenerate these pages in the same run (old URLs would otherwise 404).

Run after generating a new candidate measures-data.json:
  python build_measure_pages.py --site-dir <new-candidate-site>
Existing measure pages or sitemap are never overwritten.
"""

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

BASE_URL = "https://cal-vgp.igorgeyn.com"
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'scraper'))
from src.website.statewide_content import render_sections as render_statewide_sections, STYLE as STATEWIDE_STYLE


def esc(s):
    return html.escape(str(s), quote=True) if s is not None else ""


def safe_http_url(value):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value) or "\\" in value:
        return False
    try:
        parsed = urlsplit(value)
        return bool(parsed.scheme in {"http", "https"} and parsed.hostname
                    and not parsed.username and not parsed.password)
    except ValueError:
        return False


def official_documents_html(measure):
    """Render the already-grouped public model once per document, not per role."""
    documents = measure.get("official_documents") or []
    if not documents:
        return ""
    items = []
    identities = set()
    for document in documents:
        url = document.get("source_url")
        if not safe_http_url(url):
            raise ValueError(f"Unsafe official document URL for measure {measure['id']}")
        identity = (url, document.get("sha256"))
        if identity in identities:
            raise ValueError(f"Duplicate public document group for measure {measure['id']}")
        identities.add(identity)
        labels = document.get("labels") or document.get("roles") or ["Official document"]
        label = " · ".join(labels)
        captured = re.match(r"\d{4}-\d{2}-\d{2}", document.get("captured_at") or "")
        vintage = f"Last captured {captured[0]}" if captured else "Capture date unavailable"
        kind = "PDF" if (document.get("content_type") or "").split(";")[0] == "application/pdf" else "Document"
        review_note = (f'<p class="document-meta">{esc(document["role_review_note"])}</p>'
                       if document.get("role_review_note") else "")
        items.append(
            f'<li><a href="{esc(url)}" target="_blank" rel="noopener noreferrer">'
            f'<span>{esc(label)}</span><span class="document-meta">'
            f'{kind} · {esc(vintage)} · Opens in a new tab</span></a>{review_note}</li>'
        )
    return (
        '<section class="official-documents" aria-labelledby="official-documents-title">'
        '<h2 id="official-documents-title">Official documents</h2>'
        '<p>Documents are hosted by the county. Capture dates describe when '
        'CalBallot retrieved the files; the county may update its files.</p>'
        '<ul>' + "".join(items) + '</ul></section>'
    )


def truncate(text, limit=155):
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def jurisdiction_label(m):
    county = m.get("county") or ""
    juris = m.get("jurisdiction")
    if county == "Statewide":
        return "California Statewide"
    parts = []
    if juris:
        parts.append(str(juris))
    if county:
        parts.append(f"{county} County")
    return ", ".join(parts) or "California"


def outcome(m):
    """(badge_text, badge_color, sentence) for the measure's result."""
    if m.get("ballot_status") == "withdrawn":
        return ("Withdrawn", "#6B5F48", m["status_reason"])
    passed = m.get("passed")
    pct = m.get("percent_yes")
    pct_txt = f"{pct:.1f}% yes" if isinstance(pct, (int, float)) else None
    if passed == 1:
        return ("Passed", "#3A8C28", f"Passed{' with ' + pct_txt if pct_txt else ''}.")
    if passed == 0:
        return ("Failed", "#C0392B", f"Failed{' with ' + pct_txt if pct_txt else ''}.")
    if m.get("year") and int(m["year"]) >= date.today().year:
        return ("Upcoming", "#C9A23C", "Upcoming — not yet voted on.")
    return ("Result unknown", "#999080", "Result not recorded in our sources.")


def meta_description(m, outcome_sentence):
    for key in ("status_reason", "official_description", "summary_text", "ballot_question", "description"):
        if m.get(key):
            return truncate(m[key])
    return truncate(
        f"{jurisdiction_label(m)} ballot measure from {m.get('year')}: "
        f"{m.get('title')} {outcome_sentence}"
    )


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title_tag}</title>
    <meta name="description" content="{meta_desc}">
    <link rel="canonical" href="{canonical}">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="icon" href="/favicon.png" type="image/png" sizes="32x32">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <meta property="og:site_name" content="CalBallot">
    <meta property="og:type" content="article">
    <meta property="og:title" content="{og_title}">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="{base_url}/apple-touch-icon.png">
    <meta name="twitter:card" content="summary">
    <style>
        body {{ margin: 0; font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
               background: #F7F5F0; color: #1A1714; line-height: 1.55; }}
        .wrap {{ max-width: 44rem; margin: 0 auto; padding: 1.25rem 1.25rem 3rem; }}
        .site {{ display: flex; align-items: center; gap: 0.5rem; text-decoration: none; color: #1A1714;
                 font-weight: 800; margin-bottom: 1.75rem; }}
        .site .mark {{ background: #C9A23C; color: #111; border-radius: 6px; padding: 0.15rem 0.4rem;
                       font-size: 0.85rem; }}
        h1 {{ font-size: 1.45rem; line-height: 1.3; margin: 0 0 0.75rem; }}
        .meta {{ color: #6B5F48; font-size: 0.95rem; margin-bottom: 0.75rem; }}
        .badge {{ display: inline-block; color: #fff; border-radius: 999px; padding: 0.15rem 0.7rem;
                  font-size: 0.85rem; font-weight: 600; margin-right: 0.5rem; }}
        .votes {{ margin: 1rem 0; font-size: 0.95rem; }}
        .summary {{ background: #EEEADD; border: 1px solid #E0DAC8; border-radius: 8px;
                    padding: 1rem 1.25rem; margin: 1.25rem 0; }}
        .summary .label {{ font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em;
                           text-transform: uppercase; color: #6B5F48; margin-bottom: 0.4rem; }}
        .cta {{ display: inline-block; background: #C9A23C; color: #111; font-weight: 700;
                text-decoration: none; border-radius: 8px; padding: 0.65rem 1.2rem; margin-top: 1rem; }}
        .src {{ font-size: 0.9rem; overflow-wrap: anywhere; }}
        .official-documents {{ margin: 1.5rem 0; }}
        .official-documents h2 {{ font-size: 1.15rem; }}
        .official-documents p {{ font-size: 0.9rem; color: #6B5F48; }}
        .official-documents ul {{ padding: 0; list-style: none; }}
        .official-documents li {{ margin: 0.6rem 0; }}
        .official-documents a {{ display: block; padding: 0.8rem 1rem;
            border: 1px solid #E0DAC8; border-radius: 8px; overflow-wrap: anywhere; color: #6B5F48; }}
        .official-documents a:focus-visible {{ outline: 3px solid #6B5F48; outline-offset: 2px; }}
        .document-meta {{ display: block; font-size: 0.8rem; color: #6B5F48; margin-top: 0.3rem; }}
        a {{ color: #A8841E; }}
        footer {{ margin-top: 2.5rem; font-size: 0.85rem; color: #999080; }}
    {statewide_style}</style>
</head>
<body>
    <div class="wrap">
        <a class="site" href="/"><span class="mark">CB</span> CalBallot</a>
        <h1>{h1}</h1>
        <p class="meta">{juris} &bull; {year}{mtype}</p>
        <p><span class="badge" style="background: {badge_color};">{badge_text}</span></p>
        {votes_html}
        {summary_html}
        {source_html}
        {statewide_details}{documents_html}
        <a class="cta" href="/#m={mid}">Open in the CalBallot explorer &rarr;</a>
        <footer>
            <p>CalBallot &mdash; a free explorer for 12,000+ California ballot measures, 1911 to present.
               Data sources: CA Secretary of State, NCSL, ICPSR, CEDA.</p>
        </footer>
    </div>
</body>
</html>
"""


def build_page(m):
    mid = m["id"]
    # `summary_title` is a truncated first sentence of the summary, NOT a real
    # title — always prefer the actual `title` field.
    title = m.get("official_title") or m.get("title") or m.get("summary_title") or f"Ballot measure {mid}"
    if m.get("proposition_number"):
        title = f"Proposition {m['proposition_number']}: {title}"
    juris = jurisdiction_label(m)
    year = m.get("year") or ""
    badge_text, badge_color, outcome_sentence = outcome(m)
    desc = meta_description(m, outcome_sentence)
    mtype = f" &bull; {esc(m['measure_type'])}" if m.get("measure_type") else ""

    votes_html = ""
    py, pn = m.get("percent_yes"), m.get("percent_no")
    if isinstance(py, (int, float)):
        tv = m.get("total_votes")
        tv_txt = f" ({tv:,.0f} votes cast)" if isinstance(tv, (int, float)) and tv > 0 else ""
        no_txt = f", {pn:.1f}% no" if isinstance(pn, (int, float)) else ""
        votes_html = f'<p class="votes"><strong>Result:</strong> {py:.1f}% yes{no_txt}{tv_txt}</p>'

    summary_html = ""
    if m.get("status_reason") or m.get("official_description"):
        label = "CA SOS withdrawal record" if m.get("status_reason") else "Official description - California Secretary of State"
        summary_html = (
            f'<div class="summary"><div class="label">{esc(label)}</div>'
            f"<p>{esc(m.get('status_reason') or m['official_description'])}</p></div>"
        )
    elif m.get("summary_text"):
        summary_html = (
            '<div class="summary"><div class="label">AI-generated plain-language summary</div>'
            f"<p>{esc(truncate(m['summary_text'], 600))}</p></div>"
        )

    source_html = ""
    if safe_http_url(m.get("source_url")):
        source_html = (
            f'<p class="src">Official source: <a href="{esc(m["source_url"])}" '
            f'rel="noopener">{esc(truncate(m["source_url"], 80))}</a></p>'
        )
        if m.get("official_source_captured_at"):
            source_html += f'<p class="src">Source captured {esc(m["official_source_captured_at"][:10])}.</p>'

    title_tag = f"{title} — {juris}, {year} | CalBallot"
    guide = m.get('statewide_guide')
    statewide_details = ''
    if guide:
        sections = render_statewide_sections(guide)
        statewide_details = sections['main'] + '<h2>Research</h2>' + sections['research'] + '<h2>Campaign finance</h2>' + sections['finance']
    return PAGE.format(
        title_tag=esc(truncate(title_tag, 110)),
        meta_desc=esc(desc),
        canonical=f"{BASE_URL}/measures/{mid}.html",
        og_title=esc(truncate(f"{title} ({juris}, {year})", 90)),
        base_url=BASE_URL,
        h1=esc(title),
        juris=esc(juris),
        year=esc(year),
        mtype=mtype,
        badge_text=badge_text,
        badge_color=badge_color,
        votes_html=votes_html,
        summary_html=summary_html,
        source_html=source_html,
        documents_html=official_documents_html(m),
        statewide_style=STATEWIDE_STYLE if guide else '',
        statewide_details=statewide_details,
        mid=mid,
    )


def build_site_pages(site_dir):
    """Write a new page set; never delete a previous candidate or public tree."""
    site_dir = Path(site_dir).resolve()
    out_dir = site_dir / "measures"
    with open(site_dir / "measures-data.json", encoding="utf-8") as f:
        measures = json.load(f)

    ids = [m["id"] for m in measures]
    if any(type(mid) is not int or mid < 1 for mid in ids) or len(ids) != len(set(ids)):
        raise ValueError("Measure IDs must be unique positive integers")

    if out_dir.is_symlink() or out_dir.resolve().parent != site_dir:
        raise ValueError("Measure output must be inside the selected site directory")
    if out_dir.exists() or (site_dir / 'sitemap.xml').exists():
        raise FileExistsError("Page set already exists; choose a fresh candidate directory")
    # Validate documents before writing any page; a malformed URL must not leave
    # a plausible-looking partial bundle.
    for measure in measures:
        official_documents_html(measure)
        if measure.get('statewide_guide'):
            render_statewide_sections(measure['statewide_guide'])
    out_dir.mkdir()

    for m in measures:
        (out_dir / f"{m['id']}.html").write_text(build_page(m), encoding="utf-8")

    today = date.today().isoformat()
    urls = [
        f"  <url><loc>{BASE_URL}/</loc><lastmod>{today}</lastmod><priority>1.0</priority></url>",
        f"  <url><loc>{BASE_URL}/use-calballot/</loc><lastmod>{today}</lastmod><priority>0.8</priority></url>",
    ]
    urls += [
        f"  <url><loc>{BASE_URL}/measures/{m['id']}.html</loc><priority>0.6</priority></url>"
        for m in measures
    ]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    (site_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    print(f"Wrote {len(measures)} pages to {out_dir}/ and sitemap.xml ({len(urls)} URLs)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, required=True,
                        help="Explicit candidate directory with JSON but no existing pages/sitemap")
    build_site_pages(parser.parse_args().site_dir)


if __name__ == "__main__":
    main()
