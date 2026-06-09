"""
Reconnaissance probe: fetch a URL with a polite User-Agent, save the
raw response + metadata to local FS for inspection. Pre-Phase-0.5
tool; intentionally disposable.

Will be subsumed by the real scraper framework in Phase 0.5
(RawArtifactStore + CountyRegistrarScraper). The probe script is for
the reconnaissance phase only — find URL patterns, detect blocks,
identify JS dependencies, save sample artifacts.

Usage:
    python scraper/scripts/recon/probe.py \\
        --county la \\
        --tag june-2026-text-results \\
        --url https://results.lavote.gov/text-results/4338

Output:
    scraper/data/registrar_recon/{county}/{tag}/
        page.{html,pdf,json,...}    # raw response body
        probe.json                  # metadata: status, headers,
                                    # sha256, timestamps, etc.

Exits 0 on 2xx/3xx, 1 on 4xx/5xx, 2 on fetch error (timeout, DNS,
connection refused).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

DEFAULT_UA = (
    "cal-vgp-registrar-recon/0.1 "
    "(+https://github.com/igorgeyn/cal_vgp; "
    "contact: igorgeyn@gmail.com)"
)

DEFAULT_OUT_DIR = Path("scraper/data/registrar_recon")

# Content-type → file extension. Falls back to "bin" for unknowns.
EXT_MAP = {
    "text/html": "html",
    "application/xhtml+xml": "html",
    "application/pdf": "pdf",
    "application/json": "json",
    "text/plain": "txt",
    "application/xml": "xml",
    "text/xml": "xml",
    "text/css": "css",
    "application/javascript": "js",
    "text/javascript": "js",
}


def probe(
    url: str,
    county: str,
    tag: str,
    *,
    user_agent: str = DEFAULT_UA,
    timeout: int = 30,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict:
    """Fetch url, save artifact + metadata. Returns the metadata dict."""
    started = datetime.now(timezone.utc)
    headers = {"User-Agent": user_agent}

    resp = requests.get(
        url, headers=headers, timeout=timeout, allow_redirects=True
    )
    fetched_at = datetime.now(timezone.utc)

    body = resp.content
    sha256 = hashlib.sha256(body).hexdigest()
    ct = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    ext = EXT_MAP.get(ct, "bin")

    snap_dir = out_dir / county / tag
    snap_dir.mkdir(parents=True, exist_ok=True)

    artifact_filename = f"page.{ext}"
    (snap_dir / artifact_filename).write_bytes(body)

    metadata = {
        "url": url,
        "final_url": resp.url,
        "http_status": resp.status_code,
        "content_type": ct,
        "content_length": len(body),
        "sha256": sha256,
        "started_at": started.isoformat(),
        "fetched_at": fetched_at.isoformat(),
        "duration_seconds": (fetched_at - started).total_seconds(),
        "user_agent": user_agent,
        "response_headers": dict(resp.headers),
        "artifact_filename": artifact_filename,
        "county": county,
        "tag": tag,
    }

    (snap_dir / "probe.json").write_text(json.dumps(metadata, indent=2))
    return metadata


def main() -> int:
    p = argparse.ArgumentParser(description="Reconnaissance probe.")
    p.add_argument("--url", required=True, help="URL to fetch")
    p.add_argument(
        "--county",
        required=True,
        help="short county slug, e.g. la, sd, oc, riverside, sb",
    )
    p.add_argument(
        "--tag",
        required=True,
        help="short label for this snapshot (e.g. 'home-2026-06-08')",
    )
    p.add_argument("--user-agent", default=DEFAULT_UA)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = p.parse_args()

    try:
        meta = probe(
            args.url,
            args.county,
            args.tag,
            user_agent=args.user_agent,
            timeout=args.timeout,
            out_dir=args.out_dir,
        )
    except requests.RequestException as e:
        print(f"FETCH ERROR: {e}", file=sys.stderr)
        return 2

    # Concise summary
    print(f"[{meta['http_status']}] {meta['url']}")
    if meta["url"] != meta["final_url"]:
        print(f"  redirected to: {meta['final_url']}")
    print(f"  content-type:   {meta['content_type'] or '(none)'}")
    print(f"  size:           {meta['content_length']:,} bytes")
    print(f"  sha256:         {meta['sha256'][:16]}...")
    print(f"  saved to:       {args.out_dir}/{args.county}/{args.tag}/")
    return 0 if 200 <= meta["http_status"] < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
