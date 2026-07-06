"""
NoOpCountyScraper — proves the pipeline wiring without touching the
network.

Pretends to scrape a fake county: writes one HTML artifact, one PDF
artifact, and the snapshot manifest, then returns a success result.
Used by tests and by the first CI run to validate the full
runner → scraper → store → manifest path before any real county
scraper exists.

Not registered as a real county; the runner includes it only when
explicitly asked (e.g. --counties=noop or the wiring smoke test).
"""
from __future__ import annotations

from .base import CountyRegistrarScraper, ScrapeResult
from .storage import ArtifactMetadata

FAKE_ELECTION_DATE = "2026-01-01"

FAKE_HTML = b"""<html>
  <head><title>Noop County Registrar of Voters</title></head>
  <body>
    <h1>Measures on the 2026-01-01 ballot</h1>
    <table>
      <tr><th>Letter</th><th>Jurisdiction</th><th>Description</th></tr>
      <tr><td>Z</td><td>City of Nowhere</td><td>A measure about nothing.</td></tr>
    </table>
  </body>
</html>
"""

# Minimal syntactically-plausible PDF; parsers never read it, but it
# exercises the binary-artifact path end to end.
FAKE_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R >>\n"
    b"%%EOF\n"
)


class NoOpCountyScraper(CountyRegistrarScraper):
    county = "noop"

    def scrape(self) -> ScrapeResult:
        writer = self.open_snapshot(FAKE_ELECTION_DATE)
        writer.save_bytes(
            "page.html",
            FAKE_HTML,
            ArtifactMetadata(
                source_url="noop://registrar/measures/page.html",
                content_type="text/html",
                http_status=200,
            ),
        )
        writer.save_bytes(
            "analysis.pdf",
            FAKE_PDF,
            ArtifactMetadata(
                source_url="noop://registrar/measures/analysis.pdf",
                content_type="application/pdf",
                http_status=200,
            ),
        )
        writer.finalize(extra={"source_base_url": "noop://registrar"})
        return ScrapeResult(county=self.county, snapshots=(writer.summary(),))
