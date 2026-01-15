#!/usr/bin/env python3
"""Show historical topic statistics."""
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.historical_operations import HistoricalDatabase
from src.config import DB_PATH

db = HistoricalDatabase(DB_PATH)
stats = db.get_all_topic_stats()

print('Topic Statistics (1970+):')
print('=' * 50)
for s in stats:
    print(f'{s["icon"]} {s["label"]}: {s["total_measures"]} measures ({s["pass_rate"]}% pass rate)')
