from services.worker.parsing.testrow_rules import parse_line


def test_flag_before_unit_and_range():
    text = "TSH 4.71 High mIU/L 0.45-4.5"
    res = parse_line(text)
    pf = res.get("parsed_fields", {})
    assert pf.get("test_name") == "TSH"
    assert pf.get("result_value") == "4.71"
    assert pf.get("units") == "mIU/L"
    assert pf.get("reference_range") == "0.45-4.5"
    assert pf.get("flags") == ["HIGH"]


def test_unit_warning_for_unlikely_unit():
    text = "WBC 6.0 g/dL 4.0-10.5"
    res = parse_line(text)
    pf = res.get("parsed_fields", {})
    assert pf.get("test_name") == "WBC"
    assert pf.get("units") == "g/dL"
    warnings = res.get("fieldWarnings", [])
    assert "unit_unlikely_for_test" in warnings


def test_egfr_with_low_flag_between_value_and_unit():
    """Test: 'eGFR 52 Low mL/min/1.73 >59' -> units='mL/min/1.73', flag='LOW'"""
    text = "eGFR 52 Low mL/min/1.73 >59"
    res = parse_line(text)
    pf = res.get("parsed_fields", {})
    assert pf.get("test_name") == "eGFR"
    assert pf.get("result_value") == "52"
    assert pf.get("units") == "mL/min/1.73"
    assert pf.get("flags") == ["LOW"]
    # Note: >59 should be parsed as reference range, but the format is non-standard


def test_sodium_with_high_flag_between_value_and_unit():
    """Test: 'Sodium 150 High mmol/L 134-144 01' -> units='mmol/L', flag='HIGH'"""
    text = "Sodium 150 High mmol/L 134-144 01"
    res = parse_line(text)
    pf = res.get("parsed_fields", {})
    assert pf.get("test_name") == "Sodium"
    assert pf.get("result_value") == "150"
    assert pf.get("units") == "mmol/L"
    assert pf.get("flags") == ["HIGH"]
    assert pf.get("reference_range") == "134-144"


def test_glucose_without_flags():
    """Test: Rows without flags keep units and flag=None"""
    text = "Glucose 95 mg/dL 70-99"
    res = parse_line(text)
    pf = res.get("parsed_fields", {})
    assert pf.get("test_name") == "Glucose"
    assert pf.get("result_value") == "95"
    assert pf.get("units") == "mg/dL"
    assert pf.get("reference_range") == "70-99"
    assert pf.get("flags") == []

