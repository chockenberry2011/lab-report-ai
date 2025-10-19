import pytest

from services.worker.composer import PanelComposer
from services.worker.composer.scoring import _lookup_line_proba


def test_lookup_line_proba_variants():
    # dict keyed by line_number -> {label: prob}
    d = {3: {"TEST_ROW": 0.9, "JUNK": 0.1}}
    assert _lookup_line_proba(d, 3, "TEST_ROW") == pytest.approx(0.9)
    assert _lookup_line_proba(d, 3, "MISSING") is None
    assert _lookup_line_proba(d, 4, "TEST_ROW") is None

    # aligned list by index (line_number as index)
    aligned = [None, None, {"TEST_ROW": 0.5}]
    assert _lookup_line_proba(aligned, 2, "TEST_ROW") == pytest.approx(0.5)
    assert _lookup_line_proba(aligned, 0, "TEST_ROW") is None

    # list of dicts with distribution
    lod = [{"line_number": 7, "distribution": {"TEST_ROW": 0.8}}]
    assert _lookup_line_proba(lod, 7, "TEST_ROW") == pytest.approx(0.8)

    # list of dicts with direct probs on the item
    lod_direct = [
        {"line_number": 8, "TEST_ROW": 0.6, "SECTION_PANEL": 0.2},
        {"line_number": 9, "distribution": {"TEST_ROW": 0.7}},
    ]
    assert _lookup_line_proba(lod_direct, 8, "TEST_ROW") == pytest.approx(0.6)
    assert _lookup_line_proba(lod_direct, 9, "TEST_ROW") == pytest.approx(0.7)


def test_compose_minimal():
    lines = [
        {
            "page": 1,
            "line_number": 0,
            "text": "COMPREHENSIVE METABOLIC PANEL",
            "role": "SECTION_PANEL",
            "y_norm": 0.10,
        },
        {
            "page": 1,
            "line_number": 1,
            "text": "Glucose 101 mg/dL 70-99 H",
            "role": "TEST_ROW",
            "y_norm": 0.12,
        },
        {
            "page": 1,
            "line_number": 2,
            "text": "Sodium 140 mmol/L 135-145",
            "role": "TEST_ROW",
            "y_norm": 0.14,
        },
    ]

    pc = PanelComposer()
    # Ensure no exception when classifier_probabilities is None
    result = pc.compose(lines, classifier_probabilities=None)

    assert len(result.panels) == 1
    panel = result.panels[0]
    assert hasattr(panel, "test_count")
    assert panel.test_count() == 2

