#!/usr/bin/env python3
"""Validate/apply a pinned statewide correction to an explicit scratch DB."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.database.statewide_ballot import reconcile, create_working_copy


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--db", type=Path, help="Previously owned working copy, for check/replay")
    parser.add_argument("--baseline", type=Path, help="Read-only input to a new working copy")
    parser.add_argument("--work-dir", type=Path, help="New, nonexistent working directory")
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Apply atomically; default is a read-only check")
    args = parser.parse_args(argv)
    if args.db:
        if args.baseline or args.work_dir:
            parser.error("Use --db alone for an existing owned copy")
        db_path = args.db
    else:
        if not args.baseline or not args.work_dir:
            parser.error("Provide --baseline and --work-dir, or --db")
        if not args.work_dir.resolve().is_relative_to(args.scratch_root.resolve()):
            parser.error("Working directory must be beneath the scratch root")
        db_path = create_working_copy(args.baseline, args.work_dir)
    report = reconcile(args.review, db_path=db_path, scratch_root=args.scratch_root, apply=args.apply)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
