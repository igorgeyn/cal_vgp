"""
CPI deflator for inflation-adjusted dollar comparisons.

Source: BLS CPI-U, annual average, U.S. city average (series CUUR0000SA0).
Pinned values; bump the table forward when a new annual average publishes.

Used by the briefing pipeline to translate historical fiscal figures into
present-day dollars when the synthesis step needs to compare a 1978 measure's
$X to a 2024 measure's $Y.
"""
from typing import Optional

# Annual average CPI-U, U.S. city average. Last verified: BLS series CUUR0000SA0.
CPI_BY_YEAR = {
    1970: 38.8,  1971: 40.5,  1972: 41.8,  1973: 44.4,  1974: 49.3,
    1975: 53.8,  1976: 56.9,  1977: 60.6,  1978: 65.2,  1979: 72.6,
    1980: 82.4,  1981: 90.9,  1982: 96.5,  1983: 99.6,  1984: 103.9,
    1985: 107.6, 1986: 109.6, 1987: 113.6, 1988: 118.3, 1989: 124.0,
    1990: 130.7, 1991: 136.2, 1992: 140.3, 1993: 144.5, 1994: 148.2,
    1995: 152.4, 1996: 156.9, 1997: 160.5, 1998: 163.0, 1999: 166.6,
    2000: 172.2, 2001: 177.1, 2002: 179.9, 2003: 184.0, 2004: 188.9,
    2005: 195.3, 2006: 201.6, 2007: 207.342, 2008: 215.303, 2009: 214.537,
    2010: 218.056, 2011: 224.939, 2012: 229.594, 2013: 232.957,
    2014: 236.736, 2015: 237.017, 2016: 240.007, 2017: 245.120,
    2018: 251.107, 2019: 255.657, 2020: 258.811, 2021: 270.970,
    2022: 292.655, 2023: 304.702, 2024: 313.689,
}

# Default base year for "today's dollars" — bump when CPI_BY_YEAR is extended.
BASE_YEAR = 2024


def to_base_dollars(amount: float, from_year: int,
                    base_year: int = BASE_YEAR) -> Optional[float]:
    """Convert an amount in `from_year` dollars to `base_year` dollars.

    Returns None when either year is outside the CPI table.
    """
    src = CPI_BY_YEAR.get(from_year)
    dst = CPI_BY_YEAR.get(base_year)
    if src is None or dst is None or src == 0:
        return None
    return amount * (dst / src)


def cpi_table_for_prompt(years: list, base_year: int = BASE_YEAR) -> str:
    """Format a small CPI lookup table for inclusion in an LLM prompt.

    Only includes years that appear in `years` and the base_year, so the
    prompt stays compact. The LLM is told it can use this to convert
    historical dollar figures.
    """
    relevant_years = sorted({y for y in years if y in CPI_BY_YEAR} | {base_year})
    if len(relevant_years) <= 1:
        return ""
    lines = [f"CPI-U annual average (U.S. city average), base year {base_year}:"]
    for y in relevant_years:
        cpi = CPI_BY_YEAR[y]
        deflator = CPI_BY_YEAR[base_year] / cpi if cpi else None
        if deflator:
            lines.append(f"- {y}: CPI={cpi:.3f} (multiply {y} dollars by {deflator:.3f} for {base_year} dollars)")
    return "\n".join(lines)
