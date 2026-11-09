#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
if [[ -d "$SCRIPT_DIR/.devcontainer" ]]; then PROJECT_ROOT="$SCRIPT_DIR"; else PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"; fi
exec uv --no-config run --no-project --managed-python --python 3.13 --script "$PROJECT_ROOT/setup/sandbox.py" init "$@"
