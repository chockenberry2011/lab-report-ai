"""
Tests for panel naming functionality in composer
"""

import unittest
from unittest.mock import Mock, patch
from services.worker.composer.composer import PanelComposer, LineContext


class TestPanelNaming(unittest.TestCase):
    """Test panel naming improvements"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.composer = PanelComposer()
    
    def test_guess_panel_name_with_bold_header(self):
        """Test that bold headers are preferred for panel naming"""
        # Mock line contexts with a bold header before test rows
        contexts = [
            LineContext("Some junk", "JUNK", 1, 0, 0.1, 0, 100, 12, False),
            LineContext("CHEMISTRY PANEL", "UNKNOWN", 1, 1, 0.2, 0, 200, 12, True),  # Bold
            LineContext("Glucose 95 mg/dL", "TEST_ROW", 1, 2, 0.3, 0, 300, 12, False),
            LineContext("Sodium 140 mEq/L", "TEST_ROW", 1, 3, 0.4, 0, 300, 12, False),
        ]
        
        self.composer._current_line_contexts = contexts
        test_row_context = contexts[2]  # First test row
        
        result = self.composer._guess_panel_name(test_row_context)
        self.assertEqual(result, "CHEMISTRY PANEL")
    
    def test_guess_panel_name_with_caps_header(self):
        """Test that ALL CAPS headers are used when no bold is available"""
        contexts = [
            LineContext("Patient Info", "UNKNOWN", 1, 0, 0.1, 0, 100, 12, False),
            LineContext("LIPID PROFILE COMPLETE", "UNKNOWN", 1, 1, 0.2, 0, 200, 12, False),
            LineContext("Cholesterol 180 mg/dL", "TEST_ROW", 1, 2, 0.3, 0, 300, 12, False),
        ]
        
        self.composer._current_line_contexts = contexts
        test_row_context = contexts[2]
        
        result = self.composer._guess_panel_name(test_row_context)
        self.assertEqual(result, "LIPID PROFILE COMPLETE")
    
    def test_guess_panel_name_with_alphabetic_fallback(self):
        """Test fallback to lines with ≥2 alphabetic tokens"""
        contexts = [
            LineContext("123", "UNKNOWN", 1, 0, 0.1, 0, 100, 12, False),
            LineContext("Complete Blood Count", "UNKNOWN", 1, 1, 0.2, 0, 200, 12, False),
            LineContext("WBC 7.5 K/uL", "TEST_ROW", 1, 2, 0.3, 0, 300, 12, False),
        ]
        
        self.composer._current_line_contexts = contexts
        test_row_context = contexts[2]
        
        result = self.composer._guess_panel_name(test_row_context)
        self.assertEqual(result, "Complete Blood Count")
    
    def test_guess_panel_name_returns_unnamed_when_no_suitable_header(self):
        """Test that UNNAMED is returned when no suitable header is found"""
        contexts = [
            LineContext("123", "UNKNOWN", 1, 0, 0.1, 0, 100, 12, False),
            LineContext("x", "UNKNOWN", 1, 1, 0.2, 0, 200, 12, False),
            LineContext("WBC 7.5 K/uL", "TEST_ROW", 1, 2, 0.3, 0, 300, 12, False),
        ]
        
        self.composer._current_line_contexts = contexts
        test_row_context = contexts[2]
        
        result = self.composer._guess_panel_name(test_row_context)
        self.assertEqual(result, "UNNAMED")
    
    def test_guess_panel_name_skips_junk_and_headers(self):
        """Test that JUNK and header/footer lines are skipped"""
        contexts = [
            LineContext("Page Header Content", "PAGE_HEADER", 1, 0, 0.05, 0, 100, 12, False),
            LineContext("Some junk text", "JUNK", 1, 1, 0.1, 0, 150, 12, False),
            LineContext("METABOLIC PANEL", "UNKNOWN", 1, 2, 0.15, 0, 200, 12, True),
            LineContext("Glucose 95 mg/dL", "TEST_ROW", 1, 3, 0.2, 0, 300, 12, False),
        ]
        
        self.composer._current_line_contexts = contexts
        test_row_context = contexts[3]
        
        result = self.composer._guess_panel_name(test_row_context)
        self.assertEqual(result, "METABOLIC PANEL")
    
    def test_guess_panel_name_limits_lookback_to_8_lines(self):
        """Test that only 8 non-junk lines are checked"""
        # Create 10 lines before the test row, with a good header at position 0
        contexts = [
            LineContext("GOOD HEADER NAME", "UNKNOWN", 1, 0, 0.01, 0, 200, 12, True),
        ]
        
        # Add 9 more non-junk lines to exceed the 8-line limit
        for i in range(1, 10):
            contexts.append(
                LineContext(f"Line {i}", "UNKNOWN", 1, i, 0.01 + i*0.01, 0, 200, 12, False)
            )
        
        # Add the test row
        contexts.append(
            LineContext("Test 123 units", "TEST_ROW", 1, 10, 0.2, 0, 300, 12, False)
        )
        
        self.composer._current_line_contexts = contexts
        test_row_context = contexts[10]  # The test row
        
        # Should return UNNAMED since the good header is beyond the 8-line limit
        result = self.composer._guess_panel_name(test_row_context)
        self.assertEqual(result, "UNNAMED")
    
    def test_is_likely_panel_header_bold_priority(self):
        """Test that bold text gets priority"""
        context = LineContext("Chemistry Panel", "UNKNOWN", 1, 1, 0.2, 0, 200, 12, True)
        result = self.composer._is_likely_panel_header("Chemistry Panel", context)
        self.assertTrue(result)
    
    def test_is_likely_panel_header_caps_priority(self):
        """Test that ALL CAPS gets priority"""
        context = LineContext("LIPID PROFILE", "UNKNOWN", 1, 1, 0.2, 0, 200, 12, False)
        result = self.composer._is_likely_panel_header("LIPID PROFILE", context)
        self.assertTrue(result)
    
    def test_is_likely_panel_header_alphabetic_fallback(self):
        """Test alphabetic token fallback"""
        context = LineContext("Complete Blood Count", "UNKNOWN", 1, 1, 0.2, 0, 200, 12, False)
        result = self.composer._is_likely_panel_header("Complete Blood Count", context)
        self.assertTrue(result)
    
    def test_is_likely_panel_header_rejects_insufficient_tokens(self):
        """Test that headers with insufficient tokens are rejected"""
        context = LineContext("Test", "UNKNOWN", 1, 1, 0.2, 0, 200, 12, True)
        result = self.composer._is_likely_panel_header("Test", context)
        self.assertFalse(result)
    
    def test_boost_continuity_for_common_units(self):
        """Test that panels get continuity boost for common units"""
        from services.worker.composer.schemas import Panel, TestRow
        
        # Create a panel with test rows sharing common units
        panel = Panel(
            id="test",
            name="Test Panel", 
            started_at_page=1,
            started_at_line=1,
            continuity_score=0.3,
            open=False,
            test_rows=[]
        )
        
        # Add test rows with mg/dL units (common)
        panel.test_rows = [
            TestRow("Glucose 95", 1, 1, 0.1, units="mg/dL"),
            TestRow("Creatinine 1.0", 1, 2, 0.2, units="mg/dL"),
            TestRow("BUN 15", 1, 3, 0.3, units="mg/dL"),
        ]
        
        original_score = panel.continuity_score
        self.composer._boost_continuity_for_common_units(panel)
        
        # Should be boosted by 0.1
        self.assertAlmostEqual(panel.continuity_score, original_score + 0.1, places=2)
    
    def test_boost_continuity_no_boost_for_diverse_units(self):
        """Test that panels with diverse units don't get boosted"""
        from services.worker.composer.schemas import Panel, TestRow
        
        panel = Panel(
            id="test",
            name="Test Panel",
            started_at_page=1,
            started_at_line=1,
            continuity_score=0.3,
            open=False,
            test_rows=[]
        )
        
        # Add test rows with different units
        panel.test_rows = [
            TestRow("Glucose 95", 1, 1, 0.1, units="mg/dL"),
            TestRow("Sodium 140", 1, 2, 0.2, units="mEq/L"),
            TestRow("WBC 7.5", 1, 3, 0.3, units="K/uL"),
        ]
        
        original_score = panel.continuity_score
        self.composer._boost_continuity_for_common_units(panel)
        
        # Should remain unchanged
        self.assertEqual(panel.continuity_score, original_score)
    
    def test_boost_continuity_caps_at_1_0(self):
        """Test that continuity score doesn't exceed 1.0"""
        from services.worker.composer.schemas import Panel, TestRow
        
        panel = Panel(
            id="test",
            name="Test Panel",
            started_at_page=1,
            started_at_line=1,
            continuity_score=0.95,  # High initial score
            open=False,
            test_rows=[]
        )
        
        panel.test_rows = [
            TestRow("Test1", 1, 1, 0.1, units="mg/dL"),
            TestRow("Test2", 1, 2, 0.2, units="mg/dL"),
        ]
        
        self.composer._boost_continuity_for_common_units(panel)
        
        # Should be capped at 1.0
        self.assertEqual(panel.continuity_score, 1.0)
    
    def test_create_fallback_panel_uses_guessed_name(self):
        """Test that fallback panel creation uses guessed names"""
        from services.worker.composer.schemas import Panel, TestRow
        
        contexts = [
            LineContext("HEMATOLOGY PANEL", "UNKNOWN", 1, 0, 0.1, 0, 200, 12, True),
            LineContext("WBC 7.5 K/uL", "TEST_ROW", 1, 1, 0.2, 0, 300, 12, False),
        ]
        
        self.composer._current_line_contexts = contexts
        test_row_buffer = [contexts[1]]
        
        self.composer._create_fallback_panel(test_row_buffer)
        
        # Should have created a panel with the guessed name
        self.assertEqual(len(self.composer.panels), 1)
        panel = self.composer.panels[0]
        self.assertEqual(panel.name, "HEMATOLOGY PANEL")
        self.assertGreater(panel.continuity_score, 0.3)  # Should be boosted


if __name__ == '__main__':
    unittest.main()