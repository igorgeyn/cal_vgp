"""
Generate standalone markdown reports from research briefings.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict

REPORTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "analysis" / "reports"


def generate_report(measure: Dict, briefing: Dict, sources_consulted: list) -> str:
    """Generate a markdown report for a single measure."""
    title = measure.get('title', 'Unknown Measure')
    measure_id = measure.get('measure_id', '')
    year = measure.get('year', '')
    county = measure.get('county', 'Statewide')
    cat_type = measure.get('category_type', '')

    # Status
    if measure.get('passed') == 1:
        status = "Passed"
    elif measure.get('passed') == 0:
        status = "Failed"
    else:
        status = "Pending — on the ballot"

    md = f"""# {title}

**ID:** {measure_id}
**Year:** {year}
**Jurisdiction:** {county}, California
**Type:** {cat_type}
**Status:** {status}

---

"""

    # Sections from briefing
    sections = [
        ("What It Does", briefing.get("what_it_does")),
        ("Why It's on the Ballot", briefing.get("why_on_ballot")),
        ("Fiscal Impact", briefing.get("fiscal_impact")),
        ("Arguments For", briefing.get("pro_arguments")),
        ("Arguments Against", briefing.get("con_arguments")),
        ("Proponents", briefing.get("proponents")),
        ("Opponents", briefing.get("opponents")),
        ("Historical Context", briefing.get("historical_context")),
        ("Expert Analysis", briefing.get("expert_analysis")),
    ]

    for heading, content in sections:
        if not content or content == "Not yet available.":
            md += f"## {heading}\n\n*Not yet available.*\n\n"
            continue

        md += f"## {heading}\n\n"
        if isinstance(content, list):
            for item in content:
                md += f"- {item}\n"
            md += "\n"
        else:
            md += f"{content}\n\n"

    # Key links
    md += "## Key Sources\n\n"
    for source in sources_consulted:
        if isinstance(source, dict):
            md += f"- [{source.get('name', 'Source')}]({source.get('url', '#')})\n"
        else:
            md += f"- {source}\n"

    md += f"""
---

*Researched by CalBallot Research Agent on {datetime.now().strftime('%Y-%m-%d')}*
*Sources: {', '.join(s.get('name', str(s)) if isinstance(s, dict) else str(s) for s in sources_consulted)}*
"""

    return md


def save_report(measure: Dict, briefing: Dict, sources_consulted: list) -> Path:
    """Generate and save a markdown report."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report = generate_report(measure, briefing, sources_consulted)

    # Clean measure_id for filename
    measure_id = measure.get('measure_id', 'unknown')
    import re
    safe_id = re.sub(r'[^A-Za-z0-9_-]', '_', str(measure_id))[:50]
    filepath = REPORTS_DIR / f"{safe_id}.md"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)

    return filepath
