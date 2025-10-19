import pytest

from api.serializers import (
    serialize_lab_result,
    serialize_test_row,
)


def test_legacy_only_row_preserves_legacy_and_populates_new_keys():
    row = {
        "line_number": 10,
        "text": "Glucose 90 mg/dL 70-99",
        "test_name": "Glucose",
        "result_value": "90",
        "units": "mg/dL",
        # legacy-only reference range string
        "reference_range": "70-99",
        # no low/high provided
    }

    result = serialize_test_row(row)
    data = result.dict()

    # legacy passes through
    assert data.get("reference_range") == "70-99"
    # *_text mirrors legacy for legacy-only input
    assert data.get("reference_range_text") == "70-99"
    # structured fields present and null
    assert "reference_range_low" in data and data.get("reference_range_low") is None
    assert "reference_range_high" in data and data.get("reference_range_high") is None
    # no flag provided, but keys must exist
    assert "flag" in data and data.get("flag") is None
    assert "flag_norm" in data and data.get("flag_norm") is None


def test_structured_range_row_with_units_and_legacy_passthrough():
    row = {
        "line_number": 2,
        "text": "BUN 15 mg/dL 8-27",
        "test_name": "BUN",
        "result_value": "15",
        "units": "mg/dL",
        # structured range includes text and numeric bounds
        "reference_range": {
            "text": "8-27 mg/dL",
            "low": 8.0,
            "high": 27.0,
        },
    }

    result = serialize_test_row(row)
    data = result.dict()

    # legacy string passes through from text
    assert data.get("reference_range") == "8-27 mg/dL"
    # structured fields populated
    assert data.get("reference_range_text") == "8-27 mg/dL"
    assert data.get("reference_range_low") == 8.0
    assert data.get("reference_range_high") == 27.0
    # units should remain untouched (formatter adds units on UI side)
    assert data.get("units") == "mg/dL"


@pytest.mark.parametrize(
    "raw,expected_norm",
    [
        ("High", "H"),
        ("H", "H"),
        ("LOW", "L"),
        ("L", "L"),
        ("CRIT", "CRIT"),
        ("ABN", "ABN"),
    ],
)
def test_flag_variants_return_original_and_optional_normalized(raw, expected_norm):
    row = {
        "line_number": 3,
        "text": f"Test {raw}",
        "flag": raw,
    }

    result = serialize_test_row(row)
    data = result.dict()

    # API returns original flag string
    assert data.get("flag") == raw
    # optional normalized flag present (but do not break if omitted)
    assert "flag_norm" in data
    assert data.get("flag_norm") == expected_norm


def test_comments_and_methodology_mapped_non_empty():
    row = {
        "line_number": 4,
        "text": "Creatinine 1.5 mg/dL 0.7-1.3",
        "test_name": "Creatinine",
        "result_value": "1.5",
        "units": "mg/dL",
        "reference_range": "0.7-1.3",
        "comments": "Mildly elevated",
        "methodology": "Enzymatic",
    }

    result = serialize_test_row(row)
    data = result.dict()

    assert data.get("comments") == "Mildly elevated"
    assert data.get("methodology") == "Enzymatic"


def test_document_info_objects_present_with_nulls_when_missing():
    # No ehr_payload -> document_info still present with keys defaulting to null
    lab = {
        "lab_panels": [
            {"id": "p1", "name": "Panel", "test_rows": []}
        ]
    }

    result = serialize_lab_result(lab)
    doc = result.document_info.dict()

    # All top-level keys should be present and null
    for key in [
        "patient",
        "vendor",
        "performing_lab",
        "specimen",
        "ordering",
        "report",
    ]:
        assert key in doc
        assert doc.get(key) is None


def test_response_includes_all_expected_keys():
    row = {
        "line_number": 5,
        "text": "Sodium 140 mmol/L 136-145 H",
        "test_name": "Sodium",
        "result_value": "140",
        "units": "mmol/L",
        "reference_range": {"text": "136-145", "low": 136.0, "high": 145.0},
        "flag": "H",
        "comments": "High normal",
        "methodology": "Ion-selective electrode",
        "codes": {"loinc": "2951-2", "cpt": "82435"},
    }

    data = serialize_test_row(row).dict()

    # Ensure presence (not omission) of keys; values may be null
    expected_keys = {
        "line_number",
        "text",
        "confidence",
        "test_name",
        "result_value",
        "units",
        "reference_range",
        "reference_range_text",
        "reference_range_low",
        "reference_range_high",
        "flag",
        "flag_norm",
        "comments",
        "methodology",
        "observed_at",
        "codes",
        "page",
        "y_norm",
        "field_confidences",
    }

    missing = expected_keys.difference(data.keys())
    assert not missing, f"Missing keys from serializer output: {missing}"
