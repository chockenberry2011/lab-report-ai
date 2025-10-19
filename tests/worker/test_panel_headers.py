from services.worker.composer.panel_headers import score_panel_header
from services.worker.composer.composer import PanelComposer


def test_header_scoring_boosts():
    bold_top = {"text": "COMPREHENSIVE METABOLIC PANEL", "is_bold": True, "y_norm": 0.12}
    mid_plain = {"text": "Comprehensive Metabolic Panel", "is_bold": False, "y_norm": 0.50}
    s1 = score_panel_header(bold_top)
    s2 = score_panel_header(mid_plain)
    assert s1 > s2
    assert 0.0 <= s1 <= 1.0 and 0.0 <= s2 <= 1.0


def test_page_break_continuity_without_strong_header():
    # Page 1: strong header and one test
    lines = [
        {"page": 1, "line_number": 0, "text": "COMPREHENSIVE METABOLIC PANEL", "role": "SECTION_PANEL", "y_norm": 0.10, "is_bold": True},
        {"page": 1, "line_number": 1, "text": "Glucose 101 mg/dL 70-99 H", "role": "TEST_ROW", "y_norm": 0.15},
        # Page 2: a weak SECTION_PANEL (not in lexicon) near top
        {"page": 2, "line_number": 2, "text": "Report Page 2", "role": "SECTION_PANEL", "y_norm": 0.12, "is_bold": False},
        {"page": 2, "line_number": 3, "text": "Sodium 140 mmol/L 135-145", "role": "TEST_ROW", "y_norm": 0.18},
    ]

    pc = PanelComposer(page_break_lookahead=12, header_strong_threshold=0.6)
    res = pc.compose(lines, classifier_probabilities=None)

    # Should continue the existing panel across the page break
    assert len(res.panels) == 1
    assert len(res.panels[0].test_rows) == 2

