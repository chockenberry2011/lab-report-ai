"""
Unit tests for is_probably_test_row function to prevent header/envelope lines
from being treated as TEST_ROW.
"""

from services.worker.composer.composer import is_probably_test_row


class TestIsProbablyTestRow:
    """Test cases for is_probably_test_row function"""

    def test_valid_test_rows(self):
        """Test cases that should be identified as valid test rows"""
        valid_cases = [
            # Basic test rows with medical units
            "Glucose 95 mg/dL 70-99",
            "TSH 4.71 High mIU/L 0.45-4.5",
            "eGFR 52 Low mL/min/1.73 >59",
            "Sodium 150 High mmol/L 134-144",
            "WBC 6.5 K/uL 4.0-10.5",
            "Hemoglobin 13.2 g/dL 12.0-15.5",
            "Creatinine 1.1 mg/dL 0.7-1.3",
            
            # Test rows with percentage units
            "HbA1c 6.2 % 4.0-6.0",
            "Hematocrit 42.1 % 36.0-46.0",
            
            # Test rows with activity units
            "ALT 25 IU/L 7-56",
            "AST 32 U/L 10-40",
            
            # Test rows with blood count units
            "Platelets 250 K/uL 150-450",
            "RBC 4.5 M/uL 4.2-5.4",
            
            # Test rows without units but with early numeric position
            "Temperature 98.6",
            "Age 45",
            "Weight 150",
        ]
        
        for case in valid_cases:
            assert is_probably_test_row(case), f"Should identify as test row: '{case}'"

    def test_header_patterns_rejected(self):
        """Test cases with header patterns that should be rejected"""
        header_cases = [
            # Specimen/Lab identifiers
            "Specimen ID: ABC123456",
            "Accession: 2023-001234",
            "Acct # 987654321",
            "MRN: 12345678",
            "Patient ID: PAT001",
            
            # Contact information
            "Phone: (555) 123-4567",
            "Fax: 555-123-4568",
            
            # Lab information
            "CLIA # 05D0123456",
            "NPI: 1234567890",
            "Director: Dr. Jane Smith",
            "Location: Main Lab",
            
            # Timing information
            "Collected: 2023-01-15 08:30",
            "Received: 2023-01-15 10:00",
            "Entered: 2023-01-15 14:30",
            "Reported: 2023-01-15 16:45",
            
            # Route information
            "Rte: STAT",
        ]
        
        for case in header_cases:
            assert not is_probably_test_row(case), f"Should reject header pattern: '{case}'"

    def test_phone_clia_npi_patterns_rejected(self):
        """Test specific phone/CLIA/NPI patterns from the requirements"""
        reject_cases = [
            # Phone number formats
            "Contact: (555) 123-4567 for questions",
            "Call 555-123-4567 for results",
            "Emergency: (911) 555-0123",
            
            # CLIA patterns
            "CLIA # 05D0123456",
            "Laboratory CLIA#: 42D1234567",
            "CLIA 11D9876543",
            
            # NPI patterns  
            "NPI: 1234567890",
            "Provider NPI 9876543210",
            "NPI# 1122334455",
        ]
        
        for case in reject_cases:
            assert not is_probably_test_row(case), f"Should reject pattern: '{case}'"

    def test_multiple_colon_labels_rejected(self):
        """Test cases with multiple colon labels that should be rejected"""
        multi_colon_cases = [
            "Name: John Doe, DOB: 1990-01-01",
            "Patient: Jane Smith, MRN: 12345, DOB: 1985-05-15",
            "Lab: Quest, Location: Main, Phone: 555-1234",
            "Collected: 08:00, Received: 10:00, Reported: 14:00",
        ]
        
        for case in multi_colon_cases:
            assert not is_probably_test_row(case), f"Should reject multiple colons: '{case}'"

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Empty/whitespace
        assert not is_probably_test_row("")
        assert not is_probably_test_row("   ")
        assert not is_probably_test_row("\n\t")
        
        # Single tokens
        assert not is_probably_test_row("Glucose")
        assert not is_probably_test_row("123")
        
        # No numeric values
        assert not is_probably_test_row("Patient Name John Doe")
        assert not is_probably_test_row("Lab Report Summary")
        
        # Numeric too late in sequence
        assert not is_probably_test_row("This is a very long test name with numeric 95 mg/dL")
        
        # Invalid first tokens
        assert not is_probably_test_row("123 45 mg/dL")  # Number as first token
        assert not is_probably_test_row("The 95 mg/dL")  # Article as first token
        assert not is_probably_test_row("Label: 95 mg/dL")  # Colon in first token

    def test_borderline_cases(self):
        """Test borderline cases that might be ambiguous"""
        # Cases with numbers but no clear medical context
        borderline_cases = [
            "Page 1 of 3",
            "Total 25 items",
            "Section 2.5 results",
            "Reference 123 values",
        ]
        
        for case in borderline_cases:
            # These should be rejected as they don't have medical units
            # and don't follow clear test row patterns
            assert not is_probably_test_row(case), f"Should reject borderline case: '{case}'"

    def test_medical_units_recognition(self):
        """Test recognition of various medical units"""
        medical_unit_cases = [
            ("Glucose 95 mg/dL", True),
            ("TSH 2.5 mIU/L", True), 
            ("eGFR 85 mL/min/1.73", True),
            ("WBC 7.2 K/uL", True),
            ("Temperature 98.6 F", True),
            ("Pressure 120 mmHg", True),
            ("Time 45 minutes", True),
            ("Volume 500 mL", True),
            ("Weight 75 kg", True),
            
            # Non-medical units should be more restrictive
            ("Distance 10 miles", False),
            ("Price 25 dollars", False),
        ]
        
        for case, expected in medical_unit_cases:
            result = is_probably_test_row(case)
            assert result == expected, f"Medical unit test failed for: '{case}' (expected {expected}, got {result})"

    def test_case_insensitivity(self):
        """Test that header pattern matching is case insensitive"""
        case_variants = [
            "SPECIMEN ID: ABC123",
            "specimen id: abc123", 
            "Specimen Id: Abc123",
            "PHONE: (555) 123-4567",
            "phone: (555) 123-4567",
            "Phone: (555) 123-4567",
            "CLIA # 05D0123456",
            "clia # 05d0123456",
        ]
        
        for case in case_variants:
            assert not is_probably_test_row(case), f"Should reject case variant: '{case}'"