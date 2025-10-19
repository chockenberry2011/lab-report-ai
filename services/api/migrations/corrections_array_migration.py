"""
Corrections Array Migration Utility

Safely migrates corrections.json files from object format to array format.
This is an idempotent operation that:
1. Scans the corrections storage directory
2. Identifies corrections.json files that are JSON objects (not arrays)
3. Wraps them in single-element arrays
4. Creates .bak backups before modification
5. Logs all operations for audit trail

Usage:
    python -m migrations.corrections_array_migration --scan-only
    python -m migrations.corrections_array_migration --migrate
    python -m migrations.corrections_array_migration --directory /custom/path
"""

import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import argparse


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("corrections_migration")


class CorrectionsMigrationStats:
    """Track migration statistics."""

    def __init__(self):
        self.total_files_scanned = 0
        self.files_needing_migration = 0
        self.files_migrated = 0
        self.files_already_arrays = 0
        self.files_with_errors = 0
        self.backups_created = 0
        self.errors: List[str] = []

    def log_summary(self):
        """Log a summary of migration results."""
        logger.info("=== Migration Summary ===")
        logger.info(f"Total files scanned: {self.total_files_scanned}")
        logger.info(f"Files already in array format: {self.files_already_arrays}")
        logger.info(f"Files needing migration: {self.files_needing_migration}")
        logger.info(f"Files successfully migrated: {self.files_migrated}")
        logger.info(f"Backups created: {self.backups_created}")
        logger.info(f"Files with errors: {self.files_with_errors}")

        if self.errors:
            logger.error("Errors encountered:")
            for error in self.errors:
                logger.error(f"  - {error}")


class CorrectionsArrayMigrator:
    """Handles migration of corrections files from object to array format."""

    def __init__(self, base_directory: Optional[str] = None):
        """
        Initialize the migrator.

        Args:
            base_directory: Base directory to scan. Defaults to /data/results
        """
        if base_directory:
            self.base_dir = Path(base_directory)
        else:
            # Try to use environment variable, fall back to default
            data_root = os.environ.get("DATA_ROOT", "/data")
            self.base_dir = Path(data_root) / "results"

        self.stats = CorrectionsMigrationStats()
        logger.info(f"Initialized migrator with base directory: {self.base_dir}")

    def find_corrections_files(self) -> List[Path]:
        """
        Find all corrections.json files in the base directory.

        Returns:
            List of Path objects pointing to corrections.json files
        """
        corrections_files = []

        if not self.base_dir.exists():
            logger.warning(f"Base directory does not exist: {self.base_dir}")
            return corrections_files

        try:
            # Look for corrections.json files in subdirectories
            for corrections_file in self.base_dir.rglob("corrections.json"):
                if corrections_file.is_file():
                    corrections_files.append(corrections_file)

        except Exception as e:
            error_msg = f"Error scanning directory {self.base_dir}: {str(e)}"
            logger.error(error_msg)
            self.stats.errors.append(error_msg)

        logger.info(f"Found {len(corrections_files)} corrections.json files")
        return corrections_files

    def analyze_file(self, file_path: Path) -> Tuple[bool, Any, str]:
        """
        Analyze a corrections file to determine if it needs migration.

        Args:
            file_path: Path to the corrections.json file

        Returns:
            Tuple of (needs_migration, data, error_message)
        """
        try:
            with file_path.open('r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, list):
                # Already an array
                return False, data, ""
            elif isinstance(data, dict):
                # Object that needs migration
                return True, data, ""
            else:
                # Other types (string, number, etc.)
                error_msg = f"Unexpected data type: {type(data).__name__}"
                return False, data, error_msg

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON: {str(e)}"
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Error reading file: {str(e)}"
            return False, None, error_msg

    def create_backup(self, file_path: Path) -> bool:
        """
        Create a backup of the original file.

        Args:
            file_path: Path to the file to backup

        Returns:
            True if backup was created successfully, False otherwise
        """
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = file_path.with_suffix(f".bak.{timestamp}")

            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            self.stats.backups_created += 1
            return True

        except Exception as e:
            error_msg = f"Failed to create backup for {file_path}: {str(e)}"
            logger.error(error_msg)
            self.stats.errors.append(error_msg)
            return False

    def migrate_file(self, file_path: Path, data: Dict[str, Any]) -> bool:
        """
        Migrate a single file from object to array format.

        Args:
            file_path: Path to the corrections.json file
            data: The object data to wrap in an array

        Returns:
            True if migration was successful, False otherwise
        """
        try:
            # Wrap the object in an array
            array_data = [data]

            # Write the migrated data back to the file
            with file_path.open('w', encoding='utf-8') as f:
                json.dump(array_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Migrated file: {file_path}")
            self.stats.files_migrated += 1
            return True

        except Exception as e:
            error_msg = f"Failed to migrate {file_path}: {str(e)}"
            logger.error(error_msg)
            self.stats.errors.append(error_msg)
            self.stats.files_with_errors += 1
            return False

    def scan_only(self) -> CorrectionsMigrationStats:
        """
        Scan corrections files and report what would be migrated without making changes.

        Returns:
            Migration statistics
        """
        logger.info("Starting scan-only mode...")

        corrections_files = self.find_corrections_files()

        for file_path in corrections_files:
            self.stats.total_files_scanned += 1

            needs_migration, data, error = self.analyze_file(file_path)

            if error:
                error_msg = f"Error analyzing {file_path}: {error}"
                logger.error(error_msg)
                self.stats.errors.append(error_msg)
                self.stats.files_with_errors += 1
            elif needs_migration:
                logger.info(f"Would migrate: {file_path} (object -> array)")
                self.stats.files_needing_migration += 1
            else:
                logger.debug(f"Already array format: {file_path}")
                self.stats.files_already_arrays += 1

        self.stats.log_summary()
        return self.stats

    def migrate(self, create_backups: bool = True) -> CorrectionsMigrationStats:
        """
        Perform the actual migration of corrections files.

        Args:
            create_backups: Whether to create backup files before migration

        Returns:
            Migration statistics
        """
        logger.info("Starting migration...")

        corrections_files = self.find_corrections_files()

        for file_path in corrections_files:
            self.stats.total_files_scanned += 1

            needs_migration, data, error = self.analyze_file(file_path)

            if error:
                error_msg = f"Error analyzing {file_path}: {error}"
                logger.error(error_msg)
                self.stats.errors.append(error_msg)
                self.stats.files_with_errors += 1
                continue

            if not needs_migration:
                logger.debug(f"Already array format: {file_path}")
                self.stats.files_already_arrays += 1
                continue

            self.stats.files_needing_migration += 1

            # Create backup if requested
            if create_backups:
                if not self.create_backup(file_path):
                    # Skip migration if backup failed
                    continue

            # Perform migration
            self.migrate_file(file_path, data)

        self.stats.log_summary()
        return self.stats


def main():
    """Main entry point for the migration utility."""
    parser = argparse.ArgumentParser(
        description="Migrate corrections.json files from object to array format"
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Scan and report what would be migrated without making changes"
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Perform the actual migration"
    )
    parser.add_argument(
        "--directory",
        type=str,
        help="Custom base directory to scan (default: $DATA_ROOT/results or /data/results)"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup files (not recommended)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger("corrections_migration").setLevel(logging.DEBUG)

    if not (args.scan_only or args.migrate):
        parser.error("Must specify either --scan-only or --migrate")

    if args.scan_only and args.migrate:
        parser.error("Cannot specify both --scan-only and --migrate")

    # Initialize migrator
    migrator = CorrectionsArrayMigrator(args.directory)

    try:
        if args.scan_only:
            stats = migrator.scan_only()

            if stats.files_needing_migration > 0:
                print(f"\n⚠️  Found {stats.files_needing_migration} files that need migration.")
                print("Run with --migrate to perform the migration.")
                sys.exit(1)  # Exit with error code to indicate action needed
            else:
                print("\n✅ All corrections files are already in array format.")
                sys.exit(0)

        elif args.migrate:
            create_backups = not args.no_backup
            stats = migrator.migrate(create_backups)

            if stats.files_with_errors > 0:
                print(f"\n❌ Migration completed with {stats.files_with_errors} errors.")
                sys.exit(1)
            else:
                print(f"\n✅ Migration completed successfully. Migrated {stats.files_migrated} files.")
                sys.exit(0)

    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()