"""
Curated cross-source donor-name aliases for the combined v2 + v3 display layer.

v2 (finance_top_donors) and v3 (finance_flow_v3) canonicalize donor names
independently. The same legal entity sometimes ends up with two slightly
different canon strings — most commonly a comma/whitespace difference, a
"RESPONSIBLE OFFICER:..." suffix in v3, or a D/B/A pairing where v2 picked
the consumer-facing name and v3 picked the LLC.

This module applies ONLY at combined merge / display time
(get_combined_top_donors, _build_finance_supplements). It does NOT touch
the underlying v2 or v3 storage canonicalization — those stay independent
so reconciliation against the source dbs remains exact.

**Scope is intentionally narrow:** only pairs where the two names clearly
reference the same legal entity with minor formatting differences. We do
NOT merge:
- Different organizational levels (SEIU Local 1000 vs SEIU Local 1021,
  UFCW Local 770 vs Local 135 — those are distinct filing entities even
  though the parent unions are related).
- Parent-org / subsidiary distinctions ("PG&E Corporation" vs "Pacific
  Gas and Electric Company") — those have separate political activity.
- "Affiliated entities" suffixes that may genuinely encompass different
  contributor sets ("Essex Property Trust" vs "Essex ... AND AFFILIATED
  ENTITIES" — could be legitimately distinct accounting).

When you spot a new visible split in top-donor lists, add it here only
if both names clearly identify the same legal entity.
"""
from typing import Optional


# Map: raw donor_name_canon (case-insensitive) -> canonical display name.
# Keys are uppercase normalized (we lookup via uppercase) so adding a key
# in either case form works. The value is the preferred display string.
_DONOR_ALIASES_RAW = {
    # Uber: comma diff only between v2 and v3 canonicalization.
    "UBER TECHNOLOGIES, INC": "Uber Technologies, Inc",
    "UBER TECHNOLOGIES INC": "Uber Technologies, Inc",
    # Postmates: comma diff only.
    "POSTMATES INC": "Postmates, Inc",
    "POSTMATES, INC": "Postmates, Inc",
    # FanDuel: v2 uses the consumer-facing brand wrapping; v3 has the LLC
    # legal entity. Same underlying donor.
    "FANDUEL SPORTSBOOK (BETFAIR INTERACTIVE US)":
        "FanDuel Sportsbook (Betfair Interactive US LLC)",
    "BETFAIR INTERACTIVE US LLC D/B/A FANDUEL GROUP, INC":
        "FanDuel Sportsbook (Betfair Interactive US LLC)",
    # FBG Enterprises (DraftKings affiliate): v2 carries the LLC with a
    # responsible-officer suffix; v3 has the clean LLC name.
    "FBG ENTERPRISES, LLC": "FBG Enterprises, LLC",
    "FBG ENTERPRISES OPCO, LLC(RESPONSIBLE OFFICER: ARI BOROD)":
        "FBG Enterprises, LLC",
    "FBG ENTERPRISES OPCO, LLC(RESPONSIBLE OFFICER: JON KAPLOWITZ)":
        "FBG Enterprises, LLC",
    # Penn Interactive: same responsible-officer-suffix pattern.
    "PENN INTERACTIVE VENTURES, LLC": "Penn Interactive Ventures, LLC",
    "PENN INTERACTIVE VENTURES, LLC(RESPONSIBLE OFFICER: JON KAPLOWITZ)":
        "Penn Interactive Ventures, LLC",
    # Instacart / Maplebear: legal entity name vs consumer brand.
    # v2 already merged some variants; v3 has both forms.
    "INSTACART": "Instacart",
    "MAPLEBEAR INC. D/B/A INSTACART": "Instacart",
    # Pala Band: v3 sometimes inlines the casino entity name.
    "PALA BAND OF MISSION INDIANS": "Pala Band of Mission Indians",
    "PALA BAND OF MISSION INDIANS AND AFFILIATED ENTITY PALA CASINO SPA RESORT":
        "Pala Band of Mission Indians",
    # AIMCO: ampersand vs "and" + with/without "affiliated entities".
    # All three variants show up on the same measure.
    "APARTMENT INVESTMENT AND MANAGEMENT COMPANY (AIMCO)":
        "Apartment Investment and Management Company (AIMCO)",
    "APARTMENT INVESTMENT AND MANAGEMENT COMPANY (AIMCO) AND AFFILIATED ENTITIES":
        "Apartment Investment and Management Company (AIMCO)",
    "APARTMENT INVESTMENT AND MANAGEMENT COMPANY (AIMCO) & AFFILIATED ENTITIES":
        "Apartment Investment and Management Company (AIMCO)",
}

# Build the uppercase lookup once at import.
_DONOR_ALIASES = {k.upper(): v for k, v in _DONOR_ALIASES_RAW.items()}


def canonicalize_display_donor(name: Optional[str]) -> Optional[str]:
    """Return the canonical display name for a donor, if a curated
    alias exists; otherwise return the input unchanged. None in → None out.

    Used at combined merge points to dedupe visible splits across v2 + v3
    canonicalization drift. The lookup is case-insensitive on the input
    side; the output is the curated preferred display form.
    """
    if not name:
        return name
    return _DONOR_ALIASES.get(name.strip().upper(), name)
