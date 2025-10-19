"""
Helpers for detecting and scoring panel headers.
"""

from __future__ import annotations

from typing import Dict, Iterable


PANEL_LEXICON: Iterable[str] = [
    "COMPREHENSIVE METABOLIC PANEL",
    "CMP",
    "BASIC METABOLIC PANEL",
    "BMP",
    "COMPLETE BLOOD COUNT",
    "CBC",
    "CBC WITH DIFFERENTIAL",
    "LIPID PANEL",
    "TSH",
    "THYROID STIMULATING HORMONE",
]


def _norm_text(s: str) -> str:
    return (s or "").strip().upper()


def score_panel_header(line: Dict) -> float:
    """
    Compute a header score in [0,1] using:
      - lexicon match (case-insensitive) → big boost
      - bold → small boost
      - y_norm in top 20% → small boost
    """
    if not isinstance(line, dict):
        return 0.0
    text = _norm_text(line.get("text", ""))
    is_bold = bool(line.get("is_bold") or line.get("isBold"))
    y_norm = float(line.get("y_norm", line.get("yNorm", 0.5)) or 0.5)

    score = 0.0

    # Lexicon boost
    if text in (_norm_text(t) for t in PANEL_LEXICON):
        score += 0.7

    # Bold boost
    if is_bold:
        score += 0.15

    # Top-of-page boost (top 20%)
    if y_norm <= 0.20:
        score += 0.15

    # Clamp
    return max(0.0, min(1.0, score))


__all__ = ["PANEL_LEXICON", "score_panel_header"]

