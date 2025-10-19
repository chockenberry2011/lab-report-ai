"""
Unit tests for heuristics module.
"""

import unittest
from .heuristics import tag_rows_heuristic, _is_test_row_heuristic


class TestHeuristics(unittest.TestCase):
    
    def test_digit_and_units(self):
        """Test detection of lines with digits and units."""
        # Should detect
        line = {"text": "Glucose\t95\tmg/dL\t70-100", "predicted_role": "OTHER"}
        self.assertTrue(_is_test_row_heuristic(line))
        
        line = {"text": "Hemoglobin 12.5 g/dL", "predicted_role": "OTHER"}
        self.assertTrue(_is_test_row_heuristic(line))
        
        line = {"text": "WBC 5.2 x10³/µL", "predicted_role": "OTHER"}
        self.assertTrue(_is_test_row_heuristic(line))
        
        # Should not detect (no digits)
        line = {"text": "Glucose\tmg/dL\tNormal", "predicted_role": "OTHER"}
        self.assertFalse(_is_test_row_heuristic(line))
        
        # Should not detect (no units)
        line = {"text": "Patient Name: John Doe 123", "predicted_role": "OTHER"}
        self.assertFalse(_is_test_row_heuristic(line))
    
    def test_reference_range(self):
        """Test detection of reference range patterns."""
        # Should detect
        line = {"text": "Normal range: 70-100", "predicted_role": "OTHER"}
        self.assertTrue(_is_test_row_heuristic(line))
        
        line = {"text": "Reference: 2.5 - 4.0", "predicted_role": "OTHER"}
        self.assertTrue(_is_test_row_heuristic(line))
        
        line = {"text": "Range 1.2–3.5 is normal", "predicted_role": "OTHER"}
        self.assertTrue(_is_test_row_heuristic(line))
        
        # Should not detect
        line = {"text": "No range here", "predicted_role": "OTHER"}
        self.assertFalse(_is_test_row_heuristic(line))
    
    def test_flags_and_numbers(self):
        """Test detection of flag tokens with numbers."""
        # Should detect
        line = {"text": "Glucose 150 H", "predicted_role": "OTHER"}
        self.assertTrue(_is_test_row_heuristic(line))
        
        line = {"text": "Result: 2.1 L LOW", "predicted_role": "OTHER"}
        self.assertTrue(_is_test_row_heuristic(line))
        
        line = {"text": "CRITICAL value 200", "predicted_role": "OTHER"}
        self.assertTrue(_is_test_row_heuristic(line))
        
        # Should not detect (no numbers)
        line = {"text": "Status: HIGH", "predicted_role": "OTHER"}
        self.assertFalse(_is_test_row_heuristic(line))
        
        # Should not detect (no flags)
        line = {"text": "Normal value 100", "predicted_role": "OTHER"}
        self.assertFalse(_is_test_row_heuristic(line))
    
    def test_section_panel_preservation(self):
        """Test that SECTION_PANEL lines are not overridden."""
        line = {"text": "CBC WITH DIFFERENTIAL 123 mg/dL H", "predicted_role": "SECTION_PANEL"}
        self.assertFalse(_is_test_row_heuristic(line))
    
    def test_disclaimer_exclusion(self):
        """Test that long disclaimers are excluded."""
        # Should exclude (>= 12 words, no tabs, no units)
        disclaimer = {
            "text": "This report contains confidential medical information and should not be shared without proper authorization from the patient or legal guardian",
            "predicted_role": "OTHER"
        }
        self.assertFalse(_is_test_row_heuristic(disclaimer))
        
        # Should not exclude (has tabs)
        tabular = {
            "text": "This is a long disclaimer text\tbut it has tabs\tso it might be tabular data",
            "predicted_role": "OTHER"
        }
        # This would still be excluded because no digits/units, but the tab check works
        
        # Should not exclude (has units)
        with_units = {
            "text": "This is a long disclaimer but it mentions that normal glucose is measured in mg/dL units",
            "predicted_role": "OTHER"
        }
        # Would not be excluded due to units, but still not TEST_ROW without digits
    
    def test_tag_rows_heuristic_full(self):
        """Test the full tag_rows_heuristic function."""
        lines = [
            {"text": "COMPREHENSIVE METABOLIC PANEL", "predicted_role": "SECTION_PANEL"},
            {"text": "Glucose\t95\tmg/dL\t70-100", "predicted_role": "OTHER"},
            {"text": "Sodium 142 H", "predicted_role": "OTHER"},
            {"text": "Reference range: 136-145", "predicted_role": "OTHER"},
            {"text": "Patient information and other details", "predicted_role": "OTHER"},
            {"text": "This is a very long disclaimer with many words but no medical values or units", "predicted_role": "OTHER"}
        ]
        
        test_row_indexes = tag_rows_heuristic(lines)
        
        # Should identify indexes 1, 2, 3 as TEST_ROW
        expected = {1, 2, 3}
        self.assertEqual(test_row_indexes, expected)


if __name__ == "__main__":
    unittest.main()