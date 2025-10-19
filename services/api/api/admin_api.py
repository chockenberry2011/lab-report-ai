"""
Admin API for maintenance and migration operations.

Provides endpoints for:
- Running corrections array migration
- System diagnostics
- Data maintenance operations
"""

import logging
import os
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from migrations.corrections_array_migration import (
    CorrectionsArrayMigrator,
    CorrectionsMigrationStats
)

logger = logging.getLogger("api.admin")
router = APIRouter()


class MigrationStatusResponse(BaseModel):
    """Response model for migration status."""
    total_files_scanned: int = Field(..., description="Total corrections files found")
    files_already_arrays: int = Field(..., description="Files already in array format")
    files_needing_migration: int = Field(..., description="Files that need migration")
    files_migrated: int = Field(0, description="Files successfully migrated")
    files_with_errors: int = Field(0, description="Files that had errors")
    backups_created: int = Field(0, description="Number of backup files created")
    errors: list = Field(default_factory=list, description="List of error messages")
    migration_needed: bool = Field(..., description="Whether migration is needed")


class MigrationRequest(BaseModel):
    """Request model for migration operations."""
    create_backups: bool = Field(True, description="Whether to create backup files")
    custom_directory: Optional[str] = Field(None, description="Custom directory to scan")


def _stats_to_response(stats: CorrectionsMigrationStats, migration_performed: bool = False) -> MigrationStatusResponse:
    """Convert migration stats to API response model."""
    return MigrationStatusResponse(
        total_files_scanned=stats.total_files_scanned,
        files_already_arrays=stats.files_already_arrays,
        files_needing_migration=stats.files_needing_migration,
        files_migrated=stats.files_migrated if migration_performed else 0,
        files_with_errors=stats.files_with_errors,
        backups_created=stats.backups_created,
        errors=stats.errors,
        migration_needed=stats.files_needing_migration > 0
    )


@router.get(
    "/admin/corrections-migration/status",
    response_model=MigrationStatusResponse,
    tags=["admin"],
    summary="Check corrections migration status"
)
async def get_migration_status(
    directory: Optional[str] = Query(None, description="Custom directory to scan")
):
    """
    Scan corrections files and report migration status without making changes.

    Returns information about:
    - How many corrections files exist
    - How many are already in array format
    - How many need migration
    - Any errors encountered during scanning

    This is a safe, read-only operation.
    """
    try:
        migrator = CorrectionsArrayMigrator(directory)
        stats = migrator.scan_only()

        logger.info(
            "Migration status check completed",
            extra={
                "total_files": stats.total_files_scanned,
                "need_migration": stats.files_needing_migration,
                "errors": len(stats.errors)
            }
        )

        return _stats_to_response(stats, migration_performed=False)

    except Exception as e:
        logger.error(f"Error checking migration status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check migration status: {str(e)}"
        )


@router.post(
    "/admin/corrections-migration/migrate",
    response_model=MigrationStatusResponse,
    tags=["admin"],
    summary="Run corrections array migration"
)
async def run_migration(request: MigrationRequest):
    """
    Run the corrections array migration.

    This operation will:
    1. Scan all corrections.json files
    2. Create backups of files that need migration (unless disabled)
    3. Convert object-format files to array format by wrapping in [object]
    4. Log all operations for audit trail

    This is an idempotent operation - running it multiple times is safe.

    ⚠️ **Warning**: This modifies files on disk. Backups are created by default.
    """
    try:
        migrator = CorrectionsArrayMigrator(request.custom_directory)
        stats = migrator.migrate(create_backups=request.create_backups)

        logger.info(
            "Migration completed",
            extra={
                "files_migrated": stats.files_migrated,
                "backups_created": stats.backups_created,
                "errors": len(stats.errors),
                "created_backups": request.create_backups
            }
        )

        # Return error if there were migration failures
        if stats.files_with_errors > 0:
            raise HTTPException(
                status_code=500,
                detail=f"Migration completed with {stats.files_with_errors} errors"
            )

        return _stats_to_response(stats, migration_performed=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running migration: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Migration failed: {str(e)}"
        )


@router.get("/admin/system/info", tags=["admin"], summary="Get system information")
async def get_system_info():
    """Get basic system information for diagnostics."""
    try:
        data_root = os.environ.get("DATA_ROOT", "/data")
        results_dir = Path(data_root) / "results"

        # Count corrections files
        corrections_count = 0
        if results_dir.exists():
            corrections_count = len(list(results_dir.rglob("corrections.json")))

        return {
            "data_root": data_root,
            "results_directory": str(results_dir),
            "results_directory_exists": results_dir.exists(),
            "corrections_files_count": corrections_count,
            "environment": {
                "DATA_ROOT": os.environ.get("DATA_ROOT"),
                "RESULTS_DIR": os.environ.get("RESULTS_DIR"),
            }
        }

    except Exception as e:
        logger.error(f"Error getting system info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system info: {str(e)}"
        )