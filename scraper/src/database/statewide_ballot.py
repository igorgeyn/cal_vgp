"""Reviewed statewide ballot assignments, independent of legacy canonical IDs.

This is a bounded offline correction path, not a discovery scraper. A review
pins the entire CA_SOS current/future cohort before loading. Existing content,
fingerprints, and enrichment remain owned by their original producers.
"""
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from bs4 import BeautifulSoup


QUALIFIED_URL = "https://www.sos.ca.gov/elections/ballot-measures/qualified-ballot-measures"
ELECTION = "2026-11-03"
YEAR = 2026
PRODUCTION_DB = Path(__file__).resolve().parents[2] / "data" / "ballot_measures.db"
APPROVAL = Path(__file__).resolve().parents[3] / "docs/plans/statewide_review_approval_20261003.json"
OWNERSHIP_FILE = ".statewide-working-copy.json"
TYPES = (
    "Initiative Constitutional Amendment and Statute", "Legislative Constitutional Amendment",
    "Initiative Constitutional Amendment", "Legislative Statute", "Initiative Statute",
)
# Sessions identified explicitly in the captured Proposition 4/5 law PDFs.
# The legacy link generator guesses from election year, which is wrong for SCA 1.
LEGISLATION_URLS = {
    (ELECTION, 4): "https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202520260SB42",
    (ELECTION, 5): "https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202320240SCA1",
}
SCHEMA = (
    """CREATE TABLE statewide_ballot_entries (
        measure_id INTEGER PRIMARY KEY REFERENCES measures(id), canonical_id TEXT NOT NULL,
        election_date TEXT NOT NULL, proposition_number INTEGER,
        ballot_status TEXT NOT NULL CHECK(ballot_status IN ('qualified', 'withdrawn')),
        official_title TEXT NOT NULL, official_description TEXT,
        status_reason TEXT, withdrawn_on TEXT, source_url TEXT NOT NULL,
        evidence_json TEXT NOT NULL, captured_at TEXT NOT NULL, review_sha256 TEXT NOT NULL,
        UNIQUE(election_date, proposition_number),
        CHECK((ballot_status = 'qualified' AND proposition_number > 0) OR
              (ballot_status = 'withdrawn' AND proposition_number IS NULL)))""",
    """CREATE TABLE statewide_ballot_reviews (
        review_sha256 TEXT PRIMARY KEY, review_json TEXT NOT NULL,
        before_json TEXT NOT NULL, after_json TEXT NOT NULL,
        entries_json TEXT NOT NULL, applied_at TEXT NOT NULL)""",
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":")).encode()).hexdigest()


def parse_qualified(html):
    """Only numbered HTML proposition links in the November 2026 section."""
    soup = BeautifulSoup(html, "html.parser")
    headings = [h for h in soup.find_all("h2") if h.get_text(" ", strip=True) ==
                "November 3, 2026, Statewide Ballot Measures"]
    if len(headings) != 1:
        raise ValueError("Expected exactly one November 3, 2026 heading")
    entries = []
    for node in headings[0].next_siblings:
        if getattr(node, "name", None) == "h2":
            break
        if not getattr(node, "find_all", None):
            continue
        text = node.get_text(" ", strip=True)
        match = re.match(r"Proposition (\d+)\b", text)
        if not match:
            # Withdrawal notes contain PDFs, not ballot assignments.
            if "voterguide.sos.ca.gov/propositions/" in str(node):
                raise ValueError("Unnumbered proposition link in election section")
            continue
        number = int(match[1])
        links = node.find_all("a", href=True)
        url = f"https://voterguide.sos.ca.gov/propositions/{number}/index.htm"
        if len(links) != 1 or links[0]["href"] != url:
            raise ValueError(f"Unexpected proposition {number} link")
        title = links[0].get_text(" ", strip=True)
        category = next((t for t in TYPES if title.lower().endswith(t.lower() + ".")), None)
        if not category:
            raise ValueError(f"Unrecognized official measure type: {title}")
        entries.append(dict(proposition_number=number, official_title=title,
                            source_url=url, category_type=category, election_date=ELECTION))
    numbers = [x["proposition_number"] for x in entries]
    if not numbers or len(numbers) != len(set(numbers)):
        raise ValueError("Empty or duplicate proposition slate")
    return sorted(entries, key=lambda x: x["proposition_number"])


def parse_proposition(html, entry):
    soup = BeautifulSoup(html, "html.parser")
    number = soup.select_one("#propNum")
    title = soup.select_one(".propName h2")
    banner = soup.select_one("#txtBnr")
    summary = soup.select_one("#mainCont p.noIndent")
    if (number is None or number.get_text(strip=True) != str(entry["proposition_number"])
            or title is None or title.get_text(" ", strip=True).casefold() != entry["official_title"].casefold()
            or banner is None or "November 3, 2026" not in banner.get_text(" ", strip=True)
            or summary is None):
        raise ValueError(f"Proposition page identity/content mismatch: {entry['proposition_number']}")
    # Only the official descriptive overview. Campaign arguments and endorsements
    # are not imported into neutral description or AI summary fields.
    description = summary.get_text(" ", strip=True).split("Fiscal Impact", 1)[0].strip()
    if len(description) < 30:
        raise ValueError("Official description missing")
    return description


def cohort(conn):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM measures WHERE data_source = 'CA_SOS' AND year >= ? ORDER BY id", (YEAR,))]


def hashes(rows):
    return {str(r["id"]): digest(r) for r in rows}


def table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def read_review(path):
    path = Path(path)
    review = json.loads(path.read_text(encoding="utf-8"))
    if review["schema_version"] != 2 or review["election_date"] != ELECTION:
        raise ValueError("Unsupported review version/election")
    sources = path.parent / "sources"
    artifacts = {x["file"]: x for x in review["artifacts"]}
    for name, artifact in artifacts.items():
        if Path(name).name != name:
            raise ValueError("Evidence names must be basenames")
        if hashlib.sha256((sources / name).read_bytes()).hexdigest() != artifact["sha256"]:
            raise ValueError(f"Evidence hash mismatch: {name}")
    qualified = (sources / "qualified.html").read_bytes()
    parsed = parse_qualified(qualified)
    expected = [{k: e[k] for k in parsed[0]} for e in review["entries"]]
    if parsed != expected:
        raise ValueError("Reviewed slate differs from captured official list")
    for entry in review["entries"]:
        file = f"prop-{entry['proposition_number']}.html"
        if artifacts[file]["url"] != entry["source_url"]:
            raise ValueError("Proposition evidence URL mismatch")
        if parse_proposition((sources / file).read_bytes(), entry) != entry["description"]:
            raise ValueError("Description differs from captured official page")
        if not entry["identity_evidence"]:
            raise ValueError("Identity evidence is required")
        if entry["existing_id"] is None and entry["canonical_id"] != f"PROP_{entry['proposition_number']}_{YEAR}":
            raise ValueError("Unexpected canonical ID for a new proposition")
    if artifacts["qualified.html"]["url"] != QUALIFIED_URL:
        raise ValueError("Qualified-list evidence URL mismatch")
    if "was removed from the November 3, 2026" not in BeautifulSoup(qualified, "html.parser").get_text(" ", strip=True):
        raise ValueError("Withdrawal evidence missing")
    if review["withdrawal"]["id"] != 1 or review["withdrawal"]["canonical_id"] != "ACA 13 (Ward) Voting thresholds. (Res. Ch. 176, 20":
        raise ValueError("Unexpected withdrawal identity")
    # The approval is repository-owned, never supplied alongside an arbitrary
    # input. A changed decision requires a new explicit review and pin. PDF
    # keyword presence cannot establish identity across neighboring sections.
    approved = json.loads(APPROVAL.read_text(encoding="utf-8"))
    crosswalk = [{k: e[k] for k in ("proposition_number", "existing_id", "canonical_id", "identity_evidence")}
                 for e in review["entries"]]
    if crosswalk != approved["identity_crosswalk"] or review["withdrawal"] != approved["withdrawal"]:
        raise ValueError("Identity crosswalk differs from approved review")
    if digest(review) != approved["review_sha256"]:
        raise ValueError("Review differs from separately approved digest")
    return review


def create_working_copy(baseline, work_dir):
    """Own a new directory and SQLite copy; never apply to a caller's input file.

    The marker protects against accidentally treating recovery inputs as work
    products. It is not a security boundary against a forged marker.
    """
    baseline, work_dir = Path(baseline).resolve(), Path(work_dir).resolve()
    if not baseline.is_file():
        raise ValueError("Baseline must be an existing file")
    work_dir.mkdir(parents=True, exist_ok=False)
    target = work_dir / "measures.db"
    with closing(sqlite3.connect(baseline.as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(target)) as destination:
            source.backup(destination)
    stat = target.stat()
    marker = {"database": str(target), "baseline": str(baseline),
              "device": stat.st_dev, "inode": stat.st_ino}
    (work_dir / OWNERSHIP_FILE).write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    return target


def require_owned_copy(db_path):
    marker_path = db_path.parent / OWNERSHIP_FILE
    if not marker_path.is_file():
        raise ValueError("Database must be an owned working copy, not a baseline or recovery input")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    stat = db_path.stat()
    if (str(db_path) != marker["database"] or db_path.name != "measures.db"
            or (stat.st_dev, stat.st_ino) != (marker["device"], marker["inode"])
            or stat.st_nlink != 1 or db_path.samefile(marker["baseline"])):
        raise ValueError("Working-copy ownership mismatch")


def reconcile(review_path, *, db_path, scratch_root, apply=False):
    """Check never opens writable SQLite. Apply is atomic and scratch-only.

    No production override is provided: Part 2 must separately review/promote
    an accepted candidate and its complete build-input bundle.
    """
    db_path, scratch_root = Path(db_path).resolve(), Path(scratch_root).resolve()
    if not db_path.is_file() or not db_path.is_relative_to(scratch_root):
        raise ValueError("Database must be an existing file beneath the explicit scratch root")
    if db_path == PRODUCTION_DB.resolve() or (PRODUCTION_DB.exists() and db_path.samefile(PRODUCTION_DB)):
        raise ValueError("Production database is forbidden")
    require_owned_copy(db_path)
    review = read_review(review_path)
    review_hash = digest(review)
    conn = sqlite3.connect(db_path.as_uri() + ("?mode=rw" if apply else "?mode=ro"), uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        before = cohort(conn)
        if table_exists(conn, "statewide_ballot_reviews"):
            prior = conn.execute("SELECT * FROM statewide_ballot_reviews WHERE review_sha256=?", (review_hash,)).fetchone()
            if prior:
                entries = [dict(r) for r in conn.execute("SELECT * FROM statewide_ballot_entries ORDER BY measure_id")]
                if hashes(before) != json.loads(prior["after_json"]) or entries != json.loads(prior["entries_json"]):
                    raise ValueError("Previously applied correction has drifted")
                return {"status": "unchanged", "review_sha256": review_hash, "writes": 0}
            raise ValueError("A different statewide review already exists; reconcile it explicitly")
        if hashes(before) != review["before_sha256"]:
            raise ValueError("Statewide preimages changed; review again before loading")
        by_id = {r["id"]: r for r in before}
        existing_ids = [e["existing_id"] for e in review["entries"] if e["existing_id"] is not None]
        if len(existing_ids) != len(set(existing_ids)):
            raise ValueError("An existing measure is assigned twice")
        active = {r["id"] for r in before if r["is_active"] and not r["is_duplicate"]}
        if active != set(existing_ids) | {review["withdrawal"]["id"]}:
            raise ValueError("Every old active statewide entry needs a disposition")
        if {str(r["id"]) for r in before} != set(review["dispositions"]):
            raise ValueError("Missing disposition for inactive/duplicate record")
        for entry in review["entries"]:
            row = by_id.get(entry["existing_id"])
            if entry["existing_id"] is not None:
                if row is None or row["measure_id"] != entry["canonical_id"] or row["county"] != "Statewide":
                    raise ValueError("Canonical identity mismatch")
            elif conn.execute("SELECT 1 FROM measures WHERE measure_id=?", (entry["canonical_id"],)).fetchone():
                raise ValueError("New canonical identity already exists")
        report = {"status": "applied" if apply else "checked", "review_sha256": review_hash,
                  "matched": len(existing_ids), "inserted": len(review["entries"]) - len(existing_ids),
                  "withdrawn": 1, "writes": 0}
        if not apply:
            return report
        for statement in SCHEMA:
            conn.execute(statement)
        stamp = review["reviewed_at"]
        for entry in review["entries"]:
            row_id = entry["existing_id"]
            if row_id is None:
                from .models import BallotMeasure
                row = BallotMeasure(measure_id=entry["canonical_id"], year=YEAR, county="Statewide",
                                    title=entry["official_title"], description=entry["description"],
                                    category_type=entry["category_type"], data_source="CA_SOS",
                                    source_url=entry["source_url"], election_date=ELECTION,
                                    election_type="general", created_at=stamp, updated_at=stamp,
                                    last_seen_at=stamp).to_dict()
                row.pop("id")
                columns = list(row)
                cursor = conn.execute(f"INSERT INTO measures ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", list(row.values()))
                row_id = cursor.lastrowid
            else:
                conn.execute("""UPDATE measures SET election_date=?, election_type='general', election_type_imputed=0,
                                updated_at=?, update_count=COALESCE(update_count,0)+1 WHERE id=?""", (ELECTION, stamp, row_id))
            conn.execute("INSERT INTO statewide_ballot_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                row_id, entry["canonical_id"], ELECTION, entry["proposition_number"], "qualified",
                entry["official_title"], entry["description"], None, None,
                entry["source_url"], json.dumps(entry["identity_evidence"]),
                review["captured_at"], review_hash))
        withdrawal = review["withdrawal"]
        # is_active denotes curated archive visibility, not ballot eligibility.
        conn.execute("UPDATE measures SET updated_at=?, update_count=COALESCE(update_count,0)+1 WHERE id=?", (stamp, withdrawal["id"]))
        conn.execute("INSERT INTO statewide_ballot_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            withdrawal["id"], withdrawal["canonical_id"], ELECTION, None, "withdrawn",
            by_id[withdrawal["id"]]["title"], None, withdrawal["status_reason"], withdrawal["withdrawn_on"],
            QUALIFIED_URL, json.dumps(withdrawal["identity_evidence"]),
            review["captured_at"], review_hash))
        after = cohort(conn)
        entries = [dict(r) for r in conn.execute("SELECT * FROM statewide_ballot_entries ORDER BY measure_id")]
        conn.execute("INSERT INTO statewide_ballot_reviews VALUES (?,?,?,?,?,?)", (
            review_hash, json.dumps(review), json.dumps(before), json.dumps(hashes(after)), json.dumps(entries), stamp))
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Foreign key check failed")
        report["writes"] = conn.total_changes
        report["assignments"] = [{k: r[k] for k in ("measure_id", "canonical_id", "proposition_number", "ballot_status")} for r in entries]
        conn.commit()
        return report
    finally:
        conn.rollback()
        conn.close()


def attach_statewide_ballot_fields(conn, measures):
    """Common public projection for CLI, model builds, and later static pages."""
    if not table_exists(conn, "statewide_ballot_entries"):
        return measures
    entries = {r["measure_id"]: dict(r) for r in conn.execute("SELECT * FROM statewide_ballot_entries")}
    canonical = {(r["canonical_id"], int(r["election_date"][:4])): r["measure_id"] for r in entries.values()}
    result = []
    for measure in measures:
        row_id = measure.get("id")
        year = str(measure.get("year") or "")
        expected = canonical.get((measure.get("measure_id"), int(year) if year.isdigit() else None))
        entry = entries.get(row_id)
        if (expected is not None and (type(row_id) is not int or row_id != expected)) or (entry and expected != row_id):
            raise ValueError("Statewide ballot assignment requires matching integer and canonical IDs")
        if entry:
            if (measure.get("data_source") or measure.get("source")) != "CA_SOS" or measure.get("county") != "Statewide":
                raise ValueError("Statewide ballot assignment requires CA_SOS statewide ownership")
            measure = {**measure, **{k: entry[k] for k in (
                "proposition_number", "ballot_status", "official_title", "official_description",
                "status_reason", "withdrawn_on", "source_url")}}
            # A withdrawn row has no current election assignment. Keep its raw
            # date, and label the removed slate separately.
            if entry["ballot_status"] == "qualified":
                measure["election_date"] = entry["election_date"]
            else:
                measure["withdrawn_from_election"] = entry["election_date"]
            measure["official_source_captured_at"] = entry["captured_at"]
            if "external_links" in measure:
                links = []
                for link in measure["external_links"]:
                    if entry["ballot_status"] == "withdrawn":
                        continue
                    if link.get("source") == "CA SOS Eligible Measures":
                        continue  # qualified pages supersede eligible-initiative listings
                    if link.get("source") == "Official Voter Guide":
                        link = {**link, "url": entry["source_url"], "confidence": "high"}
                    legislation = LEGISLATION_URLS.get((entry["election_date"], entry["proposition_number"]))
                    if legislation and link.get("source", "").startswith("CA Legislature ("):
                        link = {**link, "url": legislation}
                    links.append(link)
                if entry["ballot_status"] == "withdrawn":
                    links = [{"source": "CA SOS withdrawal record", "url": QUALIFIED_URL,
                              "confidence": "high"}]
                measure["external_links"] = links
        result.append(measure)
    return result
