#!/usr/bin/env python3
"""
Corrections triage utility.

Read-only by default. Given a result_id, prints the on-disk corrections.json path,
whether it exists, and the top-level JSON type (array or object).

With --fix, if the top-level is an object, creates a .bak backup and rewrites
the file as a one-element array containing the object.

Exit codes:
  0: Success (including non-existent file in read-only mode)
  2: Invalid JSON
  3: --fix failed (backup or write error)
  5: Unknown top-level type (neither array nor object)
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime
import sys


def normalize_id(result_id: str) -> str:
    return result_id.split('.', 1)[0]


def resolve_results_dir(args) -> Path:
    # Precedence: --results-dir > --data-root > env DATA_ROOT > env RESULTS_DIR > default
    if args.results_dir:
        return Path(args.results_dir)
    data_root = args.data_root or os.environ.get('DATA_ROOT')
    if data_root:
        return Path(data_root) / 'results'
    env_results = os.environ.get('RESULTS_DIR')
    if env_results:
        return Path(env_results)
    return Path('/data/results')


def read_top_level_type(p: Path):
    try:
        with p.open('r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {p}: {e}")
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: Failed to read {p}: {e}")
        sys.exit(2)

    if isinstance(data, list):
        return 'array', data
    if isinstance(data, dict):
        return 'object', data
    return 'other', data


def backup_path(p: Path) -> Path:
    base = p.with_suffix(p.suffix + '.bak')
    if not base.exists():
        return base
    ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    return p.with_suffix(p.suffix + f'.{ts}.bak')


def main():
    ap = argparse.ArgumentParser(description='Corrections file triage utility (read-only by default)')
    ap.add_argument('result_id', help='Result ID (suffixes like .03_compose.debug are allowed)')
    ap.add_argument('--data-root', help='Override DATA_ROOT (default from env or /data)')
    ap.add_argument('--results-dir', help='Override results directory (takes precedence over --data-root)')
    ap.add_argument('--fix', action='store_true', help='Wrap object-shaped file as single-element array (creates .bak)')
    args = ap.parse_args()

    rid = normalize_id(args.result_id)
    results_dir = resolve_results_dir(args)
    path = results_dir / rid / 'corrections.json'

    print(f"Result ID (normalized): {rid}")
    print(f"Corrections file path: {path}")

    if not path.exists():
        print("Exists: no")
        # Not an error in read-only mode
        sys.exit(0)

    print("Exists: yes")

    top_type, data = read_top_level_type(path)
    print(f"Top-level JSON type: {top_type}")

    if top_type == 'array':
        print('No action needed: file is already an array.')
        sys.exit(0)

    if top_type == 'object':
        if not args.fix:
            print('Detected legacy/object shape. Re-run with --fix to wrap into an array.')
            sys.exit(0)

        # Perform fix: backup then write array
        try:
            bp = backup_path(path)
            path.replace(bp)
            # Write new array file
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', encoding='utf-8') as f:
                json.dump([data], f, ensure_ascii=False, indent=2)
            print(f"Fixed: wrapped object into array. Backup created at: {bp}")
            sys.exit(0)
        except Exception as e:
            print(f"ERROR: Failed to apply fix: {e}")
            sys.exit(3)

    # Unknown top-level type
    print('ERROR: Unknown top-level JSON type (neither array nor object).')
    sys.exit(5)


if __name__ == '__main__':
    main()

