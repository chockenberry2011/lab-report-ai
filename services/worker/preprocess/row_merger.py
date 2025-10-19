"""
Pre-classification row merger that groups same-row "cell" lines into synthetic lines.

This module merges multiple cell-level text extractions on the same row into
single merged lines, which improves role classification accuracy by providing
complete row context instead of fragmented cells.
"""

import json
import os
import statistics
from typing import List, Dict, Any


def merge_row_cells(lines: List[Dict[str, Any]], y_tol: float = 0.006) -> List[Dict[str, Any]]:
    """
    Merge cell lines that are on the same row into synthetic lines.
    
    Args:
        lines: List of line dicts from extraction (page, text, xLeft, xRight, yNorm, etc.)
        y_tol: Y-coordinate tolerance for grouping lines into same row
        
    Returns:
        List of merged line dicts, where each represents a complete row
    """
    if not lines:
        return []
    
    merged_lines = []
    
    # Group by page first
    pages = {}
    for line in lines:
        page = line.get('page', 1)
        if page not in pages:
            pages[page] = []
        pages[page].append(line)
    
    # Process each page separately
    for page_num, page_lines in pages.items():
        # Sort by yNorm to process rows top to bottom
        sorted_lines = sorted(page_lines, key=lambda x: x.get('yNorm', 0))
        
        # Group into bins using small-bin strategy
        bins = []
        current_bin = []
        
        for line in sorted_lines:
            y_norm = line.get('yNorm', 0)
            
            if not current_bin:
                # Start first bin
                current_bin = [line]
            else:
                # Check if this line belongs to current bin
                prev_y = current_bin[-1].get('yNorm', 0)
                if abs(y_norm - prev_y) <= y_tol:
                    current_bin.append(line)
                else:
                    # Start new bin
                    if current_bin:
                        bins.append(current_bin)
                    current_bin = [line]
        
        # Don't forget the last bin
        if current_bin:
            bins.append(current_bin)
        
        # Process each bin to create merged lines
        for bin_cells in bins:
            merged_line = _merge_bin_cells(bin_cells, page_num)
            if merged_line:
                merged_lines.append(merged_line)
    
    return merged_lines


def _merge_bin_cells(bin_cells: List[Dict[str, Any]], page_num: int) -> Dict[str, Any]:
    """
    Merge cells in a single row bin into one synthetic line.
    
    Args:
        bin_cells: List of cell dicts that are on the same row
        page_num: Page number
        
    Returns:
        Merged line dict or None if bin should be filtered out
    """
    if not bin_cells:
        return None
    
    # Check if we should keep this bin
    if not _should_keep_bin(bin_cells):
        return None
    
    # Sort cells by xLeft (left to right order)
    sorted_cells = sorted(bin_cells, key=lambda x: x.get('xLeft', 0))
    
    # Extract text from each cell
    cell_texts = []
    for cell in sorted_cells:
        text = cell.get('text', '').strip()
        if text:  # Only include non-empty cells
            cell_texts.append(text)
    
    if not cell_texts:
        return None
    
    # Compute merged properties
    y_norms = [cell.get('yNorm', 0) for cell in bin_cells]
    font_sizes = [cell.get('fontSize', 12) for cell in bin_cells if cell.get('fontSize')]
    x_lefts = [cell.get('xLeft', 0) for cell in bin_cells]
    x_rights = [cell.get('xRight', 0) for cell in bin_cells]
    is_bold_values = [cell.get('isBold', False) for cell in bin_cells]
    
    # Create merged line dict
    merged_line = {
        "page": page_num,
        "text": "\t".join(cell_texts),  # Use tabs to preserve column structure
        "yNorm": statistics.mean(y_norms),
        "isBold": any(is_bold_values),  # True if any cell is bold
        "hasText": True,
        "fontSize": statistics.median(font_sizes) if font_sizes else 12.0,
        "xLeft": min(x_lefts),
        "xRight": max(x_rights),
        "cells": bin_cells  # Keep original cells for debugging
    }
    
    return merged_line


def _should_keep_bin(bin_cells: List[Dict[str, Any]]) -> bool:
    """
    Determine if a bin should be kept based on content criteria.
    
    Args:
        bin_cells: List of cell dicts in the bin
        
    Returns:
        True if bin should be kept, False to filter out
    """
    if not bin_cells:
        return False
    
    # Always keep bins with multiple cells
    if len(bin_cells) >= 2:
        return True
    
    # For single cells, check additional criteria
    single_cell = bin_cells[0]
    text = single_cell.get('text', '').strip()
    
    if not text:
        return False
    
    # Keep if contains a digit (likely test result or measurement)
    if any(c.isdigit() for c in text):
        return True
    
    # Keep if looks like section header (bold and large font)
    is_bold = single_cell.get('isBold', False)
    font_size = single_cell.get('fontSize', 12)
    
    if is_bold and font_size >= 11:
        return True
    
    # Keep if text is long enough to be meaningful
    if len(text) >= 10:
        return True
    
    return False


def debug_dump(path: str, obj: Any) -> None:
    """
    Write object to JSON file for debugging.
    
    Args:
        path: Output file path
        obj: Object to serialize to JSON
    """
    try:
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        # Don't let debug writing crash the pipeline
        print(f"Warning: Failed to write debug file {path}: {e}")