"""
LLM-powered extraction and synthesis for ballot measure research.

Uses Claude to:
1. Extract structured facts from source documents
2. Synthesize all collected facts into a coherent briefing
"""
import json
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMExtractor:
    """Extracts structured information from documents using Claude."""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514",
                 rate_limit_delay: float = 0.5,
                 spec_text: Optional[str] = None,
                 spec_version: Optional[str] = None,
                 spec_hash: Optional[str] = None):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model
        self.rate_limit_delay = rate_limit_delay
        self.spec_text = spec_text
        self.spec_version = spec_version or "missing"
        self.spec_hash = spec_hash or "missing"

    def _call(self, prompt: str, max_tokens: int = 2000) -> str:
        """Call Claude API with rate limiting and error handling."""
        time.sleep(self.rate_limit_delay)
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return resp.content[0].text.strip()
        except Exception as e:
            if "overloaded" in str(e).lower() or "529" in str(e):
                logger.warning(f"API overloaded, waiting 60s...")
                time.sleep(60)
                # Retry once
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
                return resp.content[0].text.strip()
            raise

    def extract_from_document(self, document_text: str, source_name: str,
                              measure_title: str) -> Dict:
        """Extract structured facts from a single source document."""
        prompt = f"""You are analyzing a source document about a California ballot measure.

Measure: {measure_title}
Source: {source_name}

Document text:
{document_text[:8000]}

Extract the following structured information. For each field, only include it if the document provides clear evidence. Return valid JSON.

{{
    "what_it_does": "plain-language explanation of what this measure would do if passed (2-3 sentences)",
    "why_on_ballot": "who put it on the ballot and why (1-2 sentences, or null)",
    "fiscal_impact": "cost/revenue estimate if mentioned (1-2 sentences, or null)",
    "pro_arguments": ["list of arguments in favor mentioned in this source"],
    "con_arguments": ["list of arguments against mentioned in this source"],
    "proponents": ["list of named proponents/supporters"],
    "opponents": ["list of named opponents"],
    "key_facts": ["other important facts from this source"],
    "source_quality": "high/medium/low — how authoritative is this source for this measure?"
}}

Return ONLY the JSON, no preamble or explanation."""

        try:
            response = self._call(prompt, max_tokens=1500)
            # Parse JSON from response (handle markdown code blocks)
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(cleaned)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse extraction from {source_name}: {e}")
            return {}

    def synthesize_briefing(self, measure: Dict, facts: List[Dict],
                            historical_context: Dict) -> Dict:
        """Synthesize all collected facts into a structured briefing."""

        # Format historical context
        hist_text = self._format_historical_context(historical_context)

        # Format collected facts
        facts_text = ""
        for f in facts:
            if f.get('source'):
                facts_text += f"\n\n### From {f['source']}:\n"
                for key, val in f.get('extracted', {}).items():
                    if val and val != 'null':
                        facts_text += f"- **{key}**: {val}\n"

        measure_title = measure.get('title', 'Unknown measure')
        measure_type = measure.get('category_type', '')
        county = measure.get('county', 'Statewide')

        spec_section = ""
        if self.spec_text:
            spec_section = (
                "You are governed by the following editorial spec. This is the "
                "production standard for every briefing. Follow every rule. "
                "Output that violates the spec will be rejected and regenerated.\n\n"
                "---BEGIN SPEC---\n"
                f"{self.spec_text}\n"
                "---END SPEC---\n\n"
            )

        prompt = f"""{spec_section}You are writing a voter briefing for a California ballot measure.
Your job is to synthesize all available information into a clear, neutral, source-attributed briefing.

Measure: {measure_title}
Type: {measure_type}
Jurisdiction: {county}

{facts_text}

{hist_text}

Write a structured briefing with these sections. For each section, cite the source in parentheses.
If no information is available for a section, write "Not yet available."
Be neutral — present both sides fairly. Be specific — use names, numbers, dates.

Return valid JSON:

{{
    "what_it_does": "2-3 sentence plain-language explanation",
    "why_on_ballot": "1-2 sentences on political context and who put it there",
    "fiscal_impact": "fiscal impact summary with source",
    "pro_arguments": ["argument 1 (source)", "argument 2 (source)"],
    "con_arguments": ["argument 1 (source)", "argument 2 (source)"],
    "proponents": ["name/org 1", "name/org 2"],
    "opponents": ["name/org 1", "name/org 2"],
    "historical_context": "2-3 sentences on how similar measures have fared in California",
    "expert_analysis": "key analytical points from nonpartisan sources",
    "briefing_summary": "4-6 sentence comprehensive summary suitable for a voter guide"
}}

Return ONLY the JSON."""

        try:
            response = self._call(prompt, max_tokens=2000)
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(cleaned)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to synthesize briefing: {e}")
            return {"briefing_summary": f"Briefing generation failed: {e}"}

    def _format_historical_context(self, ctx: Dict) -> str:
        """Format historical context for the synthesis prompt.

        Surfaces everything assembled by historical.get_historical_context:
        topic stats, threshold context (with bucketed breakdown), temporal
        trend, concrete similar measures with outcomes, same-jurisdiction
        history, same-ballot companions, and a CPI deflator table.
        """
        if not ctx:
            return ""

        sections = []

        # Aggregate topic stats
        agg_lines = ["### Aggregate context"]
        topic_stats = ctx.get('topic_stats', {}) or {}
        if topic_stats.get('by_type'):
            t = topic_stats['by_type']
            agg_lines.append(
                f"- {t['type']} measures: {t['total']} voted on since 1998, "
                f"{t['pass_rate']}% pass rate, avg {t['avg_yes']}% YES."
            )
        if topic_stats.get('by_topic'):
            t = topic_stats['by_topic']
            agg_lines.append(
                f"- Same topic ({t['topic']}): {t['total']} measures, "
                f"{t['pass_rate']}% pass rate, avg {t['avg_yes']}% YES."
            )
        for b in topic_stats.get('by_threshold') or []:
            agg_lines.append(
                f"- At {b['threshold_label']} threshold: n={b['total']}, "
                f"pass rate {b['pass_rate']}%, avg YES {b['avg_yes']}%."
            )
        if len(agg_lines) > 1:
            sections.append("\n".join(agg_lines))

        # Threshold + trap-rate context
        threshold = ctx.get('threshold_context') or {}
        if threshold:
            t_lines = ["### Threshold"]
            t_lines.append(
                f"- This measure requires {threshold.get('threshold_label', '50%')} to pass."
            )
            if threshold.get('trap_rate', 0) > 0:
                t_lines.append(
                    f"- {threshold['trap_rate']}% of similar measures won majority support "
                    f"but failed due to supermajority requirement."
                )
            sections.append("\n".join(t_lines))

        # Temporal trend
        trend = ctx.get('temporal_trend') or []
        if len(trend) >= 2:
            first, last = trend[0], trend[-1]
            sections.append(
                f"### Trend\n- Pass rate by decade: {first['pass_rate']}% in {first['decade']}s "
                f"-> {last['pass_rate']}% in {last['decade']}s."
            )

        # Concrete similar measures (the spec requires content, not counts)
        similar = ctx.get('similar_measures') or []
        if similar:
            sim_lines = ["### Semantically similar past measures (concrete examples)"]
            for s in similar:
                outcome = {1: 'PASSED', 0: 'FAILED', None: 'unknown'}.get(s.get('passed'), 'unknown')
                py = s.get('percent_yes')
                py_str = f"{py:.1f}% YES" if py is not None else "vote unknown"
                close = " (CLOSE — within 5pts of threshold)" if s.get('is_close') else ""
                county = s.get('county') or 'Statewide'
                title = (s.get('title') or '').strip()
                title_excerpt = title[:90] + ('...' if len(title) > 90 else '')
                sim_lines.append(
                    f"- {s['year']} {county} ({s['measure_id']}): {outcome}, {py_str}{close}. {title_excerpt}"
                )
            sections.append("\n".join(sim_lines))

        # Same-jurisdiction history
        history = ctx.get('same_jurisdiction_history') or []
        if history:
            h_lines = ["### Prior measures of the same type in this jurisdiction"]
            for h in history:
                outcome = {1: 'PASSED', 0: 'FAILED', None: 'unknown'}.get(h.get('passed'), 'unknown')
                py = h.get('percent_yes')
                py_str = f"{py:.1f}% YES" if py is not None else "vote unknown"
                title_excerpt = (h.get('title') or '')[:80]
                h_lines.append(f"- {h['year']} {h['measure_id']}: {outcome}, {py_str}. {title_excerpt}")
            sections.append("\n".join(h_lines))

        # Same-ballot companions (what voters saw alongside this measure)
        companions = ctx.get('same_ballot_companions') or []
        if companions:
            c_lines = ["### Other measures on the same ballot"]
            for c in companions:
                outcome = {1: 'PASSED', 0: 'FAILED', None: 'pending'}.get(c.get('passed'), 'pending')
                py = c.get('percent_yes')
                py_str = f"{py:.1f}% YES" if py is not None else ""
                cat = c.get('category_type') or ''
                title_excerpt = (c.get('title') or '')[:60]
                c_lines.append(f"- {c['measure_id']} ({cat}): {outcome} {py_str}. {title_excerpt}")
            sections.append("\n".join(c_lines))

        # Statewide CA precedent on this topic (1911-2018 NCSL/Ballotpedia)
        cross = ctx.get('cross_state_history') or {}
        if cross:
            agg = cross.get('aggregate') or {}
            recent = cross.get('recent') or []
            cs_lines = ["### Statewide CA precedent on this topic"]
            if agg:
                flags = ', '.join(f.replace('is_', '') for f in agg.get('matched_flags', []))
                cs_lines.append(
                    f"- Matched topic(s): {flags}. {agg['n']} statewide CA measures "
                    f"({agg['first_year']}-{agg['last_year']}), pass rate {agg['pass_rate']}%, "
                    f"avg YES {agg['avg_yes']}%."
                )
            for r in recent:
                outcome = {1: 'PASSED', 0: 'FAILED', None: 'unknown'}.get(r.get('passed'), 'unknown')
                py = r.get('pct_yes')
                py_str = f"{py:.1f}% YES" if py is not None else "vote unknown"
                close = " (CLOSE)" if r.get('is_very_close') else ""
                desc = (r.get('description') or '').strip()
                desc_excerpt = desc[:90] + ('...' if len(desc) > 90 else '')
                cs_lines.append(
                    f"- {r['year']} {r['name']}: {outcome}, {py_str}{close}. {desc_excerpt}"
                )
            sections.append("\n".join(cs_lines))

        # CPI deflator table for inflation-adjusted comparisons
        cpi_table = ctx.get('cpi_table')
        if cpi_table:
            sections.append("### Inflation adjustment\n" + cpi_table)

        # Census/ACS demographics for per-household fiscal translation
        demographics = ctx.get('demographics')
        if demographics:
            from src.research.sources.census import format_demographics_for_prompt
            block = format_demographics_for_prompt(demographics)
            if block:
                sections.append("### Demographics for per-household translation\n" + block)

        # Election-cycle context: presidential / midterm / off-year / special
        cycle = ctx.get('election_cycle') or {}
        if cycle.get('current_cycle'):
            cy_lines = ["### Election-cycle context"]
            cy_lines.append(
                f"- This measure appears in a {cycle['current_cycle_label']}. "
                f"Cycle type strongly affects who turns out to vote."
            )
            for b in cycle.get('by_cycle') or []:
                marker = " (this cycle)" if b['cycle'] == cycle['current_cycle'] else ""
                avg = f"{b['avg_yes']}% avg YES" if b.get('avg_yes') else "avg YES n/a"
                cy_lines.append(
                    f"- {b['cycle_label']}{marker}: n={b['n']}, "
                    f"pass rate {b['pass_rate']}%, {avg}."
                )
            if len(cy_lines) > 1:
                sections.append("\n".join(cy_lines))

        # Author / sponsor track record (legislatively-referred measures)
        author_ctx = ctx.get('author_history') or {}
        if author_ctx.get('author'):
            ah_lines = ["### Author / sponsor track record"]
            ah_lines.append(
                f"- This measure ({author_ctx.get('leg_id') or 'this measure'}) "
                f"was authored / sponsored by {author_ctx['author']}."
            )
            prior = author_ctx.get('prior_measures') or []
            if prior:
                ah_lines.append(f"- {len(prior)} prior measure(s) by the same author:")
                for p in prior:
                    outcome = {1: 'PASSED', 0: 'FAILED', None: 'unknown'}.get(p.get('passed'), 'unknown')
                    py = p.get('percent_yes')
                    py_str = f", {py:.1f}% YES" if py is not None else ""
                    title_excerpt = (p.get('title') or '')[:80]
                    ah_lines.append(f"  - {p['year']} {p['leg_id']}: {outcome}{py_str}. {title_excerpt}")
            else:
                ah_lines.append("- No prior measures by this author found in the database.")
            sections.append("\n".join(ah_lines))

        if not sections:
            return ""
        return "### Historical Context (from CalBallot database)\n\n" + "\n\n".join(sections)
