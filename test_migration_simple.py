#!/usr/bin/env python3
"""
Simple test for the corrections migration utility.
Creates test files and validates the migration works correctly.
"""

import json
import sys
import tempfile
from pathlib import Path

# Add the services/api directory to the path
sys.path.insert(0, "services/api")

from migrations.corrections_array_migration import CorrectionsArrayMigrator


def test_basic_migration():
    """Test basic migration functionality."""
    print("🧪 Testing basic migration functionality...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)

        # Create test files
        test_files = {
            "result1": {"field": "test_name", "new_value": "Glucose"},  # Object (needs migration)
            "result2": [{"field": "test_name", "new_value": "Cholesterol"}],  # Array (already good)
            "result3": {"field": "result_value", "new_value": "72", "line_number": 15},  # Object (needs migration)
        }

        print(f"Creating test files in {base_dir}...")
        for result_id, data in test_files.items():
            result_dir = base_dir / result_id
            result_dir.mkdir()
            corrections_file = result_dir / "corrections.json"
            with corrections_file.open("w") as f:
                json.dump(data, f, indent=2)
            print(f"  Created: {corrections_file}")

        # Test scan-only mode
        print("\n📋 Running scan-only mode...")
        migrator = CorrectionsArrayMigrator(str(base_dir))
        stats = migrator.scan_only()

        print(f"  Files scanned: {stats.total_files_scanned}")
        print(f"  Already arrays: {stats.files_already_arrays}")
        print(f"  Need migration: {stats.files_needing_migration}")
        print(f"  Errors: {len(stats.errors)}")

        # Verify scan results
        assert stats.total_files_scanned == 3
        assert stats.files_already_arrays == 1  # result2
        assert stats.files_needing_migration == 2  # result1, result3
        print("✅ Scan-only mode works correctly")

        # Test actual migration
        print("\n🔧 Running migration...")
        migrator.stats = migrator.__class__(str(base_dir)).stats  # Reset stats
        stats = migrator.migrate(create_backups=True)

        print(f"  Files migrated: {stats.files_migrated}")
        print(f"  Backups created: {stats.backups_created}")
        print(f"  Errors: {len(stats.errors)}")

        # Verify migration results
        assert stats.files_migrated == 2
        assert stats.backups_created == 2
        assert stats.files_with_errors == 0
        print("✅ Migration completed successfully")

        # Verify files are now arrays
        print("\n🔍 Verifying migrated files...")
        for result_id in ["result1", "result3"]:
            corrections_file = base_dir / result_id / "corrections.json"
            with corrections_file.open() as f:
                data = json.load(f)
            assert isinstance(data, list), f"{result_id} should be array"
            assert len(data) == 1, f"{result_id} should have 1 element"
            print(f"  ✅ {result_id} is now array format")

        # Verify result2 is unchanged
        result2_file = base_dir / "result2" / "corrections.json"
        with result2_file.open() as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["field"] == "test_name"
        print("  ✅ result2 unchanged (was already array)")

        # Verify backups exist
        backup_files = list(base_dir.rglob("*.bak.*"))
        assert len(backup_files) == 2
        print(f"  ✅ {len(backup_files)} backup files created")

        # Test idempotent behavior
        print("\n🔁 Testing idempotent behavior...")
        migrator.stats = migrator.__class__(str(base_dir)).stats  # Reset stats
        stats = migrator.migrate(create_backups=True)

        assert stats.files_migrated == 0  # No files needed migration
        assert stats.files_already_arrays == 3  # All are now arrays
        print("✅ Idempotent behavior verified")

    return True


def test_error_handling():
    """Test error handling scenarios."""
    print("\n🧪 Testing error handling...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)

        # Create file with invalid JSON
        result_dir = base_dir / "invalid_json"
        result_dir.mkdir()
        invalid_file = result_dir / "corrections.json"
        invalid_file.write_text("{ invalid json }")

        # Create file with unexpected type
        result_dir2 = base_dir / "unexpected_type"
        result_dir2.mkdir()
        unexpected_file = result_dir2 / "corrections.json"
        with unexpected_file.open("w") as f:
            json.dump("string_instead_of_object_or_array", f)

        migrator = CorrectionsArrayMigrator(str(base_dir))
        stats = migrator.scan_only()

        assert stats.total_files_scanned == 2
        assert stats.files_with_errors == 2
        assert len(stats.errors) == 2
        print("✅ Error handling works correctly")

    return True


def main():
    """Run all tests."""
    print("🚀 Starting migration utility tests...\n")

    tests = [
        test_basic_migration,
        test_error_handling,
    ]

    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"❌ Test {test.__name__} failed")
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")

    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")

    if passed == len(tests):
        print("✅ All migration tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(main())