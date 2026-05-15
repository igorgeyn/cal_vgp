"""Quick smoke tests for resolver.py.

Run: python scripts/v3/test_resolver.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from v3 import resolver


def main() -> int:
    failures: list[str] = []

    # Build a tiny crosswalk for testing
    crosswalk = {
        ("14", 2004): ("PROP_14_2004", 4001),
        ("14", 2020): ("PROP_14_2020", 4002),
        ("39", 2000): ("PROP_39_2000", 5001),
        ("39", 2012): ("PROP_39_2012", 5002),
        ("22", 2020): ("PROP_22_2020", 6001),
        ("27", 2022): ("PROP_27_2022", 7001),
        # 2005 Schwarzenegger reform props with matcher-v2 collision
        # pairs (same measure_db_id, year-offset alias from CalAccess
        # late filings labeled as 2006)
        ("74", 2005): ("PROP_74_2005", 7401),
        ("74", 2006): ("PROP_74_2006", 7401),  # collision: same mdb
        ("75", 2005): ("PROP_75_2005", 7501),
        ("75", 2006): ("PROP_75_2006", 7501),
        ("76", 2005): ("PROP_76_2005", 7601),
        ("76", 2006): ("PROP_76_2006", 7601),
        ("78", 2005): ("PROP_78_2005", 8001),
        ("78", 2006): ("PROP_78_2006", 8001),
        ("79", 2005): ("PROP_79_2005", 7901),
        ("79", 2006): ("PROP_79_2006", 7901),
        # Legacy single-candidate with 1978 year (Howard Jarvis test)
        ("13", 1978): ("PROP_13_1978", 9001),
        ("38", 2000): ("PROP_38_2000", 10001),
        ("30", 2012): ("PROP_30_2012", 11001),
        ("32", 2012): ("PROP_32_2012", 12001),
        # Multi-prop test fixtures (Yes on Props 1 and 2)
        ("1", 2024): ("PROP_1_2024", 13001),
        ("2", 2024): ("PROP_2_2024", 13002),
    }
    overrides = {
        "hold politicians accountable": [("PROP_54_2016", "support")],
    }
    # Match_via signals: year_offset rows are aliases of canonical
    match_via = {
        "PROP_74_2006": "year_offset_1_title_short",
        "PROP_75_2006": "year_offset_1_title_short",
        "PROP_76_2006": "year_offset_1_title_short",
        "PROP_78_2006": "year_offset_1_title_short",
        "PROP_79_2006": "year_offset_1_title_short",
    }
    R = resolver.AttributionResolver(crosswalk, overrides,
                                     match_via_by_cid=match_via)

    def check(label, predicate, *args):
        try:
            if not predicate(*args):
                failures.append(label)
                print(f"  FAIL: {label}")
            else:
                print(f"  pass: {label}")
        except Exception as e:
            failures.append(label)
            print(f"  ERROR: {label}: {e}")

    # --- Pattern extraction ---
    print("=== extract_prop_mentions ===")
    m = resolver.extract_prop_mentions("YES ON 14: CALIFORNIANS FOR STEM CELL")
    check("YES ON 14 -> support, 14",
          lambda: len(m) == 1 and m[0].prop_num == "14" and m[0].stance == "support")

    m = resolver.extract_prop_mentions("No on Prop. 39, a coalition of teachers")
    check("No on Prop. 39 -> oppose, 39",
          lambda: len(m) == 1 and m[0].prop_num == "39" and m[0].stance == "oppose")

    m = resolver.extract_prop_mentions("PROP38YES.COM, School Vouchers 2000")
    check("PROP38YES.COM -> support, 38",
          lambda: any(x.prop_num == "38" and x.stance == "support" for x in m))

    m = resolver.extract_prop_mentions("Small Business Action Committee PAC, No on 30/Yes on 32")
    props = {(x.prop_num, x.stance) for x in m}
    check("'No on 30 / Yes on 32' -> two distinct mentions",
          lambda: ("30", "oppose") in props and ("32", "support") in props)

    m = resolver.extract_prop_mentions("PROTECT PROP. 13, A PROJECT OF HOWARD JARVIS")
    check("PROTECT PROP. 13 -> 13 only, no stance",
          lambda: len(m) == 1 and m[0].prop_num == "13" and m[0].stance is None)

    m = resolver.extract_prop_mentions("HOLD POLITICIANS ACCOUNTABLE")
    check("HOLD POLITICIANS ACCOUNTABLE -> no mention",
          lambda: m == [])

    m = resolver.extract_prop_mentions("Californians for Affordable Prescriptions - Yes on Proposition 78")
    check("Yes on Proposition 78 -> support, 78",
          lambda: any(x.prop_num == "78" and x.stance == "support" for x in m))

    m = resolver.extract_prop_mentions("YES ON 1A: CALIFORNIANS FOR INDIAN SELF-RELIANCE")
    check("YES ON 1A -> 1A (suffix preserved)",
          lambda: len(m) == 1 and m[0].prop_num == "1A" and m[0].stance == "support")

    # Should NOT match bare numbers
    m = resolver.extract_prop_mentions("Stop the $2 Billion Tax Hike")
    check("'Stop the $2 Billion Tax Hike' -> no mention (no prop language)",
          lambda: m == [])

    m = resolver.extract_prop_mentions("Citizens for Reform 2020")
    check("'Citizens for Reform 2020' -> no mention (no prop language)",
          lambda: m == [])

    # --- Cover-sheet resolver ---
    print()
    print("=== resolve_from_cover_sheet ===")
    r = R.resolve_from_cover_sheet("22", 2020, "S")
    check("cover_sheet PROP 22 2020 S -> PROP_22_2020, support",
          lambda: r.resolved and r.finance_campaign_id == "PROP_22_2020"
                 and r.stance == "support"
                 and r.attribution_method == "cover_sheet")

    r = R.resolve_from_cover_sheet("999", 2020, "S")
    check("cover_sheet unknown prop -> no_campaign_match",
          lambda: r.quarantine_reason == "no_campaign_match")

    r = R.resolve_from_cover_sheet("22", 2020, "")
    check("cover_sheet known prop, blank stance -> unknown_stance",
          lambda: r.quarantine_reason == "unknown_stance"
                 and r.finance_campaign_id == "PROP_22_2020")

    r = R.resolve_from_cover_sheet(None, None, "S")
    check("cover_sheet blank prop/year -> bad_prop_or_year",
          lambda: r.quarantine_reason == "bad_prop_or_year")

    # --- Filer-name resolver ---
    print()
    print("=== resolve_from_filer_name ===")
    r = R.resolve_from_filer_name(
        "YES ON 14: CALIFORNIANS FOR STEM CELL",
        [date(2020, 9, 1)],
    )
    check("YES ON 14 + 2020 date -> PROP_14_2020, support",
          lambda: r.resolved and r.finance_campaign_id == "PROP_14_2020"
                 and r.stance == "support"
                 and r.attribution_method == "filer_name_explicit")

    r = R.resolve_from_filer_name(
        "YES ON 14: CALIFORNIANS FOR STEM CELL",
        [date(2004, 10, 1)],
    )
    check("YES ON 14 + 2004 date -> PROP_14_2004, support",
          lambda: r.resolved and r.finance_campaign_id == "PROP_14_2004"
                 and r.stance == "support")

    r = R.resolve_from_filer_name(
        "YES ON 14: CALIFORNIANS FOR STEM CELL",
        [],
    )
    check("YES ON 14, no date hints -> ambiguous_year",
          lambda: r.quarantine_reason == "ambiguous_year")

    r = R.resolve_from_filer_name(
        "No on 30 / Yes on 32",
        [date(2012, 9, 1)],
    )
    check("'No on 30 / Yes on 32' -> ambiguous_multi_prop",
          lambda: r.quarantine_reason == "ambiguous_multi_prop")

    r = R.resolve_from_filer_name(
        "HOLD POLITICIANS ACCOUNTABLE",
        [date(2016, 10, 1)],
    )
    check("HOLD POLITICIANS ACCOUNTABLE -> filer_name_no_prop",
          lambda: r.quarantine_reason == "filer_name_no_prop")

    r = R.resolve_from_filer_name(
        "PROTECT PROP. 13",
        [date(2026, 1, 1)],
    )
    check("PROTECT PROP. 13 + 2026 -> single_candidate_stale_out_of_window",
          lambda: r.quarantine_reason == "single_candidate_stale_out_of_window")

    # --- Golden cases from Codex round-7 ---
    print()
    print("=== Codex round-7 golden cases ===")

    # Schwarzenegger 2005 wind-down: filings continue through 2007-2009
    for prop in ("74", "75", "76", "78", "79"):
        r = R.resolve_from_filer_name(
            f"NO ON {prop} - Californians Against Bad Stuff",
            [date(2007, 6, 30)],  # post-election wind-down
        )
        check(f"NO ON {prop} + 2007 wind-down -> "
              f"single_crosswalk_candidate_winddown",
              lambda r=r, prop=prop:
                  r.resolved
                  and r.finance_campaign_id == f"PROP_{prop}_2005"
                  and r.stance == "oppose"
                  and r.attribution_method == "single_crosswalk_candidate_winddown")

    # In-cycle filings (within +/- 1) use the regular method name
    r = R.resolve_from_filer_name(
        "NO ON 79 - Californians Against Wrong Prescription",
        [date(2005, 9, 1)],
    )
    check("NO ON 79 + 2005 (in-cycle) -> filer_name_explicit",
          lambda: r.resolved
                 and r.attribution_method == "filer_name_explicit")

    # Out-of-window: stale single-candidate
    r = R.resolve_from_filer_name(
        "NO ON 79 - Californians Against Wrong Prescription",
        [date(2015, 1, 1)],
    )
    check("NO ON 79 + 2015 (>5 years off) -> stale_out_of_window",
          lambda: r.quarantine_reason == "single_candidate_stale_out_of_window")

    # Multi-candidate disambiguation
    r = R.resolve_from_filer_name(
        "YES ON 14 stem cell",
        [date(2020, 9, 1)],
    )
    check("YES ON 14 + 2020 -> PROP_14_2020 (multi-candidate -> 1 plausible)",
          lambda: r.resolved and r.finance_campaign_id == "PROP_14_2020")

    r = R.resolve_from_filer_name(
        "YES ON 14 stem cell",
        [date(2004, 10, 1)],
    )
    check("YES ON 14 + 2004 -> PROP_14_2004",
          lambda: r.resolved and r.finance_campaign_id == "PROP_14_2004")

    # Plural pattern: "Yes on Props 1 and 2" should NOT fall to
    # filer_name_no_prop — should be ambiguous_multi_prop
    print()
    print("=== Plural patterns (Codex round-7) ===")
    m = resolver.extract_prop_mentions(
        "Yes on Props 1 and 2, a bipartisan coalition"
    )
    props = {(x.prop_num, x.stance) for x in m}
    check("'Yes on Props 1 and 2' -> two support mentions",
          lambda: ("1", "support") in props and ("2", "support") in props)

    r = R.resolve_from_filer_name(
        "Yes on Props 1 and 2, a bipartisan coalition",
        [date(2024, 9, 1)],
    )
    check("'Yes on Props 1 and 2' -> ambiguous_multi_prop (not filer_name_no_prop)",
          lambda: r.quarantine_reason == "ambiguous_multi_prop")

    # Cautious patterns
    m = resolver.extract_prop_mentions("Californians Supporting Prop 50")
    check("'Supporting Prop 50' -> support, 50",
          lambda: any(x.prop_num == "50" and x.stance == "support" for x in m))

    m = resolver.extract_prop_mentions("Citizens for Proposition 4")
    check("'for Proposition 4' -> support, 4",
          lambda: any(x.prop_num == "4" and x.stance == "support" for x in m))

    # --- Collision-pair collapse (Codex round-7 root cause finding) ---
    print()
    print("=== Collision-pair collapse ===")
    # Crosswalk has PROP_79_2005 + PROP_79_2006 with same mdb=7901.
    # Without collapse: resolver sees 2 candidates and applies strict
    # +/- 1 logic, which fails when hints span both years.
    # With collapse: only PROP_79_2005 remains (lowest year), and the
    # single-candidate wind-down rule fires.
    r = R.resolve_from_filer_name(
        "NO ON 79 - Californians Against Wrong Prescription",
        [date(2005, 11, 8), date(2007, 12, 31)],  # elect + thru dates
    )
    check("NO ON 79 + [2005-11, 2007-12] -> PROP_79_2005 not ambiguous "
          "(collision pair collapsed)",
          lambda: r.resolved
                 and r.finance_campaign_id == "PROP_79_2005"
                 and r.stance == "oppose")

    # Genuine reuse (Prop 14 = different measure_db_ids in 2004 vs 2020)
    # should still be multi-candidate
    r = R.resolve_from_filer_name(
        "YES ON 14",
        [date(2020, 9, 1), date(2004, 9, 1)],  # both years as hints
    )
    check("YES ON 14 + [2020, 2004] -> ambiguous_year (genuine reuse "
          "stays multi-candidate)",
          lambda: r.quarantine_reason == "ambiguous_year")

    # --- Ampersand plural pattern (Codex round-9) ---
    print()
    print("=== Ampersand plural pattern ===")
    m = resolver.extract_prop_mentions("Affordable Housing Now - Yes on Props 1&2")
    props = {(x.prop_num, x.stance) for x in m}
    check("'Yes on Props 1&2' -> two support mentions",
          lambda: ("1", "support") in props and ("2", "support") in props)

    m = resolver.extract_prop_mentions("Yes on Props 1 & 2")
    props = {(x.prop_num, x.stance) for x in m}
    check("'Yes on Props 1 & 2' (spaces) -> two support mentions",
          lambda: ("1", "support") in props and ("2", "support") in props)

    m = resolver.extract_prop_mentions("Yes on Propositions 1A & 1B")
    props = {(x.prop_num, x.stance) for x in m}
    check("'Yes on Propositions 1A & 1B' -> two support mentions",
          lambda: ("1A", "support") in props and ("1B", "support") in props)

    # Critical NON-match: bare "Prop. 13 & R.J. Riordan" shouldn't
    # trigger plural (singular PROP, not PROPS)
    m = resolver.extract_prop_mentions(
        "PROTECT PROP. 13 & R.J. Riordan, A PROJECT OF HOWARD JARVIS"
    )
    # Should only find single "PROP. 13" without stance, NOT a plural
    # "PROP. 13 & R.J." match
    check("'PROP. 13 & R.J. Riordan' -> only single 13, no R.J. match",
          lambda: len(m) == 1 and m[0].prop_num == "13"
                 and m[0].stance is None)

    # --- Multi-candidate wind-down (Codex round-9) ---
    print()
    print("=== Multi-candidate wind-down ===")
    # TABS Yes on Prop. 39 2002 case: v2 has both PROP_39_2000 and
    # PROP_39_2012 (different mdb, genuine reuse). Hint year 2002:
    # - strict +/- 1 of 2000: NO (distance 2)
    # - strict +/- 1 of 2012: NO (distance 10)
    # - wind-down [1999, 2004] of 2000: YES
    # - wind-down [2011, 2016] of 2012: NO
    # Exactly 1 wind-down candidate -> accept PROP_39_2000
    r = R.resolve_from_filer_name(
        "TAXPAYERS YES ON PROP. 39",
        [date(2002, 2, 19)],
    )
    check("'YES ON PROP. 39' + 2002 (multi-candidate wind-down) -> "
          "PROP_39_2000 via multi_candidate_winddown method",
          lambda: r.resolved
                 and r.finance_campaign_id == "PROP_39_2000"
                 and r.attribution_method
                 == "filer_name_explicit_multi_candidate_winddown")

    # Negative case: hint outside both wind-down windows
    r = R.resolve_from_filer_name(
        "YES ON PROP. 39",
        [date(2025, 1, 1)],  # outside both 2000+4=2004 and 2012+4=2016
    )
    check("'YES ON PROP. 39' + 2025 -> ambiguous_year "
          "(neither wind-down window applies)",
          lambda: r.quarantine_reason == "ambiguous_year")

    # 2014 hint: distance 2 from 2012 (outside strict +/- 1), within
    # 2012's wind-down [2011, 2016]. Should go through multi-cand
    # wind-down path -> PROP_39_2012.
    r = R.resolve_from_filer_name(
        "YES ON PROP. 39",
        [date(2014, 1, 1)],
    )
    check("'YES ON PROP. 39' + 2014 (outside strict, in 2012 wind-down) -> "
          "PROP_39_2012 via multi_candidate_winddown",
          lambda: r.resolved
                 and r.finance_campaign_id == "PROP_39_2012"
                 and r.attribution_method
                 == "filer_name_explicit_multi_candidate_winddown")

    # --- AG queue number rejection (Codex round-11 bug fix) ---
    print()
    print("=== AG queue number rejection ===")
    from v3.resolver import _clean_prop_num
    check("'19-0026' -> None (AG queue, not prop 19)",
          lambda: _clean_prop_num("19-0026") is None)
    check("'11-0099' -> None (AG queue)",
          lambda: _clean_prop_num("11-0099") is None)
    check("'09-0104' -> None (AG queue)",
          lambda: _clean_prop_num("09-0104") is None)
    check("'27' -> '27' (real prop number)",
          lambda: _clean_prop_num("27") == "27")
    check("'1A' -> '1A' (real prop with suffix)",
          lambda: _clean_prop_num("1A") == "1A")
    check("'039' -> '39' (leading zero stripped)",
          lambda: _clean_prop_num("039") == "39")
    check("'2026' -> '2026' (4-digit number, no hyphen, NOT AG queue)",
          lambda: _clean_prop_num("2026") == "2026")

    # Row-fields path: row_bal_num is AG queue, should fall to row_bal_name
    r = R.resolve_from_row_fields(
        "19-0026", "Protect App-Based Drivers", "S",
        [date(2019, 10, 30)],
    )
    check("row_fields AG queue '19-0026' + name has no PROP keyword "
          "-> bad_prop_or_year (not misattributed to PROP_19)",
          lambda: r.quarantine_reason == "bad_prop_or_year")

    r = R.resolve_from_row_fields(
        "09-0104", "Proposition 23", "S",
        [date(2010, 10, 30)],
    )
    # Crosswalk doesn't have PROP_23_2010 in test fixture but the
    # important check is: it doesn't match PROP_9_2008 via "09" extract
    check("row_fields AG queue '09-0104' + 'Proposition 23' -> "
          "extracts 23 from name, not 9 from AG number",
          lambda: r.quarantine_reason == "no_campaign_match"
                 and any("prop 23" in str(d).lower() for d in r.debug))

    # --- Row-fields conditional stance fallback (Codex round-10) ---
    print()
    print("=== Row-fields conditional cover-stance fallback ===")

    # row prop + row stance: accept row
    r = R.resolve_from_row_fields("22", None, "O", [date(2020, 9, 1)])
    check("row_fields row prop=22 row stance=O -> PROP_22_2020 oppose",
          lambda: r.resolved and r.finance_campaign_id == "PROP_22_2020"
                 and r.stance == "oppose"
                 and r.attribution_method == "row_fields")

    # row prop, no row stance, cover prop matches: use cover stance
    r = R.resolve_from_row_fields(
        "22", None, None, [date(2020, 9, 1)],
        cover_bal_num="22", cover_sup_opp_cd="S",
    )
    check("row_fields row prop=22 no row stance + cover prop=22 cover S "
          "-> PROP_22_2020 support (cover stance used)",
          lambda: r.resolved and r.finance_campaign_id == "PROP_22_2020"
                 and r.stance == "support")

    # row prop, no row stance, cover prop DIFFERS: don't use cover stance
    r = R.resolve_from_row_fields(
        "22", None, None, [date(2020, 9, 1)],
        cover_bal_num="27", cover_sup_opp_cd="S",  # cover is Prop 27, row is 22
    )
    check("row_fields row prop=22 no row stance + cover prop=27 -> "
          "unknown_stance (cover prop differs from row prop)",
          lambda: r.quarantine_reason == "unknown_stance")

    # row prop, no row stance, no cover info: unknown_stance
    r = R.resolve_from_row_fields("22", None, None, [date(2020, 9, 1)])
    check("row_fields row prop=22 no stance + no cover -> unknown_stance",
          lambda: r.quarantine_reason == "unknown_stance")

    # --- Cover-sheet canonicalization (Codex round-8 fix) ---
    print()
    print("=== Cover-sheet canonicalization ===")
    # Cover sheet hits the alias PROP_79_2006 directly. Should remap
    # to canonical PROP_79_2005 with source_crosswalk_campaign_id
    # preserving the original match.
    r = R.resolve_from_cover_sheet("79", 2006, "O")
    check("Cover_sheet (79, 2006, O) -> canonical PROP_79_2005, "
          "source=PROP_79_2006",
          lambda: r.resolved
                 and r.finance_campaign_id == "PROP_79_2005"
                 and r.source_crosswalk_campaign_id == "PROP_79_2006"
                 and r.stance == "oppose")

    # Cover sheet hits canonical directly — source equals canonical
    r = R.resolve_from_cover_sheet("79", 2005, "O")
    check("Cover_sheet (79, 2005, O) -> PROP_79_2005, source=PROP_79_2005",
          lambda: r.resolved
                 and r.finance_campaign_id == "PROP_79_2005"
                 and r.source_crosswalk_campaign_id == "PROP_79_2005")

    # --- Manual override ---
    print()
    print("=== resolve_from_manual_override ===")
    r = R.resolve_from_manual_override("12345", "HOLD POLITICIANS ACCOUNTABLE")
    check("manual override by name -> PROP_54_2016",
          lambda: r.resolved
                 and r.finance_campaign_id == "PROP_54_2016"
                 and r.attribution_method == "manual_override")

    r = R.resolve_from_manual_override("12345", "Some Random Committee")
    check("no manual override -> filer_name_no_prop",
          lambda: r.quarantine_reason == "filer_name_no_prop")

    print()
    if failures:
        print(f"=== {len(failures)} FAILURES ===")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"=== All tests pass ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
