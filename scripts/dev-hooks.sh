#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/dev-hooks.sh <command>

Commands:
  install    Install git pre-commit and pre-push hooks
  run        Run pre-commit hooks for all files
  run-push   Run pre-push hooks for all files
EOF
}

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

case "$1" in
  install)
    pre-commit install
    pre-commit install --hook-type pre-push
    ;;
  run)
    pre-commit run --all-files
    ;;
  run-push)
    pre-commit run --all-files --hook-stage pre-push
    ;;
  *)
    usage
    exit 1
    ;;
esac
