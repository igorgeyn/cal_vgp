"""
Database operations for historical ballot measures
Provides query methods for API endpoints and UI components
"""
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .historical_schema import TOPIC_CONFIG, MIN_MEASURES_FOR_FILTER

logger = logging.getLogger(__name__)


@dataclass
class TopicContext:
    """Historical context for a topic."""
    topic: str
    topic_label: str
    total_measures: int
    first_year: int
    last_year: int
    pass_rate: float  # 0-1 scale
    avg_yes_pct: float
    passed_count: int
    failed_count: int
    most_recent: Optional[Dict[str, Any]] = None


@dataclass
class HistoricalMeasure:
    """A historical ballot measure."""
    id: int
    ballot_name: str
    year: int
    description: str
    pct_yes: Optional[float]
    passed: Optional[bool]
    measure_type: str
    election_type: str
    topics: List[str]  # All applicable topic keys
    primary_topic: Optional[str]  # Highest priority topic
    margin: Optional[float]
    is_close: bool
    margin_label: str  # "Landslide", "Comfortable", "Close", "Very Close"


class HistoricalDatabase:
    """Database operations for historical ballot measures."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn = None

    def connect(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_topic_context(self, topic: str, min_year: int = 1970) -> Optional[TopicContext]:
        """
        Get historical context for a topic.

        Args:
            topic: Topic key (e.g., 'marijuana', 'gambling')
            min_year: Minimum year to include (default 1970)

        Returns:
            TopicContext with statistics and most recent measure
        """
        if topic not in TOPIC_CONFIG:
            logger.warning(f"Unknown topic: {topic}")
            return None

        config = TOPIC_CONFIG[topic]
        column = config['column']

        conn = self.connect()

        # Get aggregate statistics
        cursor = conn.execute(f"""
            SELECT
                COUNT(*) as total_measures,
                MIN(year) as first_year,
                MAX(year) as last_year,
                SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed_count,
                SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as failed_count,
                AVG(CASE WHEN passed IS NOT NULL THEN
                    CASE WHEN passed = 1 THEN 1.0 ELSE 0.0 END
                END) as pass_rate,
                AVG(pct_yes) as avg_yes_pct
            FROM ca_historical_measures
            WHERE {column} = 1 AND year >= ?
        """, (min_year,))

        row = cursor.fetchone()
        if not row or row['total_measures'] == 0:
            return None

        # Get most recent measure
        cursor = conn.execute(f"""
            SELECT
                id, ballot_name, year, description, pct_yes, passed, margin
            FROM ca_historical_measures
            WHERE {column} = 1 AND year >= ?
            ORDER BY year DESC
            LIMIT 1
        """, (min_year,))

        recent_row = cursor.fetchone()
        most_recent = None
        if recent_row:
            most_recent = {
                'id': recent_row['id'],
                'ballot_name': recent_row['ballot_name'],
                'year': recent_row['year'],
                'description': recent_row['description'][:100] + '...' if len(recent_row['description'] or '') > 100 else recent_row['description'],
                'pct_yes': recent_row['pct_yes'],
                'passed': bool(recent_row['passed']) if recent_row['passed'] is not None else None,
                'margin': recent_row['margin'],
            }

        return TopicContext(
            topic=topic,
            topic_label=config['label'],
            total_measures=row['total_measures'],
            first_year=row['first_year'],
            last_year=row['last_year'],
            pass_rate=row['pass_rate'] or 0.0,
            avg_yes_pct=row['avg_yes_pct'] or 0.0,
            passed_count=row['passed_count'] or 0,
            failed_count=row['failed_count'] or 0,
            most_recent=most_recent
        )

    def get_all_topic_stats(self, min_year: int = 1970) -> List[Dict[str, Any]]:
        """
        Get statistics for all topics.

        Returns list sorted by priority order, filtered to topics with >= MIN_MEASURES.
        """
        results = []

        for topic, config in sorted(TOPIC_CONFIG.items(), key=lambda x: x[1]['priority']):
            context = self.get_topic_context(topic, min_year)
            if context and context.total_measures >= MIN_MEASURES_FOR_FILTER:
                results.append({
                    'topic': topic,
                    'label': config['label'],
                    'color': config['color'],
                    'icon': config['icon'],
                    'priority': config['priority'],
                    'total_measures': context.total_measures,
                    'first_year': context.first_year,
                    'pass_rate': round(context.pass_rate * 100, 1),
                    'avg_yes_pct': round(context.avg_yes_pct, 1),
                })

        return results

    def get_measure_topics(self, measure_id: int) -> List[str]:
        """Get all topics for a measure, sorted by priority."""
        conn = self.connect()

        cursor = conn.execute("""
            SELECT
                is_marijuana, is_gambling, is_abortion, is_marriage,
                is_tax, is_education, is_health, is_elections,
                is_criminal, is_environment
            FROM ca_historical_measures
            WHERE id = ?
        """, (measure_id,))

        row = cursor.fetchone()
        if not row:
            return []

        topics = []
        topic_order = [
            ('marijuana', row['is_marijuana']),
            ('gambling', row['is_gambling']),
            ('abortion', row['is_abortion']),
            ('marriage', row['is_marriage']),
            ('tax', row['is_tax']),
            ('education', row['is_education']),
            ('health', row['is_health']),
            ('elections', row['is_elections']),
            ('criminal', row['is_criminal']),
            ('environment', row['is_environment']),
        ]

        for topic, is_set in topic_order:
            if is_set:
                topics.append(topic)

        return topics

    def get_measures_by_topic(
        self,
        topic: str,
        min_year: int = 1970,
        limit: int = 100,
        offset: int = 0
    ) -> List[HistoricalMeasure]:
        """Get all measures for a topic."""
        if topic not in TOPIC_CONFIG:
            return []

        column = TOPIC_CONFIG[topic]['column']
        conn = self.connect()

        cursor = conn.execute(f"""
            SELECT
                id, ballot_name, year, description, pct_yes, passed,
                measure_type, election_type, margin, is_close,
                is_marijuana, is_gambling, is_abortion, is_marriage,
                is_tax, is_education, is_health, is_elections,
                is_criminal, is_environment
            FROM ca_historical_measures
            WHERE {column} = 1 AND year >= ?
            ORDER BY year DESC
            LIMIT ? OFFSET ?
        """, (min_year, limit, offset))

        measures = []
        for row in cursor:
            topics = self._extract_topics(row)
            measures.append(self._row_to_measure(row, topics))

        return measures

    def search_measures(
        self,
        query: str,
        min_year: int = 1970,
        topic: Optional[str] = None,
        passed: Optional[bool] = None,
        limit: int = 50
    ) -> List[HistoricalMeasure]:
        """
        Full-text search on measure descriptions.

        Args:
            query: Search text
            min_year: Minimum year filter
            topic: Optional topic filter
            passed: Optional pass/fail filter
            limit: Maximum results
        """
        conn = self.connect()

        # Build WHERE clause
        conditions = ["year >= ?"]
        params = [min_year]

        if topic and topic in TOPIC_CONFIG:
            conditions.append(f"{TOPIC_CONFIG[topic]['column']} = 1")

        if passed is not None:
            conditions.append("passed = ?")
            params.append(1 if passed else 0)

        where_clause = " AND ".join(conditions)

        # Search using FTS or LIKE fallback
        try:
            cursor = conn.execute(f"""
                SELECT m.*
                FROM ca_historical_measures m
                JOIN ca_historical_search s ON m.id = s.rowid
                WHERE s.ca_historical_search MATCH ?
                AND {where_clause}
                ORDER BY year DESC
                LIMIT ?
            """, [query] + params + [limit])
        except sqlite3.OperationalError:
            # Fallback to LIKE search
            cursor = conn.execute(f"""
                SELECT *
                FROM ca_historical_measures
                WHERE (description LIKE ? OR ballot_name LIKE ?)
                AND {where_clause}
                ORDER BY year DESC
                LIMIT ?
            """, [f"%{query}%", f"%{query}%"] + params + [limit])

        measures = []
        for row in cursor:
            topics = self._extract_topics(row)
            measures.append(self._row_to_measure(row, topics))

        return measures

    def get_measure_by_id(self, measure_id: int) -> Optional[HistoricalMeasure]:
        """Get a single measure by ID."""
        conn = self.connect()

        cursor = conn.execute("""
            SELECT *
            FROM ca_historical_measures
            WHERE id = ?
        """, (measure_id,))

        row = cursor.fetchone()
        if not row:
            return None

        topics = self._extract_topics(row)
        return self._row_to_measure(row, topics)

    def get_similar_measures(
        self,
        measure_id: int,
        limit: int = 5
    ) -> List[HistoricalMeasure]:
        """
        Get measures similar to the given measure (same topics).
        """
        # Get the measure's topics
        topics = self.get_measure_topics(measure_id)
        if not topics:
            return []

        # Get the primary topic (highest priority)
        primary_topic = topics[0]
        column = TOPIC_CONFIG[primary_topic]['column']

        conn = self.connect()
        cursor = conn.execute(f"""
            SELECT *
            FROM ca_historical_measures
            WHERE {column} = 1 AND id != ?
            ORDER BY year DESC
            LIMIT ?
        """, (measure_id, limit))

        measures = []
        for row in cursor:
            row_topics = self._extract_topics(row)
            measures.append(self._row_to_measure(row, row_topics))

        return measures

    def _extract_topics(self, row: sqlite3.Row) -> List[str]:
        """Extract topic list from a database row."""
        topics = []
        topic_columns = [
            ('marijuana', 'is_marijuana'),
            ('gambling', 'is_gambling'),
            ('abortion', 'is_abortion'),
            ('marriage', 'is_marriage'),
            ('tax', 'is_tax'),
            ('education', 'is_education'),
            ('health', 'is_health'),
            ('elections', 'is_elections'),
            ('criminal', 'is_criminal'),
            ('environment', 'is_environment'),
        ]

        for topic, col in topic_columns:
            try:
                if row[col]:
                    topics.append(topic)
            except (KeyError, IndexError):
                pass

        return topics

    def _row_to_measure(self, row: sqlite3.Row, topics: List[str]) -> HistoricalMeasure:
        """Convert database row to HistoricalMeasure."""
        margin = row['margin']
        is_close = bool(row['is_close']) if row['is_close'] is not None else False

        # Determine margin label
        if margin is None:
            margin_label = "Unknown"
        elif abs(margin) < 5:
            margin_label = "Very Close"
        elif abs(margin) < 10:
            margin_label = "Close"
        elif abs(margin) < 20:
            margin_label = "Comfortable"
        else:
            margin_label = "Landslide"

        return HistoricalMeasure(
            id=row['id'],
            ballot_name=row['ballot_name'] or '',
            year=row['year'],
            description=row['description'] or '',
            pct_yes=row['pct_yes'],
            passed=bool(row['passed']) if row['passed'] is not None else None,
            measure_type=row['measure_type'] or '',
            election_type=row['election_type'] or '',
            topics=topics,
            primary_topic=topics[0] if topics else None,
            margin=margin,
            is_close=is_close,
            margin_label=margin_label,
        )
