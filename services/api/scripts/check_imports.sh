#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."  # into services/api

echo "Running import path audit..."

# 1) Grep guard: disallow 'from api.api.' anywhere inside package
if grep -R "from\s\+api\.api\." -n api | grep -v "__pycache__"; then
  echo "Disallowed import path 'api.api' detected"
  exit 1
fi

# 2) Python audit: encourage relative imports inside the package
python3 - <<'PY'
import os, re, sys
root = os.path.join(os.getcwd(), 'api')
bad = []
for r, _, files in os.walk(root):
    for f in files:
        if not f.endswith('.py'):
            continue
        p = os.path.join(r, f)
        with open(p, 'r', encoding='utf-8') as fh:
            s = fh.read()
        if re.search(r"\bfrom\s+api\.api\.", s):
            bad.append(os.path.relpath(p))
if bad:
    sys.exit("Invalid imports:\n" + "\n".join(bad))
print("import audit ok")
PY

echo "OK: imports look good."

