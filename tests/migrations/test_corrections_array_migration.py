"""
Unit tests for corrections array migration utility.

Tests all aspects of the migration:
- File discovery and scanning
- Analysis of different file formats
- Backup creation
- Object-to-array migration
- Idempotent behavior
- Error handling
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

import sys
import os

# Add the services/api directory to the path so we can import the migration module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/api"))

from migrations.corrections_array_migration import (
    CorrectionsArrayMigrator,
    CorrectionsMigrationStats
)


class TestCorrectionsMigrationStats:
    """Test the statistics tracking class."""

    def test_stats_initialization(self):
        """Test that stats are initialized with zero values."""
        stats = CorrectionsMigrationStats()

        assert stats.total_files_scanned == 0
        assert stats.files_needing_migration == 0
        assert stats.files_migrated == 0
        assert stats.files_already_arrays == 0
        assert stats.files_with_errors == 0
        assert stats.backups_created == 0
        assert stats.errors == []


class TestCorrectionsArrayMigrator:
    """Test the main migration functionality."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary data directory for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)

    @pytest.fixture
    def migrator(self, temp_data_dir):
        """Create a migrator instance with temporary directory."""
        return CorrectionsArrayMigrator(str(temp_data_dir))

    def create_corrections_file(self, base_dir: Path, result_id: str, data: any) -> Path:
        """Helper to create a corrections file with given data."""
        corrections_dir = base_dir / result_id
        corrections_dir.mkdir(parents=True, exist_ok=True)
        corrections_file = corrections_dir / "corrections.json"

        with corrections_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return corrections_file

    def test_find_corrections_files_empty_directory(self, migrator):
        """Test finding corrections files in empty directory."""
        files = migrator.find_corrections_files()
        assert files == []

    def test_find_corrections_files_nonexistent_directory(self, temp_data_dir):
        """Test finding corrections files when directory doesn't exist."""
        nonexistent_dir = temp_data_dir / "nonexistent"
        migrator = CorrectionsArrayMigrator(str(nonexistent_dir))

        files = migrator.find_corrections_files()
        assert files == []

    def test_find_corrections_files_multiple_files(self, migrator, temp_data_dir):
        """Test finding multiple corrections files."""
        # Create multiple corrections files
        self.create_corrections_file(temp_data_dir, "result1", {"field": "value1"})
        self.create_corrections_file(temp_data_dir, "result2", [{"field": "value2"}])
        self.create_corrections_file(temp_data_dir, "result3", {"field": "value3"})

        files = migrator.find_corrections_files()

        assert len(files) == 3
        filenames = [f.parent.name for f in files]
        assert "result1" in filenames
        assert "result2" in filenames
        assert "result3" in filenames

    def test_analyze_file_array_format(self, migrator, temp_data_dir):
        """Test analyzing file that's already in array format."""
        array_data = [{"field": "test", "value": "data"}]
        file_path = self.create_corrections_file(temp_data_dir, "test_array", array_data)

        needs_migration, data, error = migrator.analyze_file(file_path)

        assert not needs_migration
        assert data == array_data
        assert error == ""

    def test_analyze_file_object_format(self, migrator, temp_data_dir):
        """Test analyzing file that's in object format (needs migration)."""
        object_data = {"field": "test", "value": "data"}
        file_path = self.create_corrections_file(temp_data_dir, "test_object", object_data)

        needs_migration, data, error = migrator.analyze_file(file_path)

        assert needs_migration
        assert data == object_data
        assert error == ""

    def test_analyze_file_string_format(self, migrator, temp_data_dir):
        """Test analyzing file with unexpected string format."""
        string_data = "not_json_object_or_array"
        file_path = self.create_corrections_file(temp_data_dir, "test_string", string_data)

        needs_migration, data, error = migrator.analyze_file(file_path)

        assert not needs_migration
        assert data == string_data
        assert "Unexpected data type: str" in error

    def test_analyze_file_invalid_json(self, migrator, temp_data_dir):
        """Test analyzing file with invalid JSON."""
        corrections_dir = temp_data_dir / "test_invalid"
        corrections_dir.mkdir(parents=True, exist_ok=True)
        file_path = corrections_dir / "corrections.json"

        # Write invalid JSON
        with file_path.open("w") as f:
            f.write("{ invalid json }")

        needs_migration, data, error = migrator.analyze_file(file_path)

        assert not needs_migration
        assert data is None
        assert "Invalid JSON" in error

    def test_create_backup_success(self, migrator, temp_data_dir):
        """Test successful backup creation."""
        original_data = {"field": "original", "value": "data"}
        file_path = self.create_corrections_file(temp_data_dir, "test_backup", original_data)

        success = migrator.create_backup(file_path)

        assert success
        assert migrator.stats.backups_created == 1

        # Check that backup file exists
        backup_files = list(file_path.parent.glob("corrections.json.bak.*"))
        assert len(backup_files) == 1

        # Verify backup content
        with backup_files[0].open() as f:
            backup_data = json.load(f)
        assert backup_data == original_data

    def test_create_backup_failure(self, migrator, temp_data_dir):
        """Test backup creation failure (read-only directory)."""
        file_path = temp_data_dir / "test_backup" / "corrections.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("{}")

        # Make directory read-only (simulate permission error)
        file_path.parent.chmod(0o444)

        try:
            success = migrator.create_backup(file_path)
            assert not success
            assert migrator.stats.backups_created == 0
            assert len(migrator.stats.errors) > 0
        finally:
            # Restore permissions for cleanup
            file_path.parent.chmod(0o755)

    def test_migrate_file_success(self, migrator, temp_data_dir):
        """Test successful file migration from object to array."""
        original_data = {"field": "test", "value": "original"}
        file_path = self.create_corrections_file(temp_data_dir, "test_migrate", original_data)

        success = migrator.migrate_file(file_path, original_data)

        assert success
        assert migrator.stats.files_migrated == 1

        # Verify file was converted to array
        with file_path.open() as f:
            migrated_data = json.load(f)

        assert isinstance(migrated_data, list)
        assert len(migrated_data) == 1
        assert migrated_data[0] == original_data

    def test_migrate_file_failure(self, migrator, temp_data_dir):
        """Test file migration failure (write permission error)."""
        original_data = {"field": "test", "value": "original"}
        file_path = self.create_corrections_file(temp_data_dir, "test_migrate_fail", original_data)

        # Make file read-only
        file_path.chmod(0o444)

        try:
            success = migrator.migrate_file(file_path, original_data)
            assert not success
            assert migrator.stats.files_migrated == 0
            assert migrator.stats.files_with_errors == 1
            assert len(migrator.stats.errors) > 0
        finally:
            # Restore permissions for cleanup
            file_path.chmod(0o644)

    def test_scan_only_mixed_formats(self, migrator, temp_data_dir):
        """Test scan-only mode with mixed file formats."""
        # Create files in different formats
        self.create_corrections_file(temp_data_dir, "already_array", [{"field": "value"}])
        self.create_corrections_file(temp_data_dir, "needs_migration1", {"field": "value1"})
        self.create_corrections_file(temp_data_dir, "needs_migration2", {"field": "value2"})
        self.create_corrections_file(temp_data_dir, "already_array2", [{"field": "value3"}])

        # Write invalid JSON file
        invalid_dir = temp_data_dir / "invalid"
        invalid_dir.mkdir()
        invalid_file = invalid_dir / "corrections.json"
        invalid_file.write_text("{ invalid json }")

        stats = migrator.scan_only()

        assert stats.total_files_scanned == 5
        assert stats.files_already_arrays == 2
        assert stats.files_needing_migration == 2
        assert stats.files_migrated == 0  # Scan only, no migration
        assert stats.files_with_errors == 1
        assert stats.backups_created == 0
        assert len(stats.errors) == 1

    def test_migrate_mixed_formats(self, migrator, temp_data_dir):
        """Test full migration with mixed file formats."""
        # Create files in different formats
        self.create_corrections_file(temp_data_dir, "already_array", [{"field": "value"}])
        self.create_corrections_file(temp_data_dir, "needs_migration1", {"field": "value1"})
        self.create_corrections_file(temp_data_dir, "needs_migration2", {"field": "value2"})

        stats = migrator.migrate(create_backups=True)

        assert stats.total_files_scanned == 3
        assert stats.files_already_arrays == 1
        assert stats.files_needing_migration == 2
        assert stats.files_migrated == 2
        assert stats.backups_created == 2
        assert stats.files_with_errors == 0

        # Verify migrations were successful
        file1 = temp_data_dir / "needs_migration1" / "corrections.json"
        file2 = temp_data_dir / "needs_migration2" / "corrections.json"

        with file1.open() as f:
            data1 = json.load(f)
        with file2.open() as f:
            data2 = json.load(f)

        assert isinstance(data1, list)
        assert isinstance(data2, list)
        assert data1[0]["field"] == "value1"
        assert data2[0]["field"] == "value2"

    def test_migrate_without_backups(self, migrator, temp_data_dir):
        """Test migration without creating backups."""
        self.create_corrections_file(temp_data_dir, "test_no_backup", {"field": "value"})

        stats = migrator.migrate(create_backups=False)

        assert stats.files_migrated == 1
        assert stats.backups_created == 0

        # Verify no backup files exist
        backup_files = list(temp_data_dir.rglob("*.bak.*"))
        assert len(backup_files) == 0

    def test_idempotent_migration(self, migrator, temp_data_dir):
        """Test that migration is idempotent (safe to run multiple times)."""
        # Create a file that needs migration
        original_data = {"field": "test", "value": "original"}
        self.create_corrections_file(temp_data_dir, "test_idempotent", original_data)

        # Run migration first time
        stats1 = migrator.migrate(create_backups=True)
        assert stats1.files_migrated == 1
        assert stats1.backups_created == 1

        # Reset stats for second run
        migrator.stats = CorrectionsMigrationStats()

        # Run migration second time
        stats2 = migrator.migrate(create_backups=True)
        assert stats2.files_migrated == 0  # No files needed migration
        assert stats2.files_already_arrays == 1  # File is already array
        assert stats2.backups_created == 0  # No backups needed

        # Verify file is still correct array format
        file_path = temp_data_dir / "test_idempotent" / "corrections.json"
        with file_path.open() as f:
            final_data = json.load(f)

        assert isinstance(final_data, list)
        assert len(final_data) == 1
        assert final_data[0] == original_data


class TestComplexMigrationScenarios:
    """Test complex, real-world migration scenarios."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary data directory for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)

    def create_realistic_corrections_structure(self, base_dir: Path):
        """Create a realistic corrections directory structure for testing."""
        # Scenario 1: Simple correction object
        self.create_corrections_file(
            base_dir, "simple-correction",
            {
                "field": "test_name",
                "new_value": "Glucose",
                "old_value": "GLU",
                "line_number": 15,
                "timestamp": "2023-01-01T12:00:00Z"
            }
        )

        # Scenario 2: Already migrated (array format)
        self.create_corrections_file(
            base_dir, "already-migrated",
            [
                {
                    "field": "test_name",
                    "new_value": "Cholesterol",
                    "old_value": "CHOL",
                    "line_number": 10
                },
                {
                    "field": "result_value",
                    "new_value": "150",
                    "old_value": "145",
                    "line_number": 10
                }
            ]
        )

        # Scenario 3: Complex correction object with metadata
        self.create_corrections_file(
            base_dir, "complex-correction",
            {
                "field": "result_value",
                "new_value": "72.5",
                "old_value": "72",
                "line_number": 20,
                "timestamp": "2023-01-02T08:30:00Z",
                "operator": "manual_review",
                "confidence": 0.95,
                "metadata": {
                    "source": "lab_technician",
                    "note": "Corrected decimal precision"
                }
            }
        )

        # Scenario 4: Empty object
        self.create_corrections_file(base_dir, "empty-object", {})

        # Scenario 5: Deeply nested structure
        self.create_corrections_file(
            base_dir, "nested-structure",
            {
                "field": "header_value",
                "new_value": "Updated Lab Name",
                "corrections_metadata": {
                    "applied_by": "system",
                    "rules_applied": ["standardize_lab_names", "fix_encoding"],
                    "confidence_scores": [0.85, 0.92]
                }
            }
        )

    def create_corrections_file(self, base_dir: Path, result_id: str, data: any) -> Path:
        """Helper to create a corrections file with given data."""
        corrections_dir = base_dir / result_id
        corrections_dir.mkdir(parents=True, exist_ok=True)
        corrections_file = corrections_dir / "corrections.json"

        with corrections_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return corrections_file

    def test_realistic_migration_scenario(self, temp_data_dir):
        """Test migration with realistic corrections data structure."""
        self.create_realistic_corrections_structure(temp_data_dir)

        migrator = CorrectionsArrayMigrator(str(temp_data_dir))
        stats = migrator.migrate(create_backups=True)

        # Verify expected results
        assert stats.total_files_scanned == 5
        assert stats.files_already_arrays == 1  # already-migrated
        assert stats.files_needing_migration == 4  # All others
        assert stats.files_migrated == 4
        assert stats.backups_created == 4
        assert stats.files_with_errors == 0

        # Verify specific files were migrated correctly
        test_cases = [
            ("simple-correction", "test_name", "Glucose"),
            ("complex-correction", "result_value", "72.5"),
            ("empty-object", None, None),
            ("nested-structure", "header_value", "Updated Lab Name")
        ]

        for result_id, expected_field, expected_value in test_cases:
            file_path = temp_data_dir / result_id / "corrections.json"
            with file_path.open() as f:
                data = json.load(f)

            assert isinstance(data, list)
            assert len(data) == 1

            if expected_field:
                assert data[0]["field"] == expected_field
                assert data[0]["new_value"] == expected_value

        # Verify already-migrated file wasn't changed
        already_migrated_path = temp_data_dir / "already-migrated" / "corrections.json"
        with already_migrated_path.open() as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 2  # Still has 2 items

        # Verify backups were created and contain original data
        backup_files = list(temp_data_dir.rglob("*.bak.*"))
        assert len(backup_files) == 4  # 4 files needed migration

    def test_scan_only_realistic_scenario(self, temp_data_dir):
        """Test scan-only mode with realistic data structure."""
        self.create_realistic_corrections_structure(temp_data_dir)

        migrator = CorrectionsArrayMigrator(str(temp_data_dir))
        stats = migrator.scan_only()

        # Verify scan results without making changes
        assert stats.total_files_scanned == 5
        assert stats.files_already_arrays == 1
        assert stats.files_needing_migration == 4
        assert stats.files_migrated == 0  # No actual migration
        assert stats.backups_created == 0  # No backups in scan mode

        # Verify no files were changed
        for result_id in ["simple-correction", "complex-correction", "empty-object", "nested-structure"]:
            file_path = temp_data_dir / result_id / "corrections.json"
            with file_path.open() as f:
                data = json.load(f)
            # Should still be objects, not arrays
            assert isinstance(data, dict)

        # Already-migrated should still be array
        already_migrated_path = temp_data_dir / "already-migrated" / "corrections.json"
        with already_migrated_path.open() as f:
            data = json.load(f)
        assert isinstance(data, list)