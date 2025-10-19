#!/bin/bash

# Corrections Array Migration Helper Script
#
# Safe wrapper for running the corrections migration utility
# Provides clear prompts and safety checks

set -e

API_DIR="$(dirname "$0")/../services/api"
MIGRATION_CMD="python3 -m migrations.corrections_array_migration"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  Corrections Array Migration Utility${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo
}

print_usage() {
    echo "Usage: $0 [scan|migrate|help]"
    echo
    echo "Commands:"
    echo "  scan     - Scan and report what files need migration (safe, read-only)"
    echo "  migrate  - Perform the actual migration with backups"
    echo "  help     - Show this help message"
    echo
    echo "Environment Variables:"
    echo "  DATA_ROOT - Base directory containing results (default: /data)"
    echo
    echo "Examples:"
    echo "  $0 scan                    # Check what needs migration"
    echo "  $0 migrate                 # Run the migration"
    echo "  DATA_ROOT=/custom $0 scan  # Use custom directory"
}

check_requirements() {
    if [ ! -d "$API_DIR" ]; then
        echo -e "${RED}ERROR: API directory not found at $API_DIR${NC}"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}ERROR: python3 not found${NC}"
        exit 1
    fi

    cd "$API_DIR"
    if ! python3 -c "from migrations.corrections_array_migration import CorrectionsArrayMigrator" 2>/dev/null; then
        echo -e "${RED}ERROR: Migration module not available${NC}"
        echo "Make sure you're running from the correct directory and dependencies are installed."
        exit 1
    fi
}

run_scan() {
    echo -e "${BLUE}Running scan to check what files need migration...${NC}"
    echo

    cd "$API_DIR"
    if $MIGRATION_CMD --scan-only --verbose; then
        echo
        echo -e "${GREEN}✅ Scan completed successfully${NC}"
        echo -e "${YELLOW}Review the output above to see what would be migrated.${NC}"
    else
        echo
        echo -e "${RED}❌ Scan failed${NC}"
        exit 1
    fi
}

run_migrate() {
    echo -e "${YELLOW}⚠️  WARNING: This will modify corrections files on disk!${NC}"
    echo -e "${YELLOW}   Backups will be created automatically.${NC}"
    echo

    # First run a scan
    echo -e "${BLUE}Running preliminary scan...${NC}"
    cd "$API_DIR"
    if ! $MIGRATION_CMD --scan-only; then
        echo -e "${RED}❌ Preliminary scan failed${NC}"
        exit 1
    fi

    echo
    read -p "Do you want to proceed with the migration? (y/N): " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Migration cancelled.${NC}"
        exit 0
    fi

    echo
    echo -e "${BLUE}Running migration...${NC}"
    echo

    if $MIGRATION_CMD --migrate --verbose; then
        echo
        echo -e "${GREEN}✅ Migration completed successfully${NC}"
        echo -e "${GREEN}   Backup files were created with timestamps.${NC}"
        echo -e "${YELLOW}   Monitor your application to ensure everything works correctly.${NC}"
    else
        echo
        echo -e "${RED}❌ Migration failed${NC}"
        echo -e "${YELLOW}   Check the error messages above and any backup files created.${NC}"
        exit 1
    fi
}

main() {
    print_header

    case "${1:-}" in
        "scan")
            check_requirements
            run_scan
            ;;
        "migrate")
            check_requirements
            run_migrate
            ;;
        "help"|"-h"|"--help")
            print_usage
            ;;
        "")
            echo -e "${YELLOW}No command specified.${NC}"
            echo
            print_usage
            exit 1
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            echo
            print_usage
            exit 1
            ;;
    esac
}

main "$@"