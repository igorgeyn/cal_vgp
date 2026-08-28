"""Audience-page content, claims, and lightweight-output contracts."""

from __future__ import annotations

import re
from pathlib import Path

from src.database.operations import Database
from src.website.generator import CALIFORNIA_COUNTY_COUNT, WebsiteGenerator


def _database_with_known_coverage(path: Path) -> Database:
    database = Database(path)
    connection = database.connect()
    connection.executemany(
        """
        INSERT INTO measures (fingerprint, year, county, data_source, title)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            ("statewide-1911", 1911, "Statewide", "CA_SOS", "Historic proposition"),
            ("sb-a", 2026, "San Bernardino", "SB_County_Registrar", "Measure A"),
            ("sb-b", 2026, "San Bernardino", "SB_County_Registrar", "Measure B"),
            ("la-c", 2026, "Los Angeles", "LA_County_Registrar", "Measure C"),
            ("old-oc", 2025, "Orange", "OC_County_Registrar", "Older measure"),
        ],
    )
    connection.commit()
    return database


def test_statistics_compute_current_registrar_coverage(tmp_path: Path):
    database = _database_with_known_coverage(tmp_path / "coverage.db")

    stats = database.get_statistics()

    assert stats["total_measures"] == 5
    assert stats["year_min"] == 1911
    assert stats["year_max"] == 2026
    assert stats["counties"] == 3
    assert stats["current_registrar_year"] == 2026
    assert stats["current_registrar_counties"] == 2
    assert stats["current_registrar_measures"] == 3
    database.close()


def test_page_numbers_match_the_database_used_for_generation(tmp_path: Path):
    database = _database_with_known_coverage(tmp_path / "claims.db")
    stats = database.get_statistics()
    generator = WebsiteGenerator(database=database, output_path=tmp_path / "unused.html")

    html = generator._generate_use_calballot_html(generator._sanitize_stats(stats))

    expected = {
        "total_measures": f"{stats['total_measures']:,}",
        "year_min": str(stats["year_min"]),
        "local_measures": f"{stats['local_count']:,}",
        "current_registrar_counties": str(stats["current_registrar_counties"]),
        "california_counties": str(CALIFORNIA_COUNTY_COUNT),
        "current_registrar_measures": str(stats["current_registrar_measures"]),
        "current_registrar_year": str(stats["current_registrar_year"]),
    }
    rendered = dict(re.findall(r'data-stat="([^"]+)">([^<]+)<', html))
    assert rendered == expected
    database.close()


def test_page_has_required_audiences_metadata_and_coverage_copy(tmp_path: Path):
    database = _database_with_known_coverage(tmp_path / "content.db")
    generator = WebsiteGenerator(database=database, output_path=tmp_path / "unused.html")
    html = generator._generate_use_calballot_html(
        generator._sanitize_stats(database.get_statistics())
    )
    normalized_html = re.sub(r"\s+", " ", html)

    assert html.count("<h1") == 1
    for section_id in (
        "audiences",
        "journalists",
        "researchers",
        "civic-organizations",
        "public-affairs",
    ):
        assert f'id="{section_id}"' in html
    assert '<link rel="canonical" href="https://cal-vgp.igorgeyn.com/use-calballot/">' in html
    assert '<meta property="og:url" content="https://cal-vgp.igorgeyn.com/use-calballot/">' in html
    assert "The historical archive contains thousands of local measures" in normalized_html
    assert "Current-election registrar coverage is narrower" in normalized_html
    assert "CalBallot is not an address-based ballot finder." in normalized_html
    assert "your complete ballot" not in html.lower()
    assert "?view=" not in html
    database.close()


def test_page_is_lightweight_and_all_internal_anchors_resolve(tmp_path: Path):
    database = _database_with_known_coverage(tmp_path / "lightweight.db")
    generator = WebsiteGenerator(database=database, output_path=tmp_path / "unused.html")
    html = generator._generate_use_calballot_html(
        generator._sanitize_stats(database.get_statistics())
    )
    lowered = html.lower()

    assert "fetch('measures-data.json')" not in lowered
    assert "duckdb" not in lowered
    assert "chart.js" not in lowered
    assert "leaflet" not in lowered
    assert "<script" not in lowered
    assert "http://" not in lowered

    ids = set(re.findall(r'\bid="([^"]+)"', html))
    anchors = set(re.findall(r'href="#([^"]+)"', html))
    assert anchors <= ids
    database.close()


def test_about_modal_promotes_use_page_with_accessible_cta(tmp_path: Path, monkeypatch):
    database = Database(tmp_path / "about-modal.db")
    generator = WebsiteGenerator(database=database, output_path=tmp_path / "unused.html")
    monkeypatch.setattr(generator, "_load_finance_data", lambda: {})
    monkeypatch.setattr(generator, "_load_insights_data", lambda: {})
    monkeypatch.setattr(generator, "_generate_quiz_questions", lambda measures, stats: [])

    html = generator._generate_html([], {}, [], {})
    about_html = html.split('id="aboutModal"', 1)[1].split(
        "<!-- AI Chat Interface -->", 1
    )[0]

    section_order = [
        about_html.index("CalBallot is a tool for exploring"),
        about_html.index("Who uses CalBallot?"),
        about_html.index("<h3>Background</h3>"),
        about_html.index("<h3>Features</h3>"),
        about_html.index("<h3>Data Pipeline</h3>"),
    ]
    assert section_order == sorted(section_order)
    assert (
        '<a class="about-use-cta" href="/use-calballot/">'
        "See how each group can use CalBallot &rarr;</a>"
    ) in about_html
    assert "outline: 3px solid var(--text-primary);" in html
    assert "border: 1px solid var(--primary-dark);" in html
    database.close()


def test_sitemap_source_includes_use_calballot_route():
    root = Path(__file__).resolve().parents[2]
    source = (root / "build_measure_pages.py").read_text(encoding="utf-8")
    assert 'f"  <url><loc>{BASE_URL}/use-calballot/</loc>' in source
