"""Conservative attribution resolver for v3 finance ingest (Codex round-6).

A row in CAL-ACCESS (RCPT_CD / LOAN_CD / EXPN_CD / S496_CD / S497_CD)
resolves to a (finance_campaign_id, stance) pair via a sequence of
attribution methods, in order of preference:

  cover_sheet              -- BAL_NUM / BAL_NAME on cover sheet
  row_fields               -- BAL_NUM / SUP_OPP_CD on the line item
  filer_name_explicit      -- single-prop committee name like
                              "YES ON 14: CALIFORNIANS FOR..."
  filer_name_prop_stance_pair -- multi-prop name with per-prop stance
                              like "NO ON 30 / YES ON 32"; usable only
                              when row-level BAL/SUP fields can pick
                              which prop the line belongs to
  manual_override          -- curated table for names with no prop
                              number, e.g. "HOLD POLITICIANS
                              ACCOUNTABLE", "Stop the Republican
                              Recall of Governor Newsom"

Quarantine reasons for un-resolvable rows:

  no_cover_sheet            -- cover sheet absent (LOAN_CD / RCPT_CD /
                               etc., filing not in CVR)
  no_campaign_match         -- prop_num + year extracted but no v2
                               crosswalk entry
  bad_prop_or_year          -- couldn't extract prop_num + year at all
  ambiguous_multi_prop      -- 2+ distinct props named; no row-level
                               disambiguation
  ambiguous_year            -- prop number known but multiple plausible
                               election years (California reuses prop
                               numbers; date evidence didn't pick one)
  unknown_stance            -- prop + year resolved but stance unknown
                               and no recovery pattern matched
  filer_name_no_prop        -- filer name has no recognizable prop
                               reference and no manual override

The resolver returns a structured AttributionResult that callers
attach to finance_flow_v3 rows. attribution_method on the row records
which path produced the result.

Design rule (Codex round-6): automatic fallback requires exactly one
prop mention OR one prop-specific stance pair, plus exactly one
plausible crosswalk campaign after date scoring. Anything else is
quarantine or manual override.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Optional


# Safe automatic patterns for filer-name prop extraction. Each pattern
# yields (prop_num, stance_or_None). Order matters: more specific
# patterns first.
_FILER_NAME_PATTERNS: list[tuple[re.Pattern[str], Optional[str]]] = [
    # "VOTE YES ON ..." / "VOTE NO ON ..."
    (re.compile(r"\bVOTE\s+YES\s+ON\s+(?:PROP(?:\.|OSITION)?\s+)?(\d+[A-Z]?)\b",
                re.IGNORECASE), "support"),
    (re.compile(r"\bVOTE\s+NO\s+ON\s+(?:PROP(?:\.|OSITION)?\s+)?(\d+[A-Z]?)\b",
                re.IGNORECASE), "oppose"),
    # "YES ON PROP ..." / "NO ON PROP ..."
    (re.compile(r"\bYES\s+ON\s+PROP(?:\.|OSITION)?\s+(\d+[A-Z]?)\b",
                re.IGNORECASE), "support"),
    (re.compile(r"\bNO\s+ON\s+PROP(?:\.|OSITION)?\s+(\d+[A-Z]?)\b",
                re.IGNORECASE), "oppose"),
    # Plain "YES ON N" / "NO ON N"
    (re.compile(r"\bYES\s+ON\s+(\d+[A-Z]?)\b", re.IGNORECASE), "support"),
    (re.compile(r"\bNO\s+ON\s+(\d+[A-Z]?)\b", re.IGNORECASE), "oppose"),
    # "PROP 38 YES" / "PROP38YES.COM"
    (re.compile(r"\bPROP\.?\s*(\d+[A-Z]?)\s*YES\b", re.IGNORECASE), "support"),
    (re.compile(r"\bPROP\.?\s*(\d+[A-Z]?)\s*NO\b", re.IGNORECASE), "oppose"),
    (re.compile(r"\bPROP(\d+[A-Z]?)YES\b", re.IGNORECASE), "support"),
    (re.compile(r"\bPROP(\d+[A-Z]?)NO\b", re.IGNORECASE), "oppose"),
    # Stance verbs (Codex round-7, cautious additions)
    (re.compile(r"\bSUPPORTING\s+PROP(?:\.|OSITION)?\s+(\d+[A-Z]?)\b",
                re.IGNORECASE), "support"),
    (re.compile(r"\bOPPOSING\s+PROP(?:\.|OSITION)?\s+(\d+[A-Z]?)\b",
                re.IGNORECASE), "oppose"),
    (re.compile(r"\bFOR\s+PROP(?:\.|OSITION)\s+(\d+[A-Z]?)\b",
                re.IGNORECASE), "support"),
    (re.compile(r"\bAGAINST\s+PROP(?:\.|OSITION)\s+(\d+[A-Z]?)\b",
                re.IGNORECASE), "oppose"),
    # "YES PROP 98" (without explicit "ON")
    (re.compile(r"\bYES\s+PROP(?:\.|OSITION)?\s+(\d+[A-Z]?)\b",
                re.IGNORECASE), "support"),
    (re.compile(r"\bNO\s+PROP(?:\.|OSITION)?\s+(\d+[A-Z]?)\b",
                re.IGNORECASE), "oppose"),
    # Bare prop reference, no stance. Last so stance-bearing patterns
    # match first.
    (re.compile(r"\bPROP(?:\.|OSITION)?\s+(\d+[A-Z]?)\b",
                re.IGNORECASE), None),
]

# Plural pattern: "Yes on Props 1 and 2", "Yes on Props 1 & 2",
# "No on Propositions 30, 32", "Yes on Props 1&2".
# Codex round-9: ampersand syntax added. Requires PLURAL Props /
# Propositions keyword so "Prop. 13 & R.J. Riordan" doesn't false-
# positive (singular PROP. would never match). Requires AT LEAST
# ONE separator between numbers so a lone "PROP 13" doesn't trigger
# plural either.
_PLURAL_PATTERN_SUPPORT = re.compile(
    r"\bYES\s+ON\s+(?:PROPS|PROPOSITIONS)\.?\s+"
    r"(\d+[A-Z]?(?:\s*(?:,|AND|&)\s*\d+[A-Z]?)+)",
    re.IGNORECASE,
)
_PLURAL_PATTERN_OPPOSE = re.compile(
    r"\bNO\s+ON\s+(?:PROPS|PROPOSITIONS)\.?\s+"
    r"(\d+[A-Z]?(?:\s*(?:,|AND|&)\s*\d+[A-Z]?)+)",
    re.IGNORECASE,
)
_NUMBERED_TOKEN = re.compile(r"(\d+[A-Z]?)", re.IGNORECASE)


@dataclass
class FilerNameMention:
    """One (prop_num, stance) extraction from a filer name."""
    prop_num: str
    stance: Optional[str]  # 'support' | 'oppose' | None
    matched_text: str


def extract_prop_mentions(filer_name: str) -> list[FilerNameMention]:
    """Return all (prop_num, stance) mentions in the filer name.

    Conservative: only matches explicit prop / yes / no patterns. Does
    not extract bare numbers, years, district numbers, or "$2 billion"
    type noise. Returns empty list if no prop reference is found.
    """
    if not filer_name:
        return []
    mentions: list[FilerNameMention] = []
    seen: set[tuple[str, Optional[str]]] = set()

    # Plural patterns first: "Yes on Props 1 and 2", "No on Props 30, 32"
    # Each plural match yields multiple FilerNameMentions with same stance
    for pattern, stance in (
        (_PLURAL_PATTERN_SUPPORT, "support"),
        (_PLURAL_PATTERN_OPPOSE, "oppose"),
    ):
        for m in pattern.finditer(filer_name):
            tokens = _NUMBERED_TOKEN.findall(m.group(1))
            for prop_token in tokens:
                prop = prop_token.upper()
                key = (prop, stance)
                if key not in seen:
                    seen.add(key)
                    mentions.append(FilerNameMention(
                        prop_num=prop,
                        stance=stance,
                        matched_text=m.group(0),
                    ))

    for pattern, stance in _FILER_NAME_PATTERNS:
        for m in pattern.finditer(filer_name):
            prop = m.group(1).upper()
            # Don't merge stance=None matches with stance-bearing ones;
            # a name might say "YES ON 14" AND "PROPOSITION 14" — keep
            # the stance-bearing version only
            if stance is None and any(
                p == prop and s is not None for (p, s) in seen
            ):
                continue
            key = (prop, stance)
            if key in seen:
                continue
            # If we previously recorded the same prop without stance,
            # remove the unstanced version in favor of this one
            if stance is not None:
                mentions = [
                    mn for mn in mentions
                    if not (mn.prop_num == prop and mn.stance is None)
                ]
                seen = {
                    (p, s) for (p, s) in seen
                    if not (p == prop and s is None)
                }
            seen.add(key)
            mentions.append(FilerNameMention(
                prop_num=prop,
                stance=stance,
                matched_text=m.group(0),
            ))
    # Deduplicate: collapse stance-None entries for props that already
    # have stance-bearing entries
    final: list[FilerNameMention] = []
    stance_props = {mn.prop_num for mn in mentions if mn.stance is not None}
    for mn in mentions:
        if mn.stance is None and mn.prop_num in stance_props:
            continue
        final.append(mn)
    return final


# ---------------------------------------------------------------------------
# AttributionResult + resolver
# ---------------------------------------------------------------------------


@dataclass
class AttributionResult:
    finance_campaign_id: Optional[str] = None  # canonical (post-collapse)
    measure_db_id: Optional[int] = None
    stance: Optional[str] = None
    attribution_method: str = "failed"
    quarantine_reason: Optional[str] = None
    # Codex round-8: preserve which crosswalk row matched before
    # canonicalization. Equals finance_campaign_id when no remap
    # happened. Differs when a cover sheet hit an alias (e.g.
    # PROP_79_2006) and we collapsed to the canonical (PROP_79_2005).
    source_crosswalk_campaign_id: Optional[str] = None
    debug: list[str] = field(default_factory=list)

    @property
    def resolved(self) -> bool:
        return (
            self.finance_campaign_id is not None
            and self.stance is not None
            and self.quarantine_reason is None
        )


class AttributionResolver:
    """Resolves a row to (finance_campaign_id, stance) using a chain of
    attribution methods.

    Construct with the v2 crosswalk dict {(prop_num, year): (cid, mdb)}
    and optionally a manual-override lookup
    {normalized_filer_name: [(cid, stance), ...]}.

    Call one of the resolve_from_* methods. The first method that
    succeeds wins; downstream callers can chain.
    """

    def __init__(self, crosswalk: dict[tuple[str, int],
                                       tuple[str, int]],
                 manual_overrides: Optional[dict] = None,
                 match_via_by_cid: Optional[dict[str, str]] = None) -> None:
        self.crosswalk = crosswalk
        self.match_via_by_cid = match_via_by_cid or {}

        # Codex round-8: canonical choice principled rule.
        # For each measure_db_id with multiple crosswalk rows, the
        # canonical is the one whose match_via does NOT start with
        # 'year_offset_'. Year-offset rows are matcher-v2 late-filing
        # aliases of the actual election-year row. If match_via is
        # not available, fall back to lowest election_year (the actual
        # election year is always earlier than a year_offset alias).
        self.canonical_by_mdb: dict[int, tuple[int, str]] = {}
        rows_by_mdb: dict[int, list[tuple[int, str]]] = {}
        for (prop_num, year), (cid, mdb) in crosswalk.items():
            rows_by_mdb.setdefault(mdb, []).append((year, cid))
        for mdb, rows in rows_by_mdb.items():
            non_offset = [
                (y, c) for (y, c) in rows
                if not (self.match_via_by_cid.get(c) or "").startswith(
                    "year_offset_"
                )
            ]
            if len(non_offset) == 1:
                self.canonical_by_mdb[mdb] = non_offset[0]
            elif len(non_offset) > 1:
                # Multiple non-offset rows: pick lowest year + log
                non_offset.sort(key=lambda r: r[0])
                self.canonical_by_mdb[mdb] = non_offset[0]
            else:
                # No match_via info; fall back to lowest year
                rows.sort(key=lambda r: r[0])
                self.canonical_by_mdb[mdb] = rows[0]

        # props_by_num: distinct measures only (one entry per
        # measure_db_id, using the canonical). Genuine prop-number
        # reuse (Prop 14 = 2004 vs 2020 stem cell with different
        # measure_db_ids) stays multi-candidate.
        self.props_by_num: dict[str, list[tuple[int, str, int]]] = {}
        seen_mdbs_per_prop: dict[str, set[int]] = {}
        for (prop_num, year), (cid, mdb) in crosswalk.items():
            seen = seen_mdbs_per_prop.setdefault(prop_num, set())
            if mdb in seen:
                continue
            seen.add(mdb)
            canonical_year, canonical_cid = self.canonical_by_mdb[mdb]
            self.props_by_num.setdefault(prop_num, []).append(
                (canonical_year, canonical_cid, mdb)
            )
        for entries in self.props_by_num.values():
            entries.sort(key=lambda e: e[0])

        self.manual_overrides = manual_overrides or {}

    # -- Cover-sheet path -------------------------------------------

    def resolve_from_cover_sheet(self, prop_num: Optional[str],
                                 election_year: Optional[int],
                                 cover_sup_opp_cd: str) -> AttributionResult:
        if not prop_num or not election_year:
            return AttributionResult(
                quarantine_reason="bad_prop_or_year",
                attribution_method="failed",
                debug=[f"prop_num={prop_num!r} year={election_year!r}"],
            )
        hit = self.crosswalk.get((prop_num, election_year))
        if not hit:
            return AttributionResult(
                quarantine_reason="no_campaign_match",
                attribution_method="failed",
                debug=[f"({prop_num}, {election_year}) not in crosswalk"],
            )
        cid, mdb = hit
        stance = _normalize_sup_opp(cover_sup_opp_cd)
        # Codex round-8: canonicalize even when cover-sheet hits an
        # alias row directly. If the matched cid is a year_offset
        # alias (e.g. PROP_79_2006), remap to canonical PROP_79_2005.
        # Preserve the matched cid in source_crosswalk_campaign_id so
        # downstream audit can see what the cover sheet actually said.
        canonical = self.canonical_by_mdb.get(mdb)
        canonical_cid = canonical[1] if canonical else cid
        return AttributionResult(
            finance_campaign_id=canonical_cid,
            source_crosswalk_campaign_id=cid,
            measure_db_id=mdb,
            stance=stance,
            attribution_method="cover_sheet",
            quarantine_reason=("unknown_stance" if stance is None else None),
        )

    # -- Filer-name path --------------------------------------------

    def resolve_from_filer_name(self, filer_name: str,
                                date_hints: Iterable[date | None]
                                ) -> AttributionResult:
        """Resolve via the conservative filer-name patterns.

        date_hints are used for year-scoring when a prop number
        matches multiple v2 campaigns (e.g. Prop 14 = 2004 stem cell
        OR 2020 stem cell renewal). The resolver picks a candidate
        only when one is clearly better than any other (within 1 year
        of the date_hints AND uniquely so).
        """
        mentions = extract_prop_mentions(filer_name)
        if not mentions:
            return AttributionResult(
                quarantine_reason="filer_name_no_prop",
                attribution_method="failed",
                debug=[f"no prop mention in {filer_name!r}"],
            )
        distinct_props = {mn.prop_num for mn in mentions}
        if len(distinct_props) > 1:
            # Multi-prop name (e.g. "NO ON 30 / YES ON 32"). Stance
            # may be paired per prop, but we can't pick which prop
            # the line belongs to without row-level fields. Quarantine.
            return AttributionResult(
                quarantine_reason="ambiguous_multi_prop",
                attribution_method="failed",
                debug=[
                    f"multi-prop filer name: "
                    f"{[(m.prop_num, m.stance) for m in mentions]}",
                ],
            )
        prop_num = next(iter(distinct_props))
        # Pool stances across the mentions of that prop (if name has
        # "YES ON 14" + "PROPOSITION 14" we keep "support")
        stance_set = {mn.stance for mn in mentions if mn.stance is not None}
        stance: Optional[str]
        if len(stance_set) == 1:
            stance = stance_set.pop()
        elif len(stance_set) > 1:
            # Conflicting stances for same prop (shouldn't happen often)
            return AttributionResult(
                quarantine_reason="unknown_stance",
                attribution_method="failed",
                debug=[
                    f"conflicting stances for prop {prop_num}: "
                    f"{stance_set}",
                ],
            )
        else:
            stance = None  # bare PROP. 13 reference, no stance

        return self._resolve_prop_with_dates(
            prop_num, stance, date_hints,
            method_name="filer_name_explicit",
        )

    # -- Row-fields path (Phase 4) ----------------------------------

    def resolve_from_row_fields(self, row_bal_num: Optional[str],
                                row_bal_name: Optional[str],
                                row_sup_opp_cd: Optional[str],
                                date_hints: Iterable[date | None],
                                cover_bal_num: Optional[str] = None,
                                cover_sup_opp_cd: Optional[str] = None,
                                ) -> AttributionResult:
        """For EXPN_CD / S497_CD / S401_CD rows that have BAL_NUM /
        SUP_OPP_CD on the line item itself.

        Codex round-10: conditional cover-stance fallback when row
        stance is missing. Only fall back to cover stance when cover
        prop matches row prop — otherwise the cover stance can mis-
        attribute a multi-prop filing's individual IE line.

        Rule:
        - row prop + row stance resolved: accept.
        - row prop present but row stance missing: use cover stance
          ONLY if cover prop matches row prop. Else fall through to
          unknown_stance.
        - row prop missing: caller falls back to resolve_from_cover_sheet
          / filer_name. (This path requires a row prop.)
        """
        prop_num = _clean_prop_num(row_bal_num) or _extract_prop_from_name(
            row_bal_name
        )
        if not prop_num:
            return AttributionResult(
                quarantine_reason="bad_prop_or_year",
                attribution_method="failed",
            )
        stance = _normalize_sup_opp(row_sup_opp_cd)
        if stance is None and cover_sup_opp_cd:
            cover_prop = _clean_prop_num(cover_bal_num)
            if cover_prop == prop_num:
                stance = _normalize_sup_opp(cover_sup_opp_cd)
        return self._resolve_prop_with_dates(
            prop_num, stance, date_hints,
            method_name="row_fields",
        )

    # -- Manual override path ---------------------------------------

    def resolve_from_manual_override(self, filer_id: str,
                                     filer_name: str
                                     ) -> AttributionResult:
        """Lookup by filer_id first, then by normalized filer name.

        manual_overrides format: {key: [(cid, stance), ...]} where key
        is either a filer_id (str) or a normalized filer name (lower,
        whitespace-collapsed).
        """
        override = self.manual_overrides.get(filer_id)
        if not override:
            normalized = _normalize_name(filer_name)
            override = self.manual_overrides.get(normalized)
        if not override:
            return AttributionResult(
                quarantine_reason="filer_name_no_prop",
                attribution_method="failed",
                debug=[f"no manual override for {filer_id!r} / "
                       f"{filer_name!r}"],
            )
        if len(override) > 1:
            # Multi-prop manual override — Phase 4 row-fields can pick;
            # for filings without row-fields, quarantine
            return AttributionResult(
                quarantine_reason="ambiguous_multi_prop",
                attribution_method="failed",
                debug=[f"multi-target override: {override}"],
            )
        cid, stance = override[0]
        mdb = None
        # Look up measure_db_id from crosswalk if we have the cid
        for (_p, _y), (c, m) in self.crosswalk.items():
            if c == cid:
                mdb = m
                break
        return AttributionResult(
            finance_campaign_id=cid,
            source_crosswalk_campaign_id=cid,
            measure_db_id=mdb,
            stance=stance,
            attribution_method="manual_override",
        )

    # -- Shared year scoring helper ---------------------------------

    def _resolve_prop_with_dates(self, prop_num: str,
                                 stance: Optional[str],
                                 date_hints: Iterable[date | None],
                                 method_name: str) -> AttributionResult:
        candidates = self.props_by_num.get(prop_num, [])
        if not candidates:
            return AttributionResult(
                quarantine_reason="no_campaign_match",
                attribution_method="failed",
                debug=[f"prop {prop_num} not in v2 crosswalk"],
            )
        hint_years = [d.year for d in date_hints if d is not None]

        # No date hints + single candidate: attribute (legacy).
        # No date hints + multi candidate: ambiguous_year.
        if not hint_years:
            if len(candidates) == 1:
                year, cid, mdb = candidates[0]
                return AttributionResult(
                    finance_campaign_id=cid,
                    source_crosswalk_campaign_id=cid,
                    measure_db_id=mdb,
                    stance=stance,
                    attribution_method=method_name,
                    quarantine_reason=(
                        "unknown_stance" if stance is None else None
                    ),
                )
            return AttributionResult(
                quarantine_reason="ambiguous_year",
                attribution_method="failed",
                debug=[
                    f"prop {prop_num} has multiple candidates "
                    f"{[c[0] for c in candidates]}; no date hints",
                ],
            )

        # MULTI-CANDIDATE: strict +/- 1 year first. If no strict
        # match, try wind-down windows (Codex round-9 extension).
        # Wind-down accepts only if exactly one candidate's window
        # [year-1, year+4] contains a hint AND no other candidate's
        # window does. TABS Yes on Prop. 39 2002 case: only PROP_39_2000
        # window contains 2002, not PROP_39_2012's window -> accept.
        if len(candidates) > 1:
            plausible = [
                (year, cid, mdb)
                for (year, cid, mdb) in candidates
                if any(abs(h - year) <= 1 for h in hint_years)
            ]
            if len(plausible) == 1:
                year, cid, mdb = plausible[0]
                return AttributionResult(
                    finance_campaign_id=cid,
                    source_crosswalk_campaign_id=cid,
                    measure_db_id=mdb,
                    stance=stance,
                    attribution_method=method_name,
                    quarantine_reason=(
                        "unknown_stance" if stance is None else None
                    ),
                )
            if len(plausible) > 1:
                # Multiple strict candidates — strictly ambiguous, no
                # safe recovery
                return AttributionResult(
                    quarantine_reason="ambiguous_year",
                    attribution_method="failed",
                    debug=[
                        f"prop {prop_num}: multi-candidate "
                        f"{[c[0] for c in candidates]} for hints "
                        f"{hint_years}; "
                        f"multiple strict plausible={[p[0] for p in plausible]}",
                    ],
                )
            # 0 strict candidates — try multi-candidate wind-down rule.
            winddown_plausible = [
                (year, cid, mdb)
                for (year, cid, mdb) in candidates
                if any((year - 1) <= h <= (year + 4) for h in hint_years)
            ]
            if len(winddown_plausible) == 1:
                year, cid, mdb = winddown_plausible[0]
                method = (
                    "filer_name_explicit_multi_candidate_winddown"
                    if method_name == "filer_name_explicit"
                    else f"{method_name}_multi_cand_winddown"
                )
                return AttributionResult(
                    finance_campaign_id=cid,
                    source_crosswalk_campaign_id=cid,
                    measure_db_id=mdb,
                    stance=stance,
                    attribution_method=method,
                    quarantine_reason=(
                        "unknown_stance" if stance is None else None
                    ),
                    debug=[
                        f"multi-cand wind-down: prop {prop_num} "
                        f"candidates {[c[0] for c in candidates]}, "
                        f"hints {hint_years}, "
                        f"winddown_plausible={year}",
                    ],
                )
            return AttributionResult(
                quarantine_reason="ambiguous_year",
                attribution_method="failed",
                debug=[
                    f"prop {prop_num}: multi-candidate "
                    f"{[c[0] for c in candidates]} for hints "
                    f"{hint_years}; "
                    f"no strict, winddown_plausible="
                    f"{[p[0] for p in winddown_plausible]}",
                ],
            )

        # SINGLE-CANDIDATE: bounded wind-down rule (Codex round-7).
        # Window is [election_year - 1, election_year + 4]. A 2005
        # campaign's committee continues filing through 2007-2009 for
        # wind-down activity. Those count. A 1978 prop's "ongoing
        # legacy" 2026 activity (PROTECT PROP. 13 / Howard Jarvis)
        # falls outside the window and quarantines as
        # single_candidate_stale_out_of_window.
        #
        # Within +/- 1: regular attribution method (in-cycle).
        # Within wind-down window only: distinct method so audits can
        #   quantify the recovery.
        # Outside both: quarantine.
        year, cid, mdb = candidates[0]
        within_strict = any(abs(h - year) <= 1 for h in hint_years)
        within_winddown = any((year - 1) <= h <= (year + 4)
                              for h in hint_years)
        if within_strict:
            return AttributionResult(
                finance_campaign_id=cid,
                source_crosswalk_campaign_id=cid,
                measure_db_id=mdb,
                stance=stance,
                attribution_method=method_name,
                quarantine_reason=(
                    "unknown_stance" if stance is None else None
                ),
            )
        if within_winddown:
            # Promote method name to mark the wind-down recovery path
            if method_name == "filer_name_explicit":
                recovery_method = "single_crosswalk_candidate_winddown"
            else:
                recovery_method = f"{method_name}_winddown"
            return AttributionResult(
                finance_campaign_id=cid,
                source_crosswalk_campaign_id=cid,
                measure_db_id=mdb,
                stance=stance,
                attribution_method=recovery_method,
                quarantine_reason=(
                    "unknown_stance" if stance is None else None
                ),
                debug=[
                    f"single-candidate wind-down: prop {prop_num} "
                    f"year={year}, hints={hint_years}",
                ],
            )
        return AttributionResult(
            quarantine_reason="single_candidate_stale_out_of_window",
            attribution_method="failed",
            debug=[
                f"prop {prop_num}: single candidate year={year}, "
                f"all hints {hint_years} outside [-1, +4] window",
            ],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_sup_opp(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    val = raw.strip().upper()
    if val == "S":
        return "support"
    if val == "O":
        return "oppose"
    return None


def _normalize_name(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


# Codex round-13: field-specific ambiguity detection.
# BAL_NUM and BAL_NAME have different acceptable shapes.
# BAL_NUM is supposed to be a structured ID; commas, slashes, etc. are
# meaningful. BAL_NAME is free text; stray punctuation is normal.

# BAL_NUM-strict patterns:
_BALNUM_SEPARATORS = re.compile(r"[/&,]|\d+\s+\d+|\d+\s*(?:AND|&)\s*\d+",
                                 re.IGNORECASE)
_AG_QUEUE_PATTERN = re.compile(r"^\d{2}-\d{3,5}$")
# Broader hyphenated tracking IDs Codex round-13 flagged:
# 2024-001, 2024-V1, 24-V1, 2024-N1, RM-4, MM-A, etc.
_TRACKING_ID_PATTERN = re.compile(
    r"^\d{2,4}-[A-Z0-9]+$|^[A-Z]+-\d+$",
    re.IGNORECASE,
)
_LOCAL_PREFIX = re.compile(r"^(RM|MM|MEAS|LOC)[/\s-]", re.IGNORECASE)

# BAL_NAME-semantic patterns:
# - Numeric multi-prop with explicit indicators (digit-flanked separators)
# - Regional / local / bay area measure phrases
_BALNAME_NUMERIC_MULTI = re.compile(
    r"\d+\s*/\s*\d+|\d+\s*&\s*\d+|\d+\s+(?:AND)\s+\d+|"
    r"\bPROPS?\s+(?:\d+[A-Z]?\s*(?:,|AND|&)\s*\d+)",
    re.IGNORECASE,
)
_NONSTATEWIDE_MEASURE = re.compile(
    r"\b(REGIONAL|MUNICIPAL|LOCAL|COUNTY|CITY|BAY\s+AREA(\s+REGIONAL)?)"
    r"\s+MEASURE\b|"
    r"\bBAY\s+AREA\s+REGIONAL\s+(MEASURE|BOND|HOUSING)\b|"
    r"\b(REGIONAL|MUNICIPAL|LOCAL)\s+(BOND|HOUSING)\b",
    re.IGNORECASE,
)

_SIMPLE_PROP = re.compile(r"^(\d+[A-Z]?)$")
_PROP_PREFIXED = re.compile(r"^PROP(?:OSITION)?\.?\s*(\d+[A-Z]?)$",
                             re.IGNORECASE)


def has_ambiguous_bal_num(raw: Optional[str]) -> bool:
    """Detect non-clean BAL_NUM values that signal multi-prop /
    non-statewide / tracking-ID semantics. Strict — any separator
    or non-prop ID pattern fires.

    Codex round-13: split from the prior unified helper because
    BAL_NAME is free text and shouldn't follow the same strict rules.
    """
    if not raw:
        return False
    s = raw.strip()
    if not s:
        return False
    if _BALNUM_SEPARATORS.search(s):
        return True
    if _LOCAL_PREFIX.match(s):
        return True
    return False


def has_ambiguous_bal_name(raw: Optional[str]) -> bool:
    """Detect BAL_NAME values that signal multi-prop or non-statewide.
    Semantic — looks at the WORDS not just punctuation.

    Codex round-13: free-text names like 'Proposition 61, State
    Prescription Drug Purchases' contain commas but ARE clean
    single-prop refs. Use word-level patterns instead.
    """
    if not raw:
        return False
    s = raw.strip()
    if not s:
        return False
    if _BALNAME_NUMERIC_MULTI.search(s):
        return True
    if _NONSTATEWIDE_MEASURE.search(s):
        return True
    return False


# Backwards-compat alias: callers that did has_multi_prop_signal
# (which was previously a unified helper) get the BAL_NUM-strict
# behavior. New code should call the field-specific helpers.
def has_multi_prop_signal(raw: Optional[str]) -> bool:
    return has_ambiguous_bal_num(raw)


def _clean_prop_num(raw: Optional[str]) -> Optional[str]:
    """Extract a clean prop number from a CAL-ACCESS BAL_NUM-style value.

    Codex rounds 11/12/13: reject anything that isn't a simple
    statewide prop reference. Specifically rejects:
    - AG queue patterns ('19-0026')
    - Broader hyphenated tracking IDs ('2024-V1', '24-N1', 'RM-4')
    - Multi-prop signals ('/', '&', ',', digit-flanked AND)
    - Local prefixes (RM/, MM/, MEAS-, LOC-)

    Returns clean prop number (e.g. '27', '1A') if value is a clean
    single statewide prop. None otherwise.
    """
    if not raw:
        return None
    cleaned = raw.strip().upper()
    if _AG_QUEUE_PATTERN.match(cleaned):
        return None
    if _TRACKING_ID_PATTERN.match(cleaned):
        return None
    if has_ambiguous_bal_num(cleaned):
        return None
    m = _SIMPLE_PROP.match(cleaned)
    if m:
        return m.group(1).lstrip("0") or "0"
    m = _PROP_PREFIXED.match(cleaned)
    if m:
        return m.group(1).lstrip("0") or "0"
    return None


def _extract_prop_from_name(name: Optional[str]) -> Optional[str]:
    """Extract a single prop number from a free-form BAL_NAME.

    Codex rounds 12/13: reject multi-prop names ('Proposition 26/27',
    'Yes on 25 & 26'), non-statewide measure prefixes ('Regional
    Measure 4', 'Bay Area Regional Housing Bond').
    """
    if not name:
        return None
    if has_ambiguous_bal_name(name):
        return None
    m = re.search(
        r"PROP(?:OSITION)?\s*[#]?\s*0*(\d+[A-Z]?)",
        name,
        re.IGNORECASE,
    )
    return m.group(1).upper() if m else None
