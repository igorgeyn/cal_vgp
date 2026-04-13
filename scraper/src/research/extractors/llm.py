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
                 rate_limit_delay: float = 0.5):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model
        self.rate_limit_delay = rate_limit_delay

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

        prompt = f"""You are writing a voter briefing for a California ballot measure.
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
        """Format historical context for the synthesis prompt."""
        if not ctx:
            return ""

        lines = ["### Historical Context (from CalBallot database):"]

        topic_stats = ctx.get('topic_stats', {})
        if topic_stats.get('by_type'):
            t = topic_stats['by_type']
            lines.append(f"- {t['type']} measures: {t['total']} voted on since 1998, "
                         f"{t['pass_rate']}% pass rate, avg {t['avg_yes']}% YES")

        threshold = ctx.get('threshold_context', {})
        if threshold:
            lines.append(f"- This measure requires {threshold.get('threshold_label', '50%')} to pass")
            if threshold.get('trap_rate', 0) > 0:
                lines.append(f"- {threshold['trap_rate']}% of similar measures won majority support "
                             f"but failed due to supermajority requirement")

        trend = ctx.get('temporal_trend', [])
        if len(trend) >= 2:
            first = trend[0]
            last = trend[-1]
            lines.append(f"- Pass rate trend: {first['pass_rate']}% in {first['decade']}s → "
                         f"{last['pass_rate']}% in {last['decade']}s")

        similar = ctx.get('similar_measures', [])
        if similar:
            lines.append(f"- {len(similar)} semantically similar past measures found")

        return "\n".join(lines)
