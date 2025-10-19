#!/usr/bin/env python3
"""
Convert *.lines.json files to Label Studio tasks format.

Transforms document-level line extraction output into Label Studio import format,
where each line becomes a separate task with text and metadata.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def strip_cid_markers(text: str) -> str:
    """Remove (cid:...) substrings from text."""
    return re.sub(r'\(cid:[^)]+\)', '', text)


def load_lines_from_file(file_path: Path) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Load lines array from input file and extract source_file if present.
    
    Returns:
        (lines_list, source_file_name)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Failed to load JSON from {file_path}: {e}")
    
    # Extract source file name
    source_file = None
    if isinstance(data, dict):
        if 'data' in data and isinstance(data['data'], dict):
            source_file = data['data'].get('source_file')
        else:
            source_file = data.get('source_file')
    
    # Extract lines array
    lines = []
    if isinstance(data, list):
        # Already a list - check if it's tasks or lines
        if data and isinstance(data[0], dict) and 'data' in data[0] and 'text' in data[0]['data']:
            # Looks like Label Studio tasks already
            print(f"Warning: {file_path} appears to contain Label Studio tasks already")
            return data, source_file
        lines = data
    elif isinstance(data, dict):
        if 'data' in data and isinstance(data['data'], dict) and 'lines' in data['data']:
            lines = data['data']['lines']
            if 'source_file' not in locals() and data['data'].get('source_file'):
                source_file = data['data']['source_file']
        elif 'lines' in data:
            lines = data['lines']
        else:
            raise ValueError(f"No 'lines' array found in {file_path}")
    else:
        raise ValueError(f"Invalid JSON structure in {file_path}")
    
    if not isinstance(lines, list):
        raise ValueError(f"'lines' is not an array in {file_path}")
    
    return lines, source_file


def filter_line(line: Dict[str, Any], min_chars: int, strip_cid: bool) -> Optional[str]:
    """
    Filter and clean line text according to rules.
    
    Returns:
        Cleaned text if line passes filters, None if should be skipped
    """
    # Skip if hasText is explicitly false
    if line.get('hasText') is False:
        return None
    
    # Extract and clean text
    text = line.get('text', '').strip()
    if not text:
        return None
    
    # Strip CID markers if requested
    if strip_cid:
        text = strip_cid_markers(text)
        text = text.strip()  # Strip again after CID removal
    
    # Check minimum length
    if len(text) < min_chars:
        return None
    
    return text


def convert_line_to_task(
    line: Dict[str, Any], 
    line_index: int, 
    source_file: Optional[str],
    min_chars: int,
    strip_cid: bool
) -> Optional[Dict[str, Any]]:
    """
    Convert a single line to Label Studio task format.
    
    Returns:
        Task dict if line passes filters, None if should be skipped
    """
    text = filter_line(line, min_chars, strip_cid)
    if text is None:
        return None
    
    task_data = {
        'text': text,
        'line_index': line_index
    }
    
    # Add optional fields if present
    for field in ['page', 'isBold', 'fontSize', 'xLeft', 'xRight', 'yNorm']:
        value = line.get(field)
        if value is not None:
            task_data[field] = value
    
    # Add source file if available
    if source_file:
        task_data['source_file'] = source_file
    
    return {'data': task_data}


def convert_lines_to_tasks(
    lines: List[Dict[str, Any]], 
    source_file: Optional[str],
    min_chars: int,
    strip_cid: bool
) -> List[Dict[str, Any]]:
    """Convert list of lines to list of Label Studio tasks."""
    tasks = []
    
    for i, line in enumerate(lines):
        task = convert_line_to_task(line, i, source_file, min_chars, strip_cid)
        if task is not None:
            tasks.append(task)
    
    return tasks


def write_tasks(
    tasks: List[Dict[str, Any]], 
    output_path: Path, 
    ndjson: bool
) -> None:
    """Write tasks to output file in appropriate format."""
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        if ndjson:
            for task in tasks:
                json.dump(task, f, ensure_ascii=False)
                f.write('\n')
        else:
            json.dump(tasks, f, ensure_ascii=False, indent=2)


def determine_output_path(
    input_path: Path,
    output_arg: Optional[str],
    extension: str,
    ndjson: bool,
    multiple_inputs: bool
) -> Path:
    """Determine the output path based on CLI arguments and input."""
    if output_arg:
        output_base = Path(output_arg)
        
        if multiple_inputs or ndjson:
            # Output to directory - use input basename with new extension
            if output_base.is_file():
                # If output_arg points to existing file but we need directory behavior
                output_base = output_base.parent
            
            output_dir = output_base
            stem = input_path.stem
            # Remove .lines if present in stem
            if stem.endswith('.lines'):
                stem = stem[:-6]
            elif stem.endswith('.pdf.lines'):
                stem = stem[:-10]
            
            return output_dir / f"{stem}{extension}"
        else:
            # Single input, single output - use exactly as specified
            return output_base
    else:
        # Default: same directory as input with .ls.json extension
        stem = input_path.stem
        if stem.endswith('.lines'):
            stem = stem[:-6]
        elif stem.endswith('.pdf.lines'):
            stem = stem[:-10]
        
        return input_path.parent / f"{stem}{extension}"


def process_file(
    input_path: Path,
    output_arg: Optional[str],
    extension: str,
    ndjson: bool,
    min_chars: int,
    strip_cid: bool,
    multiple_inputs: bool
) -> int:
    """Process a single input file and return number of tasks written."""
    try:
        lines, source_file = load_lines_from_file(input_path)
        tasks = convert_lines_to_tasks(lines, source_file, min_chars, strip_cid)
        
        if not tasks:
            print(f"Warning: No valid tasks found in {input_path}", file=sys.stderr)
            return 0
        
        output_path = determine_output_path(
            input_path, output_arg, extension, ndjson, multiple_inputs
        )
        
        write_tasks(tasks, output_path, ndjson)
        
        print(f"Wrote {len(tasks)} tasks → {output_path}")
        return len(tasks)
        
    except Exception as e:
        print(f"Error processing {input_path}: {e}", file=sys.stderr)
        return -1


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert *.lines.json files to Label Studio tasks format"
    )
    
    parser.add_argument(
        'inputs',
        nargs='+',
        help='Input *.lines.json files'
    )
    
    parser.add_argument(
        '--out',
        help='Output file or directory'
    )
    
    parser.add_argument(
        '--ndjson',
        action='store_true',
        help='Output as JSON Lines (one task per line) instead of JSON array'
    )
    
    parser.add_argument(
        '--ext',
        default='.ls.json',
        help='Output file extension (default: .ls.json)'
    )
    
    parser.add_argument(
        '--strip-cid',
        action='store_true',
        help='Remove (cid:...) substrings from text'
    )
    
    parser.add_argument(
        '--min-chars',
        type=int,
        default=1,
        help='Minimum characters required to keep a line (default: 1)'
    )
    
    args = parser.parse_args()
    
    # Convert input patterns to Path objects
    input_paths = []
    for pattern in args.inputs:
        path = Path(pattern)
        if path.exists():
            input_paths.append(path)
        else:
            # Try glob expansion (handles absolute paths)
            matches = [Path(p) for p in glob.glob(pattern)]
            if matches:
                input_paths.extend(matches)
            else:
                print(f"Warning: No files found matching {pattern}", file=sys.stderr)
    
    if not input_paths:
        print("Error: No input files found", file=sys.stderr)
        sys.exit(1)
    
    multiple_inputs = len(input_paths) > 1
    total_tasks = 0
    failed_files = 0
    
    for input_path in input_paths:
        result = process_file(
            input_path,
            args.out,
            args.ext,
            args.ndjson,
            args.min_chars,
            args.strip_cid,
            multiple_inputs
        )
        
        if result < 0:
            failed_files += 1
        else:
            total_tasks += result
    
    if failed_files > 0:
        print(f"\nCompleted with {failed_files} failed files", file=sys.stderr)
        sys.exit(1)
    
    if total_tasks == 0:
        print("Error: No tasks generated from any input files", file=sys.stderr)
        sys.exit(1)
    
    print(f"\nTotal: {total_tasks} tasks from {len(input_paths)} files")


if __name__ == "__main__":
    main()