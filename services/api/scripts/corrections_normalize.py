#!/usr/bin/env python3
"""
Normalize corrections on disk and optionally apply to canonical docs.

Usage:
  python services/api/scripts/corrections_normalize.py [--data-dir /data] [--apply] [--dry-run]

Actions:
  - Iterate /data/results/*/corrections.json
  - For each correction: canonicalize field via resolve_field; prefer new_value if value empty
  - Re-save normalized corrections.json (unless --dry-run)
  - If --apply: apply normalized corrections to <RID>.json and write migration.log with counts
"""
import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from api.corrections.schema import resolve_field
from api.corrections.normalize import normalize_items
from api.results import _canonical_path  # reuse canonical path helper
from api.utils.corrections import set_by_path, unset_by_path


def _load_list(p: Path) -> List[Dict[str, Any]]:
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if isinstance(data.get('corrections'), list):
                return data['corrections']
            if isinstance(data.get('items'), list):
                return data['items']
        return []
    except Exception:
        return []


def _apply(doc: Dict[str, Any], c: Dict[str, Any]) -> bool:
    op = (c.get('op') or 'replace').lower()
    value = c.get('value')
    path = c.get('path')
    if not path:
        fld = c.get('field')
        if isinstance(fld, str):
            if fld.startswith('header_'):
                mapped = 'label' if fld == 'header_label' else 'value'
                path = f'document_info.{mapped}'
            elif fld in ('vendor_name', 'patient_first_name', 'patient_last_name'):
                path = f'document_info.{fld}'
    if not path:
        return False
    try:
        if op == 'unset':
            unset_by_path(doc, path)
        else:
            set_by_path(doc, path, value)
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description='Normalize corrections and optionally apply to canonical docs')
    ap.add_argument('--data-dir', default=os.environ.get('DATA_DIR', '/data'))
    ap.add_argument('--apply', action='store_true', help='Apply normalized corrections to canonical <RID>.json')
    ap.add_argument('--dry-run', action='store_true', help='Do not write any files')
    args = ap.parse_args()

    results_dir = Path(args.data_dir) / 'results'
    if not results_dir.exists():
        print(f"No results dir: {results_dir}")
        return 0

    total_rids = 0
    total_items = 0
    for rid_dir in sorted(results_dir.iterdir()):
        if not rid_dir.is_dir():
            continue
        rid = rid_dir.name
        cfile = rid_dir / 'corrections.json'
        if not cfile.exists():
            continue
        total_rids += 1
        items = _load_list(cfile)
        if not items:
            print(f"RID={rid}: empty corrections")
            continue
        total_items += len(items)
        normalized, stats = normalize_items(items)
        changed = normalized != items
        print(f"RID={rid}: items={len(items)} canonicalized={stats['canonicalized']} value_filled={stats['value_filled']} unknown={stats['unknown_fields']} changed={changed}")
        if not args.dry_run and changed:
            cfile.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding='utf-8')

        if args.apply:
            # Load canonical; skip if missing
            cpath = _canonical_path(rid)
            if not cpath.exists():
                print(f"RID={rid}: canonical missing, skip apply")
                continue
            try:
                doc = json.loads(cpath.read_text(encoding='utf-8'))
            except Exception as e:
                print(f"RID={rid}: failed to read canonical: {e}")
                continue
            applied = 0
            # Apply in ts order, stable
            normalized_sorted = sorted(normalized, key=lambda x: x.get('ts') or '')
            for item in normalized_sorted:
                if _apply(doc, item):
                    applied += 1
            if applied > 0 and not args.dry_run:
                cpath.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf-8')
            # Append migration log per RID
            logp = rid_dir / 'migration.log'
            line = json.dumps({
                'rid': rid,
                'items': len(items),
                'canonicalized': stats['canonicalized'],
                'value_filled': stats['value_filled'],
                'unknown': stats['unknown_fields'],
                'applied': applied,
            })
            if not args.dry_run:
                with logp.open('a', encoding='utf-8') as f:
                    f.write(line + '\n')

    print(f"Done. rids={total_rids} total_items={total_items}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
