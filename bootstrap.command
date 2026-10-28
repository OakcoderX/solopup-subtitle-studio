#!/bin/zsh
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if ! command -v python3 >/dev/null 2>&1; then
  print "Install Python 3.9+ (3.11+ recommended), then run this again."
  read -k 1 "?Press any key to close..."
  exit 1
fi
python3 bootstrap.py --install
print "Next: configure_qwen.command (for AI production), then start_workbench.command."
read -k 1 "?Press any key to close..."
