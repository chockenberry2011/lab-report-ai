#!/usr/bin/env bash
set -euo pipefail
pushd "$(dirname "$0")/.." >/dev/null
# Will fail if package.json and lock are out of sync
npm ci --dry-run >/dev/null
echo "Lockfile OK"
popd >/dev/null

