"""
Rebuild the statewide-proposition finance database from the cleaned CalAccess
source CSV, keyed by year-scoped finance_campaign_id (e.g. PROP_16_2020).

Step 3 of the finance rebuild. Reads `ballot_measure_receipts_clean.csv` and
the Step 2 crosswalk at `finance_crosswalk.csv`, validates each source row at
two levels (campaign-level + transaction-date hygiene), and writes a fresh
SQLite DB with five tables:

    finance_campaign          — the crosswalk indexed in SQLite (PK)
    finance_summary           — per (campaign, stance): receipts, committees, HHI
    finance_top_donors        — per (campaign, stance, donor): canonicalized
    finance_timeline_weekly   — per (campaign, stance, week_start)
    finance_row_quarantine    — rejected source rows with reason code

Row-level acceptance gate (Codex review 2026-05-04): a kept row must have a
real numeric prop_num, a populated year, a parseable transaction date >=
1995-01-01, a campaign in the crosswalk, AND |txn_year - election_year| <= 1.
Anything else is quarantined for audit.

Output: scraper/data/finance/finance_statewide_v2.db (parallel to the old DB
until Step 5 swaps consumers over).

This script is idempotent: rerun any time without side effects, just rewrites
the v2 DB.
"""
from __future__ import annotations

import csv
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_CSV = REPO_ROOT / "scraper" / "data" / "finance" / "calaccess_raw" / "ballot_measure_receipts_clean.csv"
CROSSWALK_CSV = REPO_ROOT / "scraper" / "data" / "finance" / "finance_crosswalk.csv"
OUTPUT_DB = REPO_ROOT / "scraper" / "data" / "finance" / "finance_statewide_v2.db"

PROP_NUM_RE = re.compile(r"^(\d+)([A-Z])?$")


# Donor alias normalization. Hand-curated for known high-value duplicates only,
# per Codex's note (don't use prefix heuristics; they false-positive on
# "California Association of Realtors" vs "...of Professional Scientists").
# Each entry is (regex_pattern, canonical_name). First match wins. The donor
# name is pre-normalized (uppercased, trailing punctuation stripped, whitespace
# collapsed) before matching, so patterns don't need case- or punctuation-
# tolerance noise.
DONOR_ALIAS_PATTERNS: list[tuple[re.Pattern, str]] = [
    # California Teachers Association — 13 variants observed totaling $505M.
    # Match anything that's clearly the CTA Issues PAC (covers "California",
    # "CA", "Calif", with/without dashes/slashes, "PAC"/"Issues"/"Issue"/"Issues PAC").
    (re.compile(r"^(CALIFORNIA|CA|CALIF)\s+TEACHERS ASSOCIATION([\s\-/]+ISSUES?( PAC)?(\s*\(CTA\))?)?$"),
     "California Teachers Association Issues PAC"),
    # Bare "California Teachers Association" (no Issues PAC suffix) is the
    # parent org — collapse only when there's no qualifier afterward.
    (re.compile(r"^CALIFORNIA TEACHERS ASSOCIATION$"),
     "California Teachers Association"),

    # AFSCME — distinct sub-entities preserved, but spelling variants collapsed.
    (re.compile(r"AMERICAN FEDERATION OF STATE,?\s*COUNTY,?\s*(AND|&)\s*MUNICIPAL EMPLOYEES.*AFL-CIO.*\(MPO\)"),
     "AFSCME AFL-CIO (MPO)"),
    (re.compile(r"AMERICAN FEDERATION OF STATE,?\s*COUNTY,?\s*(AND|&)\s*MUNICIPAL EMPLOYEES.*CALIFORNIA.*ISSUES"),
     "AFSCME California People Issues PAC"),
    (re.compile(r"AMERICAN FEDERATION OF STATE,?\s*COUNTY,?\s*(AND|&)\s*MUNICIPAL EMPLOYEES,?\s*AFL-CIO$"),
     "AFSCME AFL-CIO"),

    # AFT — 3 entities preserved.
    (re.compile(r"AMERICAN FEDERATION OF TEACHERS,?\s*AFL-CIO.*COMMITTEE ON POLITICAL EDUCATION"),
     "AFT AFL-CIO COPE"),
    (re.compile(r"AMERICAN FEDERATION OF TEACHERS,?\s*AFL-CIO$"),
     "AFT AFL-CIO"),
    (re.compile(r"^AMERICAN FEDERATION OF TEACHERS$"),
     "American Federation of Teachers"),

    # R.J. Reynolds family — multiple affiliate-naming variants. The bare RJR
    # corporate filer is the dominant entity; collapse spelling/affiliate
    # phrasing onto it. Santa Fe Natural Tobacco is a meaningfully distinct
    # subsidiary even though it's an RJR affiliate.
    (re.compile(r"^R\.?J\.?\s*REYNOLDS TOBACCO COMPANY( AND ITS AFFILIATES)?(\s*\(.+\))?$"),
     "R.J. Reynolds Tobacco Company"),
    (re.compile(r"^RJ REYNOLDS$"),
     "R.J. Reynolds Tobacco Company"),
    (re.compile(r"^AMERICAN SNUFF COMPANY.*R\.?J\.?\s*REYNOLDS TOBACCO COMPANY"),
     "American Snuff Co (R.J. Reynolds affiliate)"),
    (re.compile(r"^SANTA FE NATURAL TOBACCO COMPANY.*R\.?J\.?\s*REYNOLDS"),
     "Santa Fe Natural Tobacco (R.J. Reynolds affiliate)"),

    # San Manuel — case-only variants.
    (re.compile(r"^SAN MANUEL BAND OF MISSION INDIANS$"),
     "San Manuel Band of Mission Indians"),

    # Lyft — case-and-punctuation variants.
    (re.compile(r"^LYFT,?\s*INC$"),
     "Lyft, Inc"),

    # DraftKings — case variants on D/B/A and the corporate parent name.
    # Handle "INC" with optional trailing period or comma before "D/B/A".
    (re.compile(r"^CROWN GAMING INC[.,]?\s*D/?B/?A\s+DRAFTKINGS$"),
     "DraftKings (Crown Gaming Inc)"),
    (re.compile(r"^DRAFTKINGS,?\s*INC[.,]?$"),
     "DraftKings (Crown Gaming Inc)"),

    # FanDuel — D/B/A case variants on Betfair Interactive parent.
    (re.compile(r"^BETFAIR INTERACTIVE US LLC\s+D/B/A\s+FANDUEL SPORTSBOOK\s*\(.+\)$"),
     "FanDuel Sportsbook (Betfair Interactive US)"),

    # California Apartment Association — multiple flavors.
    (re.compile(r"^CALIFORNIA APARTMENT ASSOCIATION ISSUES COMMITTEE$"),
     "California Apartment Association Issues Committee"),
    (re.compile(r"^CALIFORNIA APARTMENT ASSOCIATION PAC$"),
     "California Apartment Association PAC"),

    # Philip Morris USA — affiliate / service-company / d/b/a variants all
    # collapse to the parent. Codex flagged: "PHILIP MORRIS USA INC. (MADE BY
    # ITS SERVICE COMPANY...)" is the same filer as "PHILIP MORRIS USA INC".
    # Distinct subsidiary brands (UST, John Middleton, Numark) preserved.
    (re.compile(r"^PHILIP MORRIS USA,? INC[.,]?\s*(AND ITS AFFILIATES)?\s*(\([^)]+\))?$"),
     "Philip Morris USA Inc"),
    (re.compile(r"^PHILIP MORRIS INCORPORATED A SUBSIDIARY OF$"),
     "Philip Morris USA Inc"),

    # ACS chapter conflations — keep distinct chapters as separate entities,
    # only collapse the bare "American Cancer Society, Inc" variants.
    (re.compile(r"^AMERICAN CANCER SOCIETY,?\s*INC$"),
     "American Cancer Society, Inc"),

    # AltaMed (corp vs corporation suffix).
    (re.compile(r"^ALTAMED HEALTH SERVICES CORP(ORATION)?$"),
     "AltaMed Health Services Corporation"),

    # California Hospitals committee — long official name with parenthetical.
    (re.compile(r"^CALIFORNIA HOSPITALS COMMITTEE ON ISSUES.*\(CHCI\).*"),
     "California Hospitals Committee on Issues (CHCI)"),
]


def _normalize_for_match(name: str) -> str:
    """Pre-normalize a donor name for alias-pattern matching: uppercase,
    strip leading/trailing whitespace and trailing punctuation, collapse
    multi-space runs. Keeps internal punctuation intact so patterns like
    "Crown Gaming Inc D/B/A DraftKings" still match.
    """
    s = (name or "").strip().upper()
    # Strip trailing terminal punctuation that's noise for matching
    s = re.sub(r"[.,;\s]+$", "", s)
    # Collapse internal whitespace
    s = re.sub(r"\s+", " ", s)
    return s


def is_real_prop_num(s: str) -> bool:
    return bool(PROP_NUM_RE.match((s or "").strip().upper()))


def canonicalize_donor(raw_name: str) -> str:
    """Apply the hand-curated alias map. Falls back to a lightly-normalized
    raw name for everything else. The pre-normalization step (uppercase,
    trimmed, collapsed whitespace, trailing-punctuation stripped) is what
    handles the LYFT, INC. / LYFT, INC family of case+punctuation variants
    without needing per-donor patterns for each."""
    if not raw_name:
        return ""
    normalized = _normalize_for_match(raw_name)
    for pattern, canonical in DONOR_ALIAS_PATTERNS:
        if pattern.match(normalized):
            return canonical
    return normalized


# Stance overrides: explicit (finance_campaign_id, committee_name_substring)
# pairs for high-dollar committees where the regex patterns below don't fire
# (because the committee name doesn't quote the prop number) but the stance is
# unambiguous from context. Per Codex's review: don't broaden the regex for
# these — overrides are safer than teaching STOP/END/etc. too aggressively.
# Each entry: ((campaign_id, committee_substring_normalized): (stance, note)).
# committee_substring_normalized is matched as a substring against the
# uppercased committee name; first match wins.
COMMITTEE_STANCE_OVERRIDES: list[tuple[str, str, str, str]] = [
    # (finance_campaign_id, committee_name_substring_uppercased, stance, note)
    ("PROP_15_2020", "CALIFORNIANS TO STOP HIGHER PROPERTY TAXES", "oppose",
     "Stop-X organization opposing the split-roll property tax Prop 15"),
    ("PROP_25_2020", "END PREDATORY & UNFAIR MONEY BAIL", "support",
     "End-cash-bail coalition supporting Prop 25 (referendum to uphold SB 10)"),
    ("PROP_62_2016", "CALIFORNIANS FOR JUSTICE AND PUBLIC SAFETY", "oppose",
     "Pro-death-penalty committee opposing Prop 62 (death-penalty repeal)"),
    ("PROP_35_2000", "TAXPAYERS FOR FAIR COMPETITION", "support",
     "Pro-private-bidding committee supporting Prop 35 (opens state engineering bidding)"),
    ("PROP_4_2008", "PLANNED PARENTHOOD ADVOCACY PROJECT LOS ANGELES COUNTY", "oppose",
     "Planned Parenthood committee opposing Prop 4 (parental notification before minor abortion)"),
]


# Stance recovery: when source CSV stance is empty, infer from committee name
# using unambiguous indicator patterns. Anything that doesn't match an explicit
# pattern stays in the unknown_stance quarantine bucket.
STANCE_RECOVERY_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # Oppose patterns — phrases a no-side committee uses about itself.
    # "STOP" / "DEFEAT" / "NO ON" / "VOTE NO" / "AGAINST" + a prop reference.
    (re.compile(r"\b(STOP|DEFEAT)\b.+\b(PROP|PROPOSITION|PROP\.|MEASURE)\b"), "oppose", "verb_stop_or_defeat"),
    (re.compile(r"\b(STOP|DEFEAT) THE\b"), "oppose", "verb_stop_or_defeat_the"),
    (re.compile(r"\b(NO ON|VOTE NO ON|VOTE NO)\b"), "oppose", "explicit_no"),
    # Support patterns — phrases a yes-side committee uses about itself.
    (re.compile(r"\b(YES ON|VOTE YES ON|VOTE YES FOR)\b"), "support", "explicit_yes"),
    (re.compile(r"\bSUPPORTERS OF (PROP|PROPOSITION)\b"), "support", "supporters_of"),
    # Mixed-direction safety: committees with BOTH "yes" and "no" in name
    # (rare; usually opposition strategists masking) — leave ambiguous.
]


def recover_stance_from_committee(
    committee_name: str,
    campaign_id: str | None = None,
) -> tuple[str | None, str | None]:
    """Return (recovered_stance, pattern_id) or (None, None) if no clean match.

    Resolution order:
      1. Explicit (campaign_id, committee_substring) override (highest priority).
      2. Regex patterns. Committees containing BOTH yes and no language are
         skipped to avoid false positives from oppositional reframing.
    """
    if not committee_name:
        return None, None
    upper = committee_name.upper()

    # 1. Explicit overrides (Codex-recommended for high-dollar cases where
    # regex can't safely fire).
    if campaign_id:
        for ov_campaign, ov_substring, ov_stance, _note in COMMITTEE_STANCE_OVERRIDES:
            if ov_campaign == campaign_id and ov_substring in upper:
                return ov_stance, f"override:{ov_substring[:30]}"

    # 2. Regex patterns with yes/no safety.
    has_yes = bool(re.search(r"\b(YES ON|VOTE YES)\b", upper))
    has_no = bool(re.search(r"\b(NO ON|VOTE NO|STOP|DEFEAT)\b", upper))
    if has_yes and has_no:
        return None, None
    for pattern, stance, label in STANCE_RECOVERY_PATTERNS:
        if pattern.search(upper):
            return stance, label
    return None, None


def parse_date(s: str) -> date | None:
    if not s:
        return None
    s = s.strip()
    # CalAccess CSV uses M/D/YYYY (e.g. "10/2/2020") — try a few formats.
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def week_start_iso(d: date) -> str:
    """Round a date down to the Monday of its ISO week. Returns YYYY-MM-DD."""
    return (d - timedelta(days=d.weekday())).isoformat()


def load_crosswalk() -> dict[tuple[str, int], dict]:
    """Build (prop_num, year) -> crosswalk_row dict from the CSV."""
    lookup: dict[tuple[str, int], dict] = {}
    with CROSSWALK_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["status"] != "matched":
                # Missing / duplicate campaigns aren't surfaceable; skip them
                # for the matched-only build. The CSV stays as audit artifact.
                continue
            key = (row["prop_num"].upper(), int(row["election_year"]))
            lookup[key] = row
    return lookup


def create_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS finance_campaign;
        DROP TABLE IF EXISTS finance_summary;
        DROP TABLE IF EXISTS finance_top_donors;
        DROP TABLE IF EXISTS finance_timeline_weekly;
        DROP TABLE IF EXISTS finance_row_quarantine;

        CREATE TABLE finance_campaign (
            finance_campaign_id TEXT PRIMARY KEY,
            prop_num TEXT NOT NULL,
            election_year INTEGER NOT NULL,
            election_month INTEGER,
            measure_db_id INTEGER,
            measure_id TEXT,
            status TEXT NOT NULL,
            match_via TEXT,
            csv_row_count INTEGER,
            csv_total_amount REAL,
            notes TEXT
        );

        -- COALESCE-based unique index (SQLite's UNIQUE constraint treats NULL
        -- as distinct, so two rows with NULL election_month would slip past
        -- a regular UNIQUE; the COALESCE forces NULL into a sentinel value).
        CREATE UNIQUE INDEX uq_finance_campaign_prop_year_month
            ON finance_campaign (prop_num, election_year, COALESCE(election_month, 0));

        CREATE TABLE finance_summary (
            finance_campaign_id TEXT NOT NULL,
            stance TEXT NOT NULL,
            total_receipts REAL NOT NULL,
            n_committees INTEGER NOT NULL,
            top5_share REAL,
            hhi REAL,
            PRIMARY KEY (finance_campaign_id, stance),
            FOREIGN KEY (finance_campaign_id) REFERENCES finance_campaign(finance_campaign_id)
        );

        CREATE TABLE finance_top_donors (
            finance_campaign_id TEXT NOT NULL,
            stance TEXT NOT NULL,
            donor_name_canon TEXT NOT NULL,
            donor_type TEXT,
            total_amount REAL NOT NULL,
            PRIMARY KEY (finance_campaign_id, stance, donor_name_canon),
            FOREIGN KEY (finance_campaign_id) REFERENCES finance_campaign(finance_campaign_id)
        );

        CREATE TABLE finance_timeline_weekly (
            finance_campaign_id TEXT NOT NULL,
            stance TEXT NOT NULL,
            week_start TEXT NOT NULL,
            weekly_receipts REAL NOT NULL,
            cumulative_receipts REAL NOT NULL,
            PRIMARY KEY (finance_campaign_id, stance, week_start),
            FOREIGN KEY (finance_campaign_id) REFERENCES finance_campaign(finance_campaign_id)
        );

        CREATE TABLE finance_row_quarantine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_row_index INTEGER NOT NULL,
            prop_num TEXT,
            year INTEGER,
            txn_date TEXT,
            txn_year INTEGER,
            finance_campaign_id TEXT,
            quarantine_reason TEXT NOT NULL,
            amount REAL,
            committee_name TEXT,
            donor_name TEXT
        );

        CREATE INDEX idx_quarantine_reason ON finance_row_quarantine(quarantine_reason);
        CREATE INDEX idx_quarantine_campaign ON finance_row_quarantine(finance_campaign_id);
        CREATE INDEX idx_top_donors_amount ON finance_top_donors(finance_campaign_id, stance, total_amount DESC);
    """)
    conn.commit()


def populate_finance_campaign(conn: sqlite3.Connection) -> int:
    """Load the entire crosswalk into the finance_campaign table (matched rows
    only; missing/duplicate stay as audit-only artifacts in the CSV)."""
    cur = conn.cursor()
    inserted = 0
    with CROSSWALK_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["status"] != "matched":
                continue
            cur.execute("""
                INSERT INTO finance_campaign
                  (finance_campaign_id, prop_num, election_year, election_month,
                   measure_db_id, measure_id, status, match_via,
                   csv_row_count, csv_total_amount, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["finance_campaign_id"],
                row["prop_num"],
                int(row["election_year"]),
                int(row["election_month"]) if row["election_month"] else None,
                int(row["measure_db_id"]) if row["measure_db_id"] else None,
                row["measure_id"] or None,
                row["status"],
                row["match_via"] or None,
                int(row["csv_row_count"]) if row["csv_row_count"] else None,
                float(row["csv_total_amount"]) if row["csv_total_amount"] else None,
                row["notes"] or None,
            ))
            inserted += 1
    conn.commit()
    return inserted


def ingest_rows(conn: sqlite3.Connection, lookup: dict) -> dict:
    """Single pass over the source CSV. Validates each row at four gates,
    quarantines rejects, and accumulates kept rows for downstream aggregation.
    Returns a dict of accumulators."""
    cur = conn.cursor()

    # In-memory accumulators (campaign × stance keyed)
    by_campaign_stance: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "total": 0.0,
        "committees": set(),
        "donor_amounts": defaultdict(float),
        "donor_types": {},
        "weekly": defaultdict(float),
    })

    # Exact-duplicate detection: the source CSV contains 1.1M+ exact-duplicate
    # rows (53.5% of the file). Without this set, accepted-row aggregation
    # double-counts (or worse) every dollar that appears in a duplicate row.
    seen_keys: set[tuple] = set()
    stance_recovery_counts = Counter()

    quarantine_buffer: list[tuple] = []
    quarantine_counts = Counter()

    def quarantine(idx, prop_num, year, txn_date, txn_year, campaign_id, reason, amount, committee, donor):
        quarantine_buffer.append((
            idx, prop_num, year,
            txn_date.isoformat() if txn_date else None,
            txn_year, campaign_id, reason, amount, committee, donor
        ))
        quarantine_counts[reason] += 1

    kept_rows = 0
    kept_amount = 0.0

    with SOURCE_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            prop_num = (row.get("prop_num") or "").strip().upper()
            year_str = (row.get("year") or "").strip()
            stance = (row.get("stance") or "").strip().lower()
            committee = (row.get("committee_name") or "").strip()
            donor_raw = (row.get("donor_name") or "").strip()
            donor_type = (row.get("donor_type") or "").strip() or None
            try:
                amount = float(row.get("amount") or 0)
            except ValueError:
                amount = 0.0

            txn_date = parse_date(row.get("date") or "")
            txn_year = txn_date.year if txn_date else None

            # Gate 1: prop_num must be a real numeric prop
            if not is_real_prop_num(prop_num):
                quarantine(idx, prop_num, None, txn_date, txn_year, None,
                           "non_numeric_prop_num", amount, committee, donor_raw)
                continue

            # Gate 2: year must be populated
            if not year_str:
                quarantine(idx, prop_num, None, txn_date, txn_year, None,
                           "no_year", amount, committee, donor_raw)
                continue
            try:
                year = int(year_str)
            except ValueError:
                quarantine(idx, prop_num, None, txn_date, txn_year, None,
                           "bad_year", amount, committee, donor_raw)
                continue
            if year < 1990 or year > 2030:
                quarantine(idx, prop_num, year, txn_date, txn_year, None,
                           "out_of_range_year", amount, committee, donor_raw)
                continue

            # Gate 3: transaction date must be parseable and >= 1995
            if txn_date is None:
                quarantine(idx, prop_num, year, None, None, None,
                           "unparseable_date", amount, committee, donor_raw)
                continue
            if txn_date < date(1995, 1, 1):
                quarantine(idx, prop_num, year, txn_date, txn_year, None,
                           "before_1995", amount, committee, donor_raw)
                continue

            # Gate 4: campaign must exist in crosswalk
            cw = lookup.get((prop_num, year))
            if cw is None:
                quarantine(idx, prop_num, year, txn_date, txn_year, None,
                           "no_campaign", amount, committee, donor_raw)
                continue

            campaign_id = cw["finance_campaign_id"]

            # Gate 5: row-level date hygiene (Codex's blocker)
            if txn_year is not None and abs(txn_year - year) > 1:
                quarantine(idx, prop_num, year, txn_date, txn_year, campaign_id,
                           "date_off_cycle", amount, committee, donor_raw)
                continue

            # Stance gate with recovery: if source stance is empty/invalid,
            # try (1) explicit overrides for known high-dollar committees,
            # then (2) regex patterns. Anything ambiguous stays quarantined.
            if stance not in ("support", "oppose"):
                recovered_stance, recovery_label = recover_stance_from_committee(
                    committee, campaign_id=campaign_id
                )
                if recovered_stance is None:
                    quarantine(idx, prop_num, year, txn_date, txn_year, campaign_id,
                               "unknown_stance", amount, committee, donor_raw)
                    continue
                stance = recovered_stance
                stance_recovery_counts[recovery_label] += 1

            # Gate 6: amount must be positive (negatives are refunds; zero is
            # noise. We're aggregating gross receipts.)
            if amount <= 0:
                quarantine(idx, prop_num, year, txn_date, txn_year, campaign_id,
                           "non_positive_amount", amount, committee, donor_raw)
                continue

            # Gate 7: exact-duplicate dedupe. The CalAccess clean CSV contains
            # extensive exact-row repetition (PROP_22 / PROP_27 inflated 60-75%
            # without this gate). Key on the full (campaign, stance, date,
            # amount, donor, donor_type, committee) tuple.
            dup_key = (
                campaign_id, stance, txn_date.isoformat(), amount,
                donor_raw, donor_type or "", committee,
            )
            if dup_key in seen_keys:
                quarantine(idx, prop_num, year, txn_date, txn_year, campaign_id,
                           "exact_duplicate", amount, committee, donor_raw)
                continue
            seen_keys.add(dup_key)

            # Accept the row — accumulate.
            donor_canon = canonicalize_donor(donor_raw)

            acc = by_campaign_stance[(campaign_id, stance)]
            acc["total"] += amount
            if committee:
                acc["committees"].add(committee)
            if donor_canon:
                acc["donor_amounts"][donor_canon] += amount
                # First-seen donor_type wins (most rows for a donor share a
                # type; very occasional disagreements aren't worth a vote).
                if donor_canon not in acc["donor_types"] and donor_type:
                    acc["donor_types"][donor_canon] = donor_type
            acc["weekly"][week_start_iso(txn_date)] += amount

            kept_rows += 1
            kept_amount += amount

            if idx and idx % 200_000 == 0:
                # Flush quarantine buffer periodically to keep memory bounded.
                cur.executemany("""
                    INSERT INTO finance_row_quarantine
                      (source_row_index, prop_num, year, txn_date, txn_year,
                       finance_campaign_id, quarantine_reason, amount,
                       committee_name, donor_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, quarantine_buffer)
                quarantine_buffer.clear()
                conn.commit()

    # Final flush of quarantine buffer
    if quarantine_buffer:
        cur.executemany("""
            INSERT INTO finance_row_quarantine
              (source_row_index, prop_num, year, txn_date, txn_year,
               finance_campaign_id, quarantine_reason, amount,
               committee_name, donor_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, quarantine_buffer)
    conn.commit()

    return {
        "by_campaign_stance": by_campaign_stance,
        "quarantine_counts": quarantine_counts,
        "stance_recovery_counts": stance_recovery_counts,
        "kept_rows": kept_rows,
        "kept_amount": kept_amount,
    }


def write_aggregates(conn: sqlite3.Connection, accumulators: dict) -> None:
    """Build finance_summary, finance_top_donors, finance_timeline_weekly from
    the in-memory accumulators."""
    cur = conn.cursor()

    summary_rows = []
    top_donor_rows = []
    timeline_rows = []

    for (campaign_id, stance), acc in accumulators.items():
        total = acc["total"]
        if total <= 0:
            continue

        # Summary
        donor_amounts = acc["donor_amounts"]
        sorted_donors = sorted(donor_amounts.items(), key=lambda kv: -kv[1])
        top5_total = sum(amt for _, amt in sorted_donors[:5])
        top5_share = round(100 * top5_total / total, 2) if total else None

        # HHI: sum of (donor_share_pct)^2
        hhi = sum((100 * amt / total) ** 2 for amt in donor_amounts.values()) if total else 0
        hhi = round(hhi, 2)

        summary_rows.append((
            campaign_id, stance, total,
            len(acc["committees"]), top5_share, hhi,
        ))

        # Top donors (top 20 per stance — enough for the Insights panel and
        # per-measure modal; can be raised later if needed)
        for donor_canon, amt in sorted_donors[:20]:
            donor_type = acc["donor_types"].get(donor_canon)
            top_donor_rows.append((
                campaign_id, stance, donor_canon, donor_type, amt,
            ))

        # Timeline weekly
        sorted_weeks = sorted(acc["weekly"].items())
        cum = 0.0
        for week_start, weekly_amt in sorted_weeks:
            cum += weekly_amt
            timeline_rows.append((
                campaign_id, stance, week_start, weekly_amt, cum,
            ))

    cur.executemany("""
        INSERT INTO finance_summary
          (finance_campaign_id, stance, total_receipts, n_committees, top5_share, hhi)
        VALUES (?, ?, ?, ?, ?, ?)
    """, summary_rows)

    cur.executemany("""
        INSERT INTO finance_top_donors
          (finance_campaign_id, stance, donor_name_canon, donor_type, total_amount)
        VALUES (?, ?, ?, ?, ?)
    """, top_donor_rows)

    cur.executemany("""
        INSERT INTO finance_timeline_weekly
          (finance_campaign_id, stance, week_start, weekly_receipts, cumulative_receipts)
        VALUES (?, ?, ?, ?, ?)
    """, timeline_rows)

    conn.commit()
    print(f"  finance_summary rows: {len(summary_rows):,}")
    print(f"  finance_top_donors rows: {len(top_donor_rows):,}")
    print(f"  finance_timeline_weekly rows: {len(timeline_rows):,}")


def run_validation_gates(conn: sqlite3.Connection) -> None:
    """Codex's 7-point validation including named sentinel checks."""
    cur = conn.cursor()
    print("\n=== Validation gates ===")

    # 1. No finance summary rows keyed only by reused PROP_xx (every row has finance_campaign_id)
    cur.execute("SELECT COUNT(*) FROM finance_summary WHERE finance_campaign_id IS NULL OR finance_campaign_id NOT LIKE 'PROP%_%'")
    bad = cur.fetchone()[0]
    print(f"  [1] All summary rows have finance_campaign_id: {'OK' if bad == 0 else f'FAIL ({bad} bad rows)'}")

    # 2. Every campaign maps to a measure_db_id or is explicitly marked
    cur.execute("SELECT COUNT(*) FROM finance_campaign WHERE measure_db_id IS NULL AND status = 'matched'")
    bad = cur.fetchone()[0]
    print(f"  [2] Matched campaigns all have measure_db_id: {'OK' if bad == 0 else f'FAIL ({bad} bad rows)'}")

    # 3. Top-donor totals reconcile against summary totals
    cur.execute("""
        SELECT s.finance_campaign_id, s.stance, s.total_receipts,
               COALESCE((SELECT SUM(total_amount) FROM finance_top_donors d
                         WHERE d.finance_campaign_id = s.finance_campaign_id
                         AND d.stance = s.stance), 0) as top_donor_total
        FROM finance_summary s
    """)
    mismatches = []
    for cid, stance, total, top_total in cur.fetchall():
        # top-20 donor total should be <= summary total
        if top_total > total + 0.01:
            mismatches.append((cid, stance, total, top_total))
    print(f"  [3] Top-donor totals <= summary totals: {'OK' if not mismatches else f'FAIL ({len(mismatches)})'}")

    # 4. No campaign has multiple stance-rows where committee names overlap with conflicting stances
    cur.execute("""
        SELECT finance_campaign_id, COUNT(DISTINCT stance) FROM finance_summary
        GROUP BY finance_campaign_id HAVING COUNT(DISTINCT stance) > 2
    """)
    bad = cur.fetchall()
    print(f"  [4] No campaign has more than 2 stances: {'OK' if not bad else f'FAIL ({len(bad)})'}")

    # 5. Quarantine reason distribution + dollar impact
    cur.execute("""
        SELECT quarantine_reason, COUNT(*), COALESCE(SUM(amount), 0) FROM finance_row_quarantine
        GROUP BY quarantine_reason ORDER BY COUNT(*) DESC
    """)
    print(f"  [5] Quarantine breakdown:")
    for reason, n, amt in cur.fetchall():
        print(f"      {reason}: {n:,} rows, ${amt/1e6:.2f}M")

    # 6. Sentinel checks
    print(f"  [6] Sentinel checks (no wrong-cycle contamination):")
    sentinels = [
        ("PROP_16_2020", 2020, "no PG&E-dominated 2010 money"),
        ("PROP_32_2024", 2024, "no 2012 Paycheck Protection money"),
        ("PROP_22_2020", 2020, "no 2000/2010 activity"),
        ("PROP_6_2024", 2024, "no 2018 gas-tax money"),
    ]
    for cid, expected_year, desc in sentinels:
        cur.execute("""
            SELECT MIN(week_start), MAX(week_start),
                   SUM(weekly_receipts) FILTER (WHERE substr(week_start,1,4) = CAST(? AS TEXT)) as in_year_amt,
                   SUM(weekly_receipts) as total_amt
            FROM finance_timeline_weekly
            WHERE finance_campaign_id = ?
        """, (str(expected_year), cid))
        row = cur.fetchone()
        if row[0] is None:
            print(f"      {cid}: NO TIMELINE DATA")
            continue
        wmin, wmax, in_year, total = row
        in_year = in_year or 0
        total = total or 0
        in_year_pct = 100 * in_year / total if total else 0
        status = 'OK' if in_year_pct >= 90 else 'WARN' if in_year_pct >= 75 else 'FAIL'
        print(f"      {cid}: {status} — {in_year_pct:.1f}% of ${total/1e6:.2f}M is in {expected_year} (range {wmin[:7]} to {wmax[:7]}); {desc}")

    # 7. Total dollar reconciliation against the crosswalk's expected total
    cur.execute("SELECT SUM(total_receipts) FROM finance_summary")
    summary_total = cur.fetchone()[0] or 0
    cur.execute("SELECT SUM(csv_total_amount) FROM finance_campaign WHERE status='matched'")
    crosswalk_expected = cur.fetchone()[0] or 0
    drop_pct = 100 * (crosswalk_expected - summary_total) / crosswalk_expected if crosswalk_expected else 0
    print(f"  [7] Dollar reconciliation:")
    print(f"      Crosswalk-expected: ${crosswalk_expected/1e6:.1f}M")
    print(f"      Summary actual:     ${summary_total/1e6:.1f}M")
    print(f"      Drop (exact duplicates / off-cycle / unknown stance / no_campaign / non-positive): ${(crosswalk_expected-summary_total)/1e6:.1f}M ({drop_pct:.1f}%)")


def main() -> None:
    if not SOURCE_CSV.exists():
        raise SystemExit(f"Source CSV missing: {SOURCE_CSV}")
    if not CROSSWALK_CSV.exists():
        raise SystemExit(f"Crosswalk missing: {CROSSWALK_CSV}. Run build_finance_crosswalk.py first.")

    print(f"Loading crosswalk: {CROSSWALK_CSV}")
    lookup = load_crosswalk()
    print(f"  Crosswalk has {len(lookup):,} matched campaigns")

    if OUTPUT_DB.exists():
        OUTPUT_DB.unlink()
    print(f"\nCreating fresh DB: {OUTPUT_DB}")
    conn = sqlite3.connect(str(OUTPUT_DB))
    create_schema(conn)

    print("\nPopulating finance_campaign from crosswalk...")
    n = populate_finance_campaign(conn)
    print(f"  Inserted {n} campaign rows")

    print(f"\nIngesting source CSV with row-level validation...")
    accumulators = ingest_rows(conn, lookup)
    print(f"  Kept rows: {accumulators['kept_rows']:,}  (${accumulators['kept_amount']/1e6:,.1f}M)")
    if accumulators.get("stance_recovery_counts"):
        print(f"  Stance recovered from committee name:")
        for label, count in accumulators["stance_recovery_counts"].most_common():
            print(f"    {label}: {count:,}")
    print(f"  Quarantined:")
    for reason, count in accumulators["quarantine_counts"].most_common():
        print(f"    {reason}: {count:,}")

    print(f"\nWriting aggregates...")
    write_aggregates(conn, accumulators["by_campaign_stance"])

    run_validation_gates(conn)

    conn.close()
    print(f"\nDone. {OUTPUT_DB}")


if __name__ == "__main__":
    main()
