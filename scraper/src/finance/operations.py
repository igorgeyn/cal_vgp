"""
Query layer for the statewide proposition finance database.
"""
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional

from .schema import FINANCE_DB_PATH


class FinanceDatabase:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or FINANCE_DB_PATH
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def get_finance_summary(self, measure_id: str) -> List[Dict]:
        cursor = self.conn.execute(
            "SELECT stance, total_receipts, n_committees, top5_share, hhi FROM measure_finance_summary WHERE measure_id = ?",
            (measure_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_finance_timeline(self, measure_id: str) -> List[Dict]:
        cursor = self.conn.execute(
            "SELECT stance, week_start, weekly_receipts, cumulative_receipts FROM measure_finance_timeline_weekly WHERE measure_id = ? ORDER BY week_start",
            (measure_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_top_donors(self, measure_id: str, limit: int = 10) -> List[Dict]:
        cursor = self.conn.execute(
            "SELECT stance, donor_name_canon, donor_type, donor_sector, total_amount FROM measure_top_donors WHERE measure_id = ? ORDER BY total_amount DESC LIMIT ?",
            (measure_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_all_measure_ids(self) -> List[str]:
        cursor = self.conn.execute(
            "SELECT DISTINCT measure_id FROM measure_finance_summary"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_contribution_breakdown(self, measure_id: str) -> Dict:
        """Get contribution size distribution for a measure."""
        cursor = self.conn.execute("""
            SELECT
                CASE
                    WHEN ABS(amount) < 100 THEN 'small'
                    WHEN ABS(amount) < 1000 THEN 'medium'
                    WHEN ABS(amount) < 10000 THEN 'large'
                    ELSE 'mega'
                END as bucket,
                COUNT(*) as count,
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total
            FROM transaction_record tr
            JOIN measure_committee_link mcl ON tr.committee_id = mcl.committee_id
            WHERE mcl.measure_id = ?
            GROUP BY bucket
        """, (measure_id,))

        result = {'small': {'count': 0, 'total': 0}, 'medium': {'count': 0, 'total': 0},
                  'large': {'count': 0, 'total': 0}, 'mega': {'count': 0, 'total': 0}}
        for row in cursor.fetchall():
            result[row['bucket']] = {'count': row['count'], 'total': row['total']}
        return result

    def close(self):
        if self.conn:
            self.conn.close()
