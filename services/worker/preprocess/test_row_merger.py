"""
Unit tests for row_merger module.
"""

import unittest
from row_merger import merge_row_cells


class TestRowMerger(unittest.TestCase):
    
    def test_merge_multiple_cells_same_row(self):
        """Test that multiple cells with close yNorm merge into single line in x-order."""
        lines = [
            {
                "page": 1,
                "text": "Glucose",
                "xLeft": 10.0,
                "xRight": 50.0,
                "yNorm": 0.5,
                "fontSize": 12.0,
                "isBold": False,
                "hasText": True
            },
            {
                "page": 1,
                "text": "95",
                "xLeft": 60.0,
                "xRight": 80.0,
                "yNorm": 0.501,  # Very close to first cell
                "fontSize": 12.0,
                "isBold": False,
                "hasText": True
            },
            {
                "page": 1,
                "text": "mg/dL",
                "xLeft": 90.0,
                "xRight": 120.0,
                "yNorm": 0.499,  # Very close to first cell
                "fontSize": 12.0,
                "isBold": False,
                "hasText": True
            }
        ]
        
        merged = merge_row_cells(lines, y_tol=0.006)
        
        # Should merge into one line
        self.assertEqual(len(merged), 1)
        
        # Should be in x-order (left to right)
        self.assertEqual(merged[0]["text"], "Glucose\t95\tmg/dL")
        
        # Should have merged properties
        self.assertEqual(merged[0]["page"], 1)
        self.assertEqual(merged[0]["xLeft"], 10.0)  # min xLeft
        self.assertEqual(merged[0]["xRight"], 120.0)  # max xRight
        self.assertAlmostEqual(merged[0]["yNorm"], 0.5, places=2)  # mean yNorm
        self.assertFalse(merged[0]["isBold"])  # no bold cells
        self.assertEqual(len(merged[0]["cells"]), 3)  # original cells preserved
    
    def test_different_rows_not_merged(self):
        """Test that cells with different yNorm (different rows) are not merged."""
        lines = [
            {
                "page": 1,
                "text": "Test 1",
                "xLeft": 10.0,
                "xRight": 50.0,
                "yNorm": 0.5,
                "fontSize": 12.0,
                "isBold": False,
                "hasText": True
            },
            {
                "page": 1,
                "text": "Test 2",
                "xLeft": 10.0,
                "xRight": 50.0,
                "yNorm": 0.6,  # Different row (> tolerance)
                "fontSize": 12.0,
                "isBold": False,
                "hasText": True
            }
        ]
        
        merged = merge_row_cells(lines, y_tol=0.006)
        
        # Should keep as separate lines since they're different rows
        # But single cells need to meet keep criteria (contains digit, bold+large font, or long text)
        # These should be kept because they're long enough (>= 10 chars is False, but let's make them meet criteria)
        
        # Actually, let's modify the test to use cells that meet criteria
        lines[0]["text"] = "Test with 123"  # Contains digit
        lines[1]["text"] = "Another test 456"  # Contains digit
        
        merged = merge_row_cells(lines, y_tol=0.006)
        self.assertEqual(len(merged), 2)
    
    def test_bold_any_merging(self):
        """Test that isBold is True if any cell in row is bold."""
        lines = [
            {
                "page": 1,
                "text": "Normal",
                "xLeft": 10.0,
                "xRight": 50.0,
                "yNorm": 0.5,
                "fontSize": 12.0,
                "isBold": False,
                "hasText": True
            },
            {
                "page": 1,
                "text": "Bold",
                "xLeft": 60.0,
                "xRight": 90.0,
                "yNorm": 0.501,
                "fontSize": 12.0,
                "isBold": True,  # This cell is bold
                "hasText": True
            }
        ]
        
        merged = merge_row_cells(lines, y_tol=0.006)
        
        # Should merge and be bold because one cell was bold
        self.assertEqual(len(merged), 1)
        self.assertTrue(merged[0]["isBold"])
    
    def test_single_cell_filtering(self):
        """Test that single cells are filtered based on criteria."""
        lines = [
            {
                "page": 1,
                "text": "X",  # Short, no digit, not bold
                "xLeft": 10.0,
                "xRight": 20.0,
                "yNorm": 0.5,
                "fontSize": 10.0,
                "isBold": False,
                "hasText": True
            },
            {
                "page": 1,
                "text": "Value: 123",  # Contains digit - should keep
                "xLeft": 10.0,
                "xRight": 80.0,
                "yNorm": 0.6,
                "fontSize": 10.0,
                "isBold": False,
                "hasText": True
            },
            {
                "page": 1,
                "text": "SECTION HEADER",  # Bold and large font - should keep
                "xLeft": 10.0,
                "xRight": 120.0,
                "yNorm": 0.7,
                "fontSize": 14.0,
                "isBold": True,
                "hasText": True
            }
        ]
        
        merged = merge_row_cells(lines, y_tol=0.006)
        
        # Should keep 2 lines (the digit one and the header), filter out the short one
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["text"], "Value: 123")
        self.assertEqual(merged[1]["text"], "SECTION HEADER")
    
    def test_empty_input(self):
        """Test handling of empty input."""
        merged = merge_row_cells([])
        self.assertEqual(len(merged), 0)
    
    def test_multiple_pages(self):
        """Test that pages are processed separately."""
        lines = [
            {
                "page": 1,
                "text": "Page 1 Cell 1",
                "xLeft": 10.0,
                "xRight": 80.0,
                "yNorm": 0.5,
                "fontSize": 12.0,
                "isBold": False,
                "hasText": True
            },
            {
                "page": 1,
                "text": "Page 1 Cell 2", 
                "xLeft": 90.0,
                "xRight": 160.0,
                "yNorm": 0.501,  # Same row as previous
                "fontSize": 12.0,
                "isBold": False,
                "hasText": True
            },
            {
                "page": 2,
                "text": "Page 2 content",
                "xLeft": 10.0,
                "xRight": 100.0,
                "yNorm": 0.5,  # Same yNorm but different page
                "fontSize": 12.0,
                "isBold": False,
                "hasText": True
            }
        ]
        
        merged = merge_row_cells(lines, y_tol=0.006)
        
        # Should have 2 lines: merged from page 1, single from page 2
        self.assertEqual(len(merged), 2)
        
        # Find the merged page 1 line
        page1_line = next(line for line in merged if line["page"] == 1)
        self.assertEqual(page1_line["text"], "Page 1 Cell 1\tPage 1 Cell 2")
        
        # Find the page 2 line
        page2_line = next(line for line in merged if line["page"] == 2)
        self.assertEqual(page2_line["text"], "Page 2 content")


if __name__ == "__main__":
    unittest.main()