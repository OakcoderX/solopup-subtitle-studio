#!/usr/bin/env python3
"""Prepare an isolated Python runtime, without making AI requests."""
import argparse
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--install", action="store_true", help="Create .venv and install basic dependencies")
    a = p.parse_args()
    if sys.version_info < (3, 9):
        p.error("Python 3.9+ required; Python 3.11+ recommended")
    python = sys.executable
    if a.install:
        env = ROOT / ".venv"
        python = str(env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"))
        if not Path(python).exists():
            subprocess.run([sys.executable, "-m", "venv", str(env)], check=True)
        subprocess.run([python, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
    result = subprocess.run([python, str(ROOT / "scripts/doctor.py")])
    if result.returncode:
        print("If FFmpeg is missing: macOS: brew install ffmpeg; Ubuntu/Debian: sudo apt install ffmpeg.")
        print("Install tools using your machine's package manager, then run this check again.")
    print("AI production requires your own Qwen API key. Read docs/QWEN_SETUP.md: check eligible trial quota, test a short clip, then prepare provider billing and budget for batch work. Offline imported-subtitle review needs no key.")
    return result.returncode
if __name__ == "__main__":
    raise SystemExit(main())
