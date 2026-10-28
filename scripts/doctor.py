#!/usr/bin/env python3
"""Offline readiness check. Reports credential presence, never credential contents."""
import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def inspect(root=ROOT):
    required = ["start_workbench.py", "workbench/server.py", "workbench/index.html",
                "skill/SKILL.md", "scripts/provider_config.py"]
    missing = [p for p in required if not (root / p).is_file()]
    tools = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}
    numpy = importlib.util.find_spec("numpy") is not None
    python_ok = sys.version_info >= (3, 9)
    credential = bool(os.environ.get("QWEN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY") or
                      ((root / "config/team_api_key").is_file() and (root / "config/team_api_key").stat().st_size))
    return {"ready": python_ok and all(tools.values()) and numpy and not missing,
            "python": sys.version.split()[0], "python_supported": python_ok,
            "tools": tools, "numpy_available": numpy, "missing_files": missing,
            "qwen_key_present": credential,
            "qwen_network_tested": False,
            "notes": ["Qwen key is optional for local review; production requires provider access.",
                      "Local ASR is optional: requirements-asr.txt. Node.js is only needed for JS tests."]}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(); result = inspect()
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        print("Ready" if result["ready"] else "Setup needed")
        print("Python:", result["python"], "| NumPy:", "ready" if result["numpy_available"] else "missing")
        for name, path in result["tools"].items(): print(name + ":", path or "missing (install FFmpeg)")
        print("Qwen:", "configured locally (not network-tested)" if result["qwen_key_present"] else "not configured; run configure_qwen.command when production is needed")
        for name in result["missing_files"]: print("Missing kit file:", name)
    return 0 if result["ready"] else 1
if __name__ == "__main__":
    raise SystemExit(main())
