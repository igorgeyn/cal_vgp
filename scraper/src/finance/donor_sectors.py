"""
Hand-curated donor → sector classification.

Maps post-canonicalization `donor_name_canon` values (the strings produced
by `scripts/rebuild_finance_db.py::canonicalize_donor`) to a sector label.
Scope: top donors by aggregate dollar volume plus narrative-relevant names
below the top-25 cutoff. Long tail of small donors stays unclassified
(returns None from `get_donor_sector`) — renders as no chip in the UI.

Coverage caveat: top-25 by aggregate amount covers ~43% of total donor
dollar volume in `finance_top_donors` (Codex measurement, 2026-05-12) —
NOT 95% as initially claimed. The scope is "prominent visible donors"
not "majority of volume." Aggregate-by-sector cuts will report on
classified donors only with a clear "Other / unclassified" bucket for
the unclassified tail.

Taxonomy (12 categories, Codex-blessed):
- Labor              union committees, teacher / public-sector PACs
- Gig Economy        Uber, Lyft, DoorDash, Instacart, etc. — narrow.
                     Future Meta/Google would be a separate "Tech" bucket
                     when (if) they appear; not pre-creating it now.
- Tribal Gaming      casino-operating bands. Distinct from Commercial
                     Gambling because these are tribal governments;
                     downstream narrative can roll them up to a broader
                     gambling sector if useful.
- Commercial Gambling sportsbook firms / online gaming
- Healthcare         dialysis providers, hospital committees, drug
                     companies, healthcare advocacy. Internally
                     heterogeneous; subsector notes documented per-entry
                     until / unless a split is warranted by a narrative
                     use case.
- Real Estate        landlords + realtors. Internally heterogeneous;
                     CAA (anti-rent-control) vs CAR (broker interests)
                     have distinct policy stances. Subsector notes
                     documented per-entry.
- Tobacco            cigarette + smokeless tobacco companies
- Utilities          regulated electric / gas / water utilities (PG&E,
                     SCE, etc.)
- Energy             extractive / generative (oil, gas, renewable when
                     they show up). Distinct from Utilities.
- Individual         high-dollar individual donors. Narrative-specific
                     subdivisions (Munger Jr's redistricting focus,
                     Delaney's criminal-justice focus) stay outside this
                     data-layer lookup; they belong in editorial copy.
- Party / Political org   state/national party orgs, leadership PACs
- Other              business-roundtable orgs, financial-services
                     firms, or anything that doesn't cleanly fit the
                     above. Last-resort bucket.
"""
from __future__ import annotations

from typing import Optional


# Hand-curated donor → sector. Keys must match the post-canonicalization
# `donor_name_canon` exactly (the canonicalize_donor() output, not raw
# CalAccess names). Comments explain contentious calls per entry.
DONOR_SECTORS: dict[str, str] = {
    # ---- Labor --------------------------------------------------------
    "California Teachers Association Issues PAC": "Labor",
    "California Teachers Association": "Labor",
    "AFSCME AFL-CIO (MPO)": "Labor",
    "AFSCME California People Issues PAC": "Labor",
    "AFSCME AFL-CIO": "Labor",
    "AFT AFL-CIO COPE": "Labor",
    "AFT AFL-CIO": "Labor",
    "American Federation of Teachers": "Labor",
    # SEIU locals stay distinct (different bargaining units), all Labor
    "SEIU LOCAL 2015 ISSUES PAC": "Labor",
    "SERVICE EMPLOYEES INTERNATIONAL UNION LOCAL 721 CTW, CLC ISSUES & INITIATIVES": "Labor",
    "SERVICE EMPLOYEES INTERNATIONAL UNION LOCAL 1000 ISSUES PAC": "Labor",
    "SERVICE EMPLOYEES INTERNATIONAL UNION LOCAL 1000 CA STATE EMPLOYEES ASSOCIATION PAC": "Labor",
    "SEIU UNITED HEALTHCARE WORKERS WEST POLITICAL ISSUES COMMITTEE": "Labor",
    "SEIU CALIFORNIA STATE COUNCIL (NONPROFIT 501 (C)(5))": "Labor",
    "CALIFORNIA STATE COUNCIL OF SERVICE EMPLOYEES ISSUES COMMITTEE (SEIU)": "Labor",
    "SERVICE EMPLOYEES INTERNATIONAL UNION": "Labor",
    "NORTHERN CALIFORNIA CARPENTERS REGIONAL COUNCIL ISSUES PAC": "Labor",
    "CALIFORNIA FACULTY ASSOCIATION POLITICAL ISSUES COMMITTEE": "Labor",
    "CALIFORNIA FEDERATION OF TEACHERS COPE PROP/BALLOT COMMITTEE": "Labor",
    "CALIFORNIA PROFESSIONAL FIREFIGHTERS BALLOT ISSUES COMMITTEE": "Labor",
    "PACE OF CALIFORNIA SCHOOL EMPLOYEES ASSOCIATION - ISSUES": "Labor",
    # Labor unions visible on marquee fights (PROP_22 / PROP_8 oppose sides)
    "INTERNATIONAL BROTHERHOOD OF TEAMSTERS": "Labor",
    "UNITED FOOD & COMMERCIAL WORKERS LOCAL 770": "Labor",
    "UNITED FOOD AND COMMERCIAL WORKERS LOCAL 770": "Labor",
    "UNITED FOOD AND COMMERCIAL WORKERS INTERNATIONAL UNION CLC": "Labor",
    "UNITED FOOD AND COMMERCIAL WORKERS WESTERN STATES ISSUES PAC": "Labor",
    # SEIU UHW Nonprofit 501(c)(5) — multiple suffix variants now collapse
    # via canonicalize_donor to "SEIU-UHW Nonprofit 501(c)(5)" (audit
    # 2026-05-12 found CalAccess double-records the same transaction
    # under different suffix labels). The new canonical is what the v2
    # data carries; the older suffix-specific keys below are kept as
    # defense-in-depth for any data refresh that hasn't been re-rebuilt.
    "SEIU-UHW Nonprofit 501(c)(5)": "Labor",
    "SERVICE EMPLOYEES INTERNATIONAL UNION, UNITED HEALTHCARE WORKERS WEST (NONPROFIT 501(C)(5)) - YES ON 8 - CALIFORNIANS FOR KIDNEY DIALYSIS PATIENT PROTECTION": "Labor",
    "SERVICE EMPLOYEES INTERNATIONAL UNION, UNITED HEALTHCARE WORKERS WEST (NONPROFIT 501(C)(5)) - CALIFORNIANS FOR KIDNEY DIALYSIS PATIENT PROTECTION AND CALIFORNIANS CARE": "Labor",
    "SERVICE EMPLOYEES INTERNATIONAL UNION, UNITED HEALTHCARE WORKERS WEST (NONPROFIT 501(C)(5)) - YES ON 23- CALIFORNIANS FOR KIDNEY DIALYSIS PATIENT PROTECTION": "Labor",
    "SERVICE EMPLOYEES INTERNATIONAL UNION UNITED HEALTH CARE WORKERS WEST POLITICAL ISSUES COMMITTEE": "Labor",
    "SERVICE EMPLOYEES INTERNATIONAL UNION UNITED HEALTHCARE WORKERS WEST POLITICAL ISSUES COMMITTEE": "Labor",
    "SERVICE EMPLOYEES INTERNATIONAL UNION, UNITED HEALTHCARE WORKERS WEST NONPROFIT 501(C)(5)": "Labor",
    "SERVICE EMPLOYEES INTERNATIONAL UNION - UNITED HEALTHCARE WORKERS WEST": "Labor",
    "CA STATE COUNCIL OF SERVICE EMPLOYEES ISSUES COMMITTEE": "Labor",
    "SERVICE EMPLOYEES INTERNATIONAL UNION LOCAL 1021": "Labor",
    "DIGNITY CALIFORNIA SEIU LOCAL 2015": "Labor",

    # ---- Gig Economy --------------------------------------------------
    "Lyft, Inc": "Gig Economy",
    "UBER TECHNOLOGIES, INC": "Gig Economy",
    "DOORDASH, INC": "Gig Economy",
    "Instacart": "Gig Economy",  # post-canonicalization of Maplebear DBA
    "POSTMATES INC": "Gig Economy",  # acquired by Uber 2020 but filed under own name on PROP_22

    # ---- Tribal Gaming ------------------------------------------------
    # Casino-operating bands. Tribal-government status is preserved by
    # this sector label rather than lumping with Commercial Gambling.
    # Their political donations in CA are casino-policy-driven.
    "San Manuel Band of Mission Indians": "Tribal Gaming",
    "Pechanga Band of Luiseno Mission Indians": "Tribal Gaming",
    "MORONGO BAND OF MISSION INDIANS": "Tribal Gaming",
    "AGUA CALIENTE BAND OF CAHUILLA INDIANS": "Tribal Gaming",
    "PALA CASINO RESORT SPA": "Tribal Gaming",
    "PALA BAND OF MISSION INDIANS": "Tribal Gaming",
    # Tribal coalition opposing online sports betting (PROP_27_2022)
    "CALIFORNIANS FOR COMMUNITY SAFETY, EQUALITY AND REINVESTMENT, SPONSORED BY TRIBAL ORGANIZATIONS": "Tribal Gaming",

    # ---- Commercial Gambling ------------------------------------------
    "FanDuel Sportsbook (Betfair Interactive US)": "Commercial Gambling",
    "DraftKings (Crown Gaming Inc)": "Commercial Gambling",
    # Other PROP_27_2022 support-side sportsbook firms
    "FBG ENTERPRISES OPCO, LLC(RESPONSIBLE OFFICER: ARI BOROD)": "Commercial Gambling",  # Fanatics
    "PENN INTERACTIVE VENTURES, LLC(RESPONSIBLE OFFICER: JON KAPLOWITZ)": "Commercial Gambling",  # Penn/Barstool
    "BETMGM LLC(RESPONSIBLE OFFICER: ANDREW HAGOPIAN)": "Commercial Gambling",

    # ---- Healthcare ---------------------------------------------------
    # Subsector notes (not exposed yet — kept here for future splits):
    # - DaVita / Fresenius: dialysis providers (Prop 8 2018 fight)
    # - AIDS Healthcare Foundation: advocacy / drug pricing / housing
    # - California Hospitals Committee (CHCI): hospital industry
    # - PhRMA: pharma industry
    # - AMR: ambulance / emergency medical services
    "DaVita": "Healthcare",
    "FRESENIUS MEDICAL CARE NORTH AMERICA": "Healthcare",
    "AIDS HEALTHCARE FOUNDATION": "Healthcare",
    "California Hospitals Committee on Issues (CHCI)": "Healthcare",
    "CALIFORNIA HOSPITALS COMMITTEE ON ISSUES, SPONSORED BY CAHHS": "Healthcare",
    "PHARMACEUTICAL RESEARCH AND MANUFACTURERS OF AMERICA CA INITIATIVE FUND": "Healthcare",
    "AMERICAN MEDICAL RESPONSE (AMR)": "Healthcare",
    # PROP_8_2018 oppose-side dialysis providers (industry coalition)
    "US RENAL CARE, INC": "Healthcare",
    "DIALYSIS CLINIC, INC": "Healthcare",
    "SATELLITE HEALTHCARE, INC": "Healthcare",
    "AMERICAN RENAL MANAGEMENT LLC": "Healthcare",

    # ---- Real Estate --------------------------------------------------
    # Subsector notes (per-entry):
    # - CAA (Cal Apt Assn): landlord interests, anti-rent-control
    # - CAR / CAR IMPAC: realtor interests, often pro-housing-supply
    # - NAR: national realtor org, different entity from state CAR
    "California Apartment Association Issues Committee": "Real Estate",
    "California Apartment Association PAC": "Real Estate",
    "CALIFORNIA ASSOCIATION OF REALTORS": "Real Estate",
    "California Association of Realtors Issues Mobilization PAC": "Real Estate",
    "NATIONAL ASSOCIATION OF REALTORS": "Real Estate",

    # ---- Tobacco ------------------------------------------------------
    "Philip Morris USA Inc": "Tobacco",
    "R.J. Reynolds Tobacco Company": "Tobacco",
    "American Snuff Co (R.J. Reynolds affiliate)": "Tobacco",
    "Santa Fe Natural Tobacco (R.J. Reynolds affiliate)": "Tobacco",

    # ---- Utilities (regulated monopolies) ----------------------------
    # PG&E appears under 7 spelling variants; classifying each so the
    # sector chip fires regardless of which name is on the row. Future
    # work could canonicalize these to one PG&E entry (deferred).
    "PACIFIC GAS AND ELECTRIC COMPANY": "Utilities",
    "PACIFIC GAS & ELECTRIC COMPANY": "Utilities",
    "PG&E CORPORATION AND AFFILIATED ENTITIES": "Utilities",
    "PG&E CORPORATION": "Utilities",
    "PG&E CORPORATION AND AFILIATED ENTITIES": "Utilities",
    "PG&E AND AFFILIATED ENTITIES": "Utilities",
    "COALITION FOR RELIABLE AND AFFORDABLE ELECTRICITY (PG&E)": "Utilities",

    # ---- Energy (extractive / generative) ----------------------------
    "CHEVRON CORPORATION": "Energy",
    "AERA ENERGY LLP": "Energy",

    # ---- Individual ---------------------------------------------------
    # Narrative-specific subdivisions (Munger Jr's redistricting focus,
    # Delaney's criminal-justice focus, Bloomberg's gun-control + soda-tax
    # focus) stay outside this lookup — they belong in editorial copy.
    "Charles T. Munger, Jr.": "Individual",
    "MUNGER, MOLLY": "Individual",
    "M. Quinn Delaney": "Individual",
    "BLOOMBERG, MICHAEL R": "Individual",
    "HASTINGS, REED": "Individual",

    # ---- Party / Political org ----------------------------------------
    "CONGRESSIONAL LEADERSHIP FUND": "Party / Political org",
    "CALIFORNIA DEMOCRATIC PARTY": "Party / Political org",
    "DEMOCRATIC STATE CENTRAL COMMITTEE OF CALIFORNIA": "Party / Political org",

    # ---- Other --------------------------------------------------------
    # Business-roundtable / financial-services / single-purpose committees
    # that don't fit a cleaner sector. Last-resort bucket. Documented per
    # entry; subdivisions can emerge from this bucket later if a narrative
    # use case demands.
    "CALIFORNIA BUSINESS ROUNDTABLE ISSUES PAC": "Other",
    "ROBERT W. BAIRD & CO. INC": "Other",  # financial services / investment bank
    "SALOMONSMITHBARNEY": "Other",  # historical financial-services
    "JPMORGAN CHASE BANK": "Other",  # financial services
    "FIRST REPUBLIC BANK": "Other",  # financial services
    "BANK OF MARIN": "Other",  # financial services
}


# Recognized sector names — used for sanity-checking and as the contract
# for downstream consumers (UI chip colors, aggregate-by-sector queries).
SECTORS: tuple[str, ...] = (
    "Labor",
    "Gig Economy",
    "Tribal Gaming",
    "Commercial Gambling",
    "Healthcare",
    "Real Estate",
    "Tobacco",
    "Utilities",
    "Energy",
    "Individual",
    "Party / Political org",
    "Other",
)


def get_donor_sector(donor_name_canon: Optional[str]) -> Optional[str]:
    """Return the sector label for a canonicalized donor name, or None if
    the donor isn't in the hand-curated lookup. Lookups are exact-match on
    the canonical name — apply `canonicalize_donor()` upstream first if
    you're starting from a raw CalAccess donor string.
    """
    if not donor_name_canon:
        return None
    return DONOR_SECTORS.get(donor_name_canon)
