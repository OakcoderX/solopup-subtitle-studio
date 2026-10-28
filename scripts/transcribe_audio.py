#!/usr/bin/env python3
"""Create a word-timed local Whisper draft from an episode audio track."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", type=Path)
    p.add_argument("output", type=Path, help="Output JSON transcript path")
    p.add_argument("--script", type=Path, help="Extract name glossary first")
    p.add_argument("--model", default="small.en", help="For English use small.en; for multilingual use small/medium/large-v3")
    p.add_argument("--language", default="en", help="Whisper language code; use auto to detect")
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--end", type=float, default=None)
    p.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    p.add_argument("--compute-type", default="int8")
    args = p.parse_args()
    if args.script:
        from character_lookup import extract
        extract(args.script, args.output.parent / "character_lookup.md")
    video = args.video.expanduser().resolve()
    if not video.is_file():
        p.error(f"video not found: {video}")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        p.error("FFmpeg is required; install it with your operating system package manager")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        p.error("Install faster-whisper first: python3 -m pip install -r requirements-asr.txt")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    wav = args.output.with_suffix(".16k-mono.wav")
    command = [ffmpeg, "-hide_banner", "-loglevel", "error"]
    if args.start:
        command.extend(["-ss", str(args.start)])
    command.extend(["-i", str(video), "-vn", "-ac", "1", "-ar", "16000"])
    if args.end is not None:
        command.extend(["-t", str(max(0, args.end - args.start))])
    command.extend(["-c:a", "pcm_s16le", "-y", str(wav)])
    run(command)
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    language = None if args.language.lower() == "auto" else args.language
    segments, info = model.transcribe(str(wav), language=language, beam_size=5, word_timestamps=True, vad_filter=True)
    rows = []
    for segment in segments:
        rows.append({
            "start": round(segment.start + args.start, 3),
            "end": round(segment.end + args.start, 3),
            "text": segment.text.strip(),
            "confidence": round(segment.avg_logprob, 4),
            "words": [
                {"start": round(word.start + args.start, 3), "end": round(word.end + args.start, 3), "word": word.word, "probability": round(word.probability, 4)}
                for word in (segment.words or [])
            ],
        })
    result = {"status": "machine_draft_unreviewed", "model": args.model, "language": info.language, "language_probability": info.language_probability, "scope_seconds": [args.start, args.end], "segments": rows}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(rows)} unreviewed segments to {args.output}")
    print(f"Temporary audio retained at {wav}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
