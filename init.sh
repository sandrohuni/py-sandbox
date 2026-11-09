#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Script dependencies are isolated from the project's own environment.
exec uv run --no-project --script scripts/sandbox.py init "$@"
