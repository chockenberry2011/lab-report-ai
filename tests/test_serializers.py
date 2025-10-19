# tests/test_serializers.py
"""
Tests for enhanced API serializers.
"""

import pytest
from api.serializers import (
    serialize_lab_result,
    serialize_test_row,
    serialize_ehr_payload,
    normalize_flag,
    parse_reference_range,
    parse_address,
    EnhancedTestRow,
    EnhancedLabResult,
    ReferenceRange,
    Address,
    Patient,
    Vendor
)


class TestNormalizeFlag:
    """Test flag normalization."""
    
    def test_normalize_high_flags(self):
        """Test normalization of high flags."""
        result = normalize_flag("H")
        assert result == {"flag": "H", "flag_norm": "H"}
        
        result = normalize_flag("High")
        assert result == {"flag": "High", "flag_norm": "H"}
        
        result = normalize_flag("HI")
        assert result == {"flag": "HI", "flag_norm": "H"}
    
    def test_normalize_low_flags(self):
        """Test normalization of low flags."""
        result = normalize_flag("L")
        assert result == {"flag": "L", "flag_norm": "L"}
        
        result = normalize_flag("Low")
        assert result == {"flag": "Low", "flag_norm": "L"}
        
        result = normalize_flag("LO")
        assert result == {"flag": "LO", "flag_norm": "L"}
    
    def test_normalize_critical_flags(self):
        """Test normalization of critical flags."""
        result = normalize_flag("CRIT")
        assert result == {"flag": "CRIT", "flag_norm": "CRIT"}
        
        result = normalize_flag("Critical")
        assert result == {"flag": "Critical", "flag_norm": "CRIT"}
        
        result = normalize_flag("PANIC")
        assert result == {"flag": "PANIC", "flag_norm": "CRIT"}
    
    def test_normalize_abnormal_flags(self):
        """Test normalization of abnormal flags."""
        result = normalize_flag("ABN")
        assert result == {"flag": "ABN", "flag_norm": "ABN"}
        
        result = normalize_flag("Abnormal")
        assert result == {"flag": "Abnormal", "flag_norm": "ABN"}
    
    def test_normalize_none_flag(self):
        """Test normalization of None flag."""
        result = normalize_flag(None)
        assert result == {"flag": None, "flag_norm": None}
        
        result = normalize_flag("")
        assert result == {"flag": None, "flag_norm": None}
        
        result = normalize_flag("   ")
        assert result == {"flag": None, "flag_norm": None}
    
    def test_normalize_unknown_flag(self):
        """Test normalization of unknown flags."""
        result = normalize_flag("CUSTOM_FLAG")
        assert result == {"flag": "CUSTOM_FLAG", "flag_norm": "CUSTOM_FLA"}  # Truncated to 10 chars


class TestParseReferenceRange:
    """Test reference range parsing."""
    
    def test_parse_string_range(self):
        """Test parsing string reference range."""
        result = parse_reference_range("70-99")
        expected = ReferenceRange(
            reference_range="70-99",
            reference_range_text="70-99"
        )
        assert result.dict() == expected.dict()
    
    def test_parse_structured_range(self):
        """Test parsing structured reference range."""
        range_data = {
            "text": "70-99 mg/dL",
            "low": 70.0,
            "high": 99.0
        }
        result = parse_reference_range(range_data)
        expected = ReferenceRange(
            reference_range="70-99 mg/dL",
            reference_range_text="70-99 mg/dL",
            reference_range_low=70.0,
            reference_range_high=99.0
        )
        assert result.dict() == expected.dict()
    
    def test_parse_none_range(self):
        """Test parsing None reference range."""
        result = parse_reference_range(None)
        expected = ReferenceRange()
        assert result.dict() == expected.dict()
    
    def test_parse_malformed_range(self):
        """Test parsing malformed reference range."""
        result = parse_reference_range(123)
        expected = ReferenceRange(reference_range="123")
        assert result.dict() == expected.dict()


class TestParseAddress:
    """Test address parsing."""
    
    def test_parse_structured_address(self):
        """Test parsing structured address."""
        addr_data = {
            "street": "123 Main St",
            "city": "Anytown",
            "state": "CA",
            "zip": "90210"
        }
        result = parse_address(addr_data)
        expected = Address(**addr_data)
        assert result.dict() == expected.dict()
    
    def test_parse_string_address(self):
        """Test parsing string address."""
        result = parse_address("123 Main St, Anytown, CA 90210")
        expected = Address(street="123 Main St, Anytown, CA 90210")
        assert result.dict() == expected.dict()
    
    def test_parse_none_address(self):
        """Test parsing None address."""
        result = parse_address(None)
        assert result is None


class TestSerializeTestRow:
    """Test test row serialization."""
    
    def test_serialize_basic_test_row(self):
        """Test serialization of basic test row."""
        row_data = {
            "line_number": 1,
            "text": "Glucose 70 mg/dL 70-99",
            "test_name": "Glucose",
            "result_value": "70",
            "units": "mg/dL",
            "reference_range": "70-99",
            "confidence": 0.85
        }
        result = serialize_test_row(row_data)
        
        assert result.line_number == 1
        assert result.text == "Glucose 70 mg/dL 70-99"
        assert result.test_name == "Glucose"
        assert result.result_value == "70"
        assert result.units == "mg/dL"
        assert result.reference_range == "70-99"
        assert result.reference_range_text == "70-99"
        assert result.confidence == 0.85
    
    def test_serialize_test_row_with_structured_range(self):
        """Test serialization with structured reference range."""
        row_data = {
            "line_number": 2,
            "text": "BUN 15 mg/dL 8-27",
            "test_name": "BUN",
            "result_value": "15",
            "units": "mg/dL",
            "reference_range": {
                "text": "8-27 mg/dL",
                "low": 8.0,
                "high": 27.0
            },
            "flag": "H",
            "codes": {"loinc": "6299-2", "cpt": "84520"}
        }
        result = serialize_test_row(row_data)
        
        assert result.reference_range == "8-27 mg/dL"
        assert result.reference_range_text == "8-27 mg/dL"
        assert result.reference_range_low == 8.0
        assert result.reference_range_high == 27.0
        assert result.flag == "H"
        assert result.flag_norm == "H"
        assert result.codes.loinc == "6299-2"
        assert result.codes.cpt == "84520"
    
    def test_serialize_test_row_with_flag_and_comments(self):
        """Test serialization with flag and comments."""
        row_data = {
            "line_number": 3,
            "text": "Creatinine 2.5 mg/dL 0.7-1.3 H",
            "test_name": "Creatinine",
            "result_value": "2.5",
            "units": "mg/dL",
            "reference_range": "0.7-1.3",
            "flag": "Critical",
            "comments": "Elevated creatinine may indicate kidney dysfunction",
            "methodology": "Enzymatic"
        }
        result = serialize_test_row(row_data)
        
        assert result.flag == "Critical"
        assert result.flag_norm == "CRIT"
        assert result.comments == "Elevated creatinine may indicate kidney dysfunction"
        assert result.methodology == "Enzymatic"
    
    def test_serialize_minimal_test_row(self):
        """Test serialization of minimal test row."""
        row_data = {
            "line_number": 4,
            "text": "Unknown test"
        }
        result = serialize_test_row(row_data)
        
        assert result.line_number == 4
        assert result.text == "Unknown test"
        assert result.test_name is None
        assert result.result_value is None
        assert result.flag is None
        assert result.flag_norm is None


class TestSerializeEhrPayload:
    """Test EHR payload serialization."""
    
    def test_serialize_complete_ehr_payload(self):
        """Test serialization of complete EHR payload."""
        ehr_data = {
            "patient": {
                "last_name": "Doe",
                "first_name": "John",
                "middle": "Q",
                "dob": "1980-01-01",
                "sex": "M",
                "mrn": "12345",
                "phone": "(555) 123-4567"
            },
            "vendor": {
                "name": "LabCorp",
                "account_number": "ACC123",
                "phone": "(800) 555-0123"
            },
            "specimen": {
                "id": "SPEC001",
                "type": "SERUM",
                "collected_at": "2023-01-15T10:30:00Z"
            }
        }
        result = serialize_ehr_payload(ehr_data)
        
        assert result.patient.last_name == "Doe"
        assert result.patient.first_name == "John"
        assert result.patient.dob == "1980-01-01"
        assert result.vendor.name == "LabCorp"
        assert result.vendor.account_number == "ACC123"
        assert result.specimen.id == "SPEC001"
        assert result.specimen.type == "SERUM"
    
    def test_serialize_empty_ehr_payload(self):
        """Test serialization of empty EHR payload."""
        result = serialize_ehr_payload({})
        
        assert result.patient is None
        assert result.vendor is None
        assert result.specimen is None


class TestSerializeLabResult:
    """Test complete lab result serialization."""
    
    def test_serialize_complete_lab_result(self):
        """Test serialization of complete lab result."""
        lab_data = {
            "ehr_payload": {
                "patient": {
                    "last_name": "Smith",
                    "first_name": "Jane",
                    "dob": "1975-05-15",
                    "mrn": "67890"
                }
            },
            "lab_panels": [
                {
                    "id": "panel_1",
                    "name": "Basic Metabolic Panel",
                    "test_count": 2,
                    "test_rows": [
                        {
                            "line_number": 1,
                            "text": "Glucose 90 mg/dL 70-99",
                            "test_name": "Glucose",
                            "result_value": "90",
                            "units": "mg/dL",
                            "reference_range": "70-99",
                            "confidence": 0.95
                        },
                        {
                            "line_number": 2,
                            "text": "Sodium 140 mmol/L 136-145 H",
                            "test_name": "Sodium",
                            "result_value": "140",
                            "units": "mmol/L",
                            "reference_range": {
                                "text": "136-145",
                                "low": 136.0,
                                "high": 145.0
                            },
                            "flag": "H"
                        }
                    ]
                }
            ]
        }
        
        result = serialize_lab_result(lab_data)
        
        # Check document info
        assert result.document_info.patient.last_name == "Smith"
        assert result.document_info.patient.first_name == "Jane"
        
        # Check panels
        assert len(result.lab_panels) == 1
        panel = result.lab_panels[0]
        assert panel.id == "panel_1"
        assert panel.name == "Basic Metabolic Panel"
        assert panel.test_count == 2
        
        # Check test rows
        assert len(panel.test_rows) == 2
        
        glucose_row = panel.test_rows[0]
        assert glucose_row.test_name == "Glucose"
        assert glucose_row.result_value == "90"
        assert glucose_row.reference_range == "70-99"
        assert glucose_row.reference_range_text == "70-99"
        
        sodium_row = panel.test_rows[1]
        assert sodium_row.test_name == "Sodium"
        assert sodium_row.flag == "H"
        assert sodium_row.flag_norm == "H"
        assert sodium_row.reference_range_low == 136.0
        assert sodium_row.reference_range_high == 145.0
    
    def test_serialize_minimal_lab_result(self):
        """Test serialization of minimal lab result."""
        lab_data = {
            "lab_panels": []
        }
        
        result = serialize_lab_result(lab_data)
        
        assert len(result.lab_panels) == 0
        assert result.document_info.patient is None
    
    def test_serialize_lab_result_null_safety(self):
        """Test null safety in lab result serialization."""
        lab_data = {
            "ehr_payload": None,
            "lab_panels": [
                {
                    "id": "panel_1",
                    "name": None,
                    "test_rows": [
                        {
                            "line_number": 1,
                            "text": "Test with nulls",
                            "test_name": None,
                            "result_value": None,
                            "reference_range": None,
                            "flag": None
                        }
                    ]
                }
            ]
        }
        
        result = serialize_lab_result(lab_data)
        
        # Should not raise exceptions
        assert result.document_info.patient is None
        assert len(result.lab_panels) == 1
        
        test_row = result.lab_panels[0].test_rows[0]
        assert test_row.test_name is None
        assert test_row.flag is None
        assert test_row.flag_norm is None
        assert test_row.reference_range is None


if __name__ == "__main__":
    pytest.main([__file__])
