"""
Quick helper to peek at the first merged lines.

Usage:
  python -m services.worker.debug.peek_merged <pdf_basename>

Loads /data/outbox/<pdf_basename>.01a_lines_merged.debug.json and prints the
first 40 merged lines with text and compact x-range and y value.
"""

import argparse
import json
from pathlib import Path
import sys


def fmt_float(val, nd=3):
    try:
        return f"{float(val):.{nd}f}"
    except Exception:
        return str(val)


def main():
    parser = argparse.ArgumentParser(description="Peek merged lines for a processed PDF")
    parser.add_argument("pdf_basename", help="PDF base name without .pdf")
    args = parser.parse_args()

    debug_path = Path(f"/data/outbox/{args.pdf_basename}.01a_lines_merged.debug.json")
    if not debug_path.exists():
        print(f"Not found: {debug_path}")
        return 1

    try:
        data = json.loads(debug_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to load {debug_path}: {e}")
        return 1

    lines = data.get("lines", [])
    print(f"Merged lines: showing first {min(40, len(lines))} of {len(lines)} from {debug_path.name}\n")
    for i, line in enumerate(lines[:40], start=1):
        text = (line.get("text") or "").strip().replace("\n", " ")
        page = line.get("page", "?")
        x0 = line.get("xLeft", line.get("x_left", None))
        x1 = line.get("xRight", line.get("x_right", None))
        y = line.get("yNorm", line.get("y_norm", None))
        x0s = fmt_float(x0, 1)
        x1s = fmt_float(x1, 1)
        ys = fmt_float(y, 3)
        print(f"{i:2d}. p{page} y={ys} x=[{x0s}-{x1s}]  {text}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

