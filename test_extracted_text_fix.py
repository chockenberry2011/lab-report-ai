#!/usr/bin/env python3
"""
Quick validation script to test the normalize_result_id function and 
extracted text compatibility route fixes.
"""

import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "services" / "api"))

def test_normalize_function():
    """Test the normalize_result_id function."""
    print("🧪 Testing normalize_result_id function...")
    
    try:
        from services.api.api.utils.ids import normalize_result_id
        
        test_cases = [
            ("abc.03_compose.debug", "abc"),
            ("abc.debug", "abc"),
            ("abc", "abc"),
            ("uuid-1234.03_compose.debug", "uuid-1234"),
            ("test-id.debug", "test-id"),
            ("no-suffix", "no-suffix"),
        ]
        
        for input_id, expected in test_cases:
            result = normalize_result_id(input_id)
            assert result == expected, f"Expected {expected}, got {result} for input {input_id}"
            print(f"  ✅ {input_id} -> {result}")
        
        print("✅ normalize_result_id function works correctly!")
        return True
        
    except ImportError as e:
        print(f"❌ Could not import function: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_import_structure():
    """Test that all imports work correctly."""
    print("🧪 Testing import structure...")
    
    try:
        from services.api.api.results import router
        from services.api.api.utils.ids import normalize_result_id
        print("  ✅ results module imports correctly")
        
        from services.api.api.main import app
        print("  ✅ main app imports correctly")
        
        print("✅ All imports work correctly!")
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Testing extracted text compatibility fixes...\n")
    
    success = True
    success &= test_import_structure()
    print()
    success &= test_normalize_function()
    
    if success:
        print("\n🎉 All tests passed! The fixes are ready.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        sys.exit(1)
