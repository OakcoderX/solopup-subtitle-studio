#!/bin/zsh
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then PY="$(command -v python3)"; fi
if [ -z "$PY" ]; then
  print "Python 3 was not found. Run bootstrap.command first."
  read -k 1 "?Press any key to close this window..."
  exit 1
fi
print "Starting the local SDH review workbench..."
print "Keep this Terminal window open while using the workbench."
print "To stop it, press Ctrl+C. To use it again later, double-click this launcher and refresh the browser page."
print ""
"$PY" start_workbench.py
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  print ""
  print "The workbench stopped with an error. If port 8877 is already in use, refresh http://127.0.0.1:8877 first."
  print "If that page does not respond, start it on another port from this folder: python3 start_workbench.py --port 8878"
  read -k 1 "?Press any key to close this window..."
fi
exit "$STATUS"
