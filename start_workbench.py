#!/usr/bin/env python3
"""Start the portable episode review workbench for a selected video."""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))



def parse_time(value: str) -> float:
    h, m, rest = value.split(":")
    sec, ms = re.split(r"[,.]", rest)
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms.ljust(3, "0")[:3]) / 1000


def read_srt(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if text.startswith("WEBVTT"):
        text = text.split("\n", 1)[1]
    rows = []
    for block in re.split(r"\n\s*\n", text.strip()):
        match = re.search(r"(\d{2,}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{2,}:\d{2}:\d{2}[,.]\d{1,3})[^\n]*\n([\s\S]*)", block)
        if not match:
            continue
        start, end = parse_time(match.group(1)), parse_time(match.group(2))
        body = re.sub(r"<[^>]+>", "", match.group(3).strip())
        if end > start and body:
            rows.append({"id": f"I{len(rows)+1:03d}", "start": start, "end": end, "text": body, "checked": False})
    return rows


def choose_video() -> Path:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        name = filedialog.askopenfilename(title="Choose final episode video", filetypes=[("Video", "*.mp4 *.mov *.m4v *.mkv"), ("All files", "*.*")])
        root.destroy()
        return Path(name) if name else Path()
    except Exception as exc:
        if sys.platform == "darwin" and shutil.which("osascript"):
            result = subprocess.run(
                ["osascript", "-e", 'POSIX path of (choose file with prompt "Select final episode video")'],
                capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip())
        raise SystemExit(f"Pass --video PATH to select the episode video. File picker unavailable: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, help="Final episode video; omit to choose in a file dialog")
    parser.add_argument("--project", type=Path, help="Work folder; default: Subtitle_Projects/<video-name>")
    parser.add_argument("--title", help="Project title shown in the workbench")
    parser.add_argument("--script", type=Path, help="Screenplay: extract character_lookup.md before any recognition")
    parser.add_argument("--standard-srt", type=Path)
    parser.add_argument("--sdh-srt", type=Path)
    parser.add_argument("--sounds-csv", type=Path, help="Optional candidate CSV; its referenced clips will be copied into the project")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument('--library',type=Path,help='Persistent project library')
    parser.add_argument('--key-zip',type=Path,help='Optional credential bundle')
    parser.add_argument('--fresh',action='store_true',help='Choose a new video instead of resuming the last session')
    args = parser.parse_args()
    session_file=ROOT/'last_session.json'
    if not args.video and not args.project and not args.fresh and session_file.exists():
        previous=json.loads(session_file.read_text())
        if Path(previous.get('video','')).is_file() or (Path(previous.get('project',''))/'workbench_state.json').is_file():
            args.video=Path(previous['video']);args.project=Path(previous['project'])
            args.title=args.title or previous.get('title')
            args.port=args.port or previous.get('port',8877)
            if previous.get('sounds_csv') and Path(previous['sounds_csv']).exists():args.sounds_csv=Path(previous['sounds_csv'])
            args.library=args.library or Path(previous['library'])
            if previous.get('key_zip') and Path(previous['key_zip']).is_file():args.key_zip=args.key_zip or Path(previous['key_zip'])
            print('Resuming the last project library and saved background queue.')
    args.port=args.port or 8877
    video = (args.video or choose_video()).expanduser().resolve()
    if not video.is_file() and not (args.project and (args.project.expanduser()/'workbench_state.json').is_file()):
        parser.error("Select an existing video with --video or a saved --project for offline editing")
    project = (args.project or (ROOT / "Subtitle_Projects" / video.stem)).expanduser().resolve()
    project.mkdir(parents=True, exist_ok=True)
    if args.script:
        sys.path.insert(0, str(ROOT / "scripts"))
        from character_lookup import extract
        extract(args.script, project / "character_lookup.md")
    state_path = project / "workbench_state.json"
    if not state_path.exists():
        state = {"standard": read_srt(args.standard_srt) if args.standard_srt else [], "sdh": read_srt(args.sdh_srt) if args.sdh_srt else [], "subtitleSpec": "prime", "targetLanguage": "en-US"}
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    sounds_csv = None
    if args.sounds_csv:
        source_csv = args.sounds_csv.expanduser().resolve()
        if not source_csv.is_file():
            parser.error(f"Sound CSV not found: {source_csv}")
        clips = project / "clips"
        clips.mkdir(exist_ok=True)
        with source_csv.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            src = source_csv.parent / row.get("clip_file", "")
            if src.is_file():
                dest = clips / src.name
                if src.resolve() != dest.resolve():
                    shutil.copy2(src, dest)
                row["clip_file"] = f"clips/{dest.name}"
        sounds_csv = project / "SDH_Sound_Candidates.csv"
        with sounds_csv.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["start", "end", "caption", "clip_file"])
            writer.writeheader()
            writer.writerows(rows)
    args.library=(args.library or ROOT/'Subtitle_Library').expanduser().resolve()
    command = [sys.executable, str(ROOT / "workbench" / "server.py"), "--video", str(video), "--project", str(project), "--title", args.title or video.stem, "--port", str(args.port)]
    if sounds_csv:
        command += ["--sounds-csv", str(sounds_csv)]
    command+=['--library',str(args.library)]
    if args.key_zip:command+=['--key-zip',str(args.key_zip.resolve())]
    session_file.write_text(json.dumps({'video':str(video),'project':str(project),'title':args.title or video.stem,
        'port':args.port,'sounds_csv':str(sounds_csv or ''),'library':str(args.library),'key_zip':str(args.key_zip.resolve()) if args.key_zip else ''},ensure_ascii=False,indent=2))
    print(f"Review outputs will be saved in: {project}")
    result = subprocess.run(command, check=False, cwd=project)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
