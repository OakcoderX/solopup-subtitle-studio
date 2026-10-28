#!/usr/bin/env python3
"""Generate unreviewed SDH sound candidates and listenable clips with Qwen Omni."""
from __future__ import annotations

import argparse
import base64
import csv
import getpass
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from provider_config import base_url

DEFAULT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
KIT_ROOT = Path(__file__).resolve().parents[1]
PROMPT = """Listen to the original final-mix audio segment and find only possible SDH sound cues. Return valid JSON only: {\"sound_events\":[{\"start\":0.0,\"end\":1.0,\"description\":\"[short audible caption]\",\"confidence\":\"high|medium|low\"}],\"music\":\"brief note or empty\",\"uncertain_items\":[]}. Times are seconds from this clip's start. Include at most 8 clearly audible, potentially meaningful non-speech events, including vocalizations. Do NOT transcribe or paraphrase dialogue; intelligible speech belongs in the transcript. For each event, apply all three tests: audible in the mix; omission would remove narrative, emotional, or comprehension information; and that information is not already clear from dialogue. You receive audio only: whether a sound is redundant with the picture must be decided in the subsequent video review, not invented here. Omit routine foley,  faint incidental noise, and decorative sounds with no distinct audible information. Never infer sound from visuals. Do not identify an unseen physical source unless the audio supports it; when uncertain, use a neutral acoustic description or put it in uncertain_items instead of a confident cue. Use the shortest neutral present-tense wording. Separate non-speech vocalizations from effects. Do not emit a generic continuous music-bed cue; note music only if a meaningful start, stop, conspicuous change, lyric, or story-relevant signal occurs. For English Prime Video drafts, sound descriptions must be in square brackets and lowercase except proper nouns; no italics or ellipses. If significance or source is uncertain, prefer uncertain_items over sound_events. Timestamps must match audible onset and end, not the visible action. This is an unreviewed candidate-finding pass, never a final SDH decision."""


def ffmpeg_cut(ffmpeg: str, video: Path, start: float, duration: float, target: Path, audio_only: bool = False) -> None:
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{duration:.3f}"]
    if audio_only:
        cmd += ["-vn", "-ac", "1", "-ar", "24000", "-c:a", "libmp3lame", "-b:a", "48k"]
    else:
        cmd += ["-vn", "-ac", "1", "-ar", "24000", "-c:a", "libmp3lame", "-b:a", "48k"]
    cmd += ["-y", str(target)]
    subprocess.run(cmd, check=True)


def content_text(response: dict) -> str:
    content = response["choices"][0]["message"]["content"]
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    return str(content)


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    return json.loads(text)


import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sdh_policy import prompt_rules
PROMPT += '\n'+prompt_rules()

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", type=Path)
    p.add_argument("project", type=Path, help="Episode workbench folder; output goes into project/clips")
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--end", type=float, default=None)
    p.add_argument("--chunk-seconds", type=float, default=60)
    p.add_argument("--context", type=float, default=2.5, help="Seconds of context around each candidate clip")
    p.add_argument("--model", default=__import__("provider_config").model())
    p.add_argument("--base-url", default=base_url())
    p.add_argument("--max-events-per-chunk", type=int, default=8)
    args = p.parse_args()
    video = args.video.expanduser().resolve()
    if not video.is_file():
        p.error(f"video not found: {video}")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        p.error("FFmpeg is required")
    bundled_key = KIT_ROOT / "config" / "team_api_key"
    key = os.environ.get("QWEN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY") or (bundled_key.read_text(encoding="utf-8").strip() if bundled_key.is_file() else "") or getpass.getpass("Qwen API key (input hidden): ").strip()
    if not key:
        p.error("Set QWEN_API_KEY or DASHSCOPE_API_KEY, or enter a key when prompted")
    project = args.project.expanduser().resolve()
    chunk_dir = project / "model_audio_chunks"
    clip_dir = project / "clips"
    raw_dir = project / "qwen_sound_events"
    for d in (chunk_dir, clip_dir, raw_dir):
        d.mkdir(parents=True, exist_ok=True)

    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        probe = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(video)], check=True, capture_output=True, text=True)
        duration = float(probe.stdout.strip())
    else:
        duration = args.end if args.end is not None else 0
    end = min(args.end if args.end is not None else duration, duration) if duration else args.end
    if end is None or end <= args.start:
        p.error("Could not determine video duration. Install FFprobe or specify --end.")
    base = args.base_url.rstrip("/")
    if not base.endswith("/chat/completions"):
        base += "/chat/completions"

    events = []
    chunks = []
    t = args.start
    while t < end:
        stop = min(t + args.chunk_seconds, end)
        tag = f"{int(t//60):02d}m{int(t%60):02d}s"
        audio_path = chunk_dir / f"{tag}.mp3"
        ffmpeg_cut(ffmpeg, video, t, stop - t, audio_path, audio_only=True)
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": [
                {"type": "input_audio", "input_audio": {"data": "data:audio/mpeg;base64," + base64.b64encode(audio_path.read_bytes()).decode("ascii"), "format": "mp3"}},
                {"type": "text", "text": PROMPT},
            ]}],
            "modalities": ["text"],
            "stream": False,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(base, data=data, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as res:
                response = json.loads(res.read().decode("utf-8"))
            content = content_text(response)
            try:
                parsed = parse_json(content)
                parse_status = "valid_json"
            except Exception:
                parsed = None
                parse_status = "unparsed_raw_retained"
            (raw_dir / f"{tag}.json").write_text(json.dumps({"status": "unreviewed", "model": args.model, "offset_seconds": t, "response": response, "content": content, "parsed": parsed, "parse_status": parse_status}, ensure_ascii=False, indent=2), encoding="utf-8")
            chunks.append({"start": t, "end": stop, "tag": tag, "parse_status": parse_status})
            if parsed:
                for event in parsed.get("sound_events", [])[:args.max_events_per_chunk]:
                    try:
                        local_start = max(0.0, float(event["start"]))
                        local_end = min(stop - t, float(event["end"]))
                        if local_end <= local_start:
                            continue
                        abs_start, abs_end = t + local_start, t + local_end
                        events.append({"start": abs_start, "end": abs_end, "caption": str(event.get("description", "")).strip(), "confidence": event.get("confidence", ""), "source_chunk": tag})
                    except (TypeError, ValueError, KeyError):
                        continue
            print(f"{tag}: {parse_status}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            (raw_dir / f"{tag}_error.json").write_text(json.dumps({"status": "http_error", "status_code": exc.code, "detail": detail}, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{tag}: HTTP {exc.code}; details saved")
        t = stop

    rows = []
    for i, event in enumerate(events, 1):
        if not event["caption"]:
            continue
        clip_start = max(0.0, event["start"] - args.context)
        clip_end = min(duration, event["end"] + args.context) if duration else event["end"] + args.context
        safe = re.sub(r"[^a-z0-9]+", "_", event["caption"].lower()).strip("_")[:48] or "sound"
        clip_name = f"{i:03d}_{int(event['start']//60):02d}m{int(event['start']%60):02d}s_{safe}.mp3"
        ffmpeg_cut(ffmpeg, video, clip_start, clip_end - clip_start, clip_dir / clip_name, audio_only=True)
        rows.append({
            "start": round(event["start"], 3), "end": round(event["end"], 3), "caption": event["caption"],
            "selection_reason": f"Qwen {args.model}; confidence {event['confidence']}; source {event['source_chunk']}",
            "review_status": "UNREVIEWED", "clip_file": f"clips/{clip_name}",
            "clip_start": round(clip_start, 3), "clip_end": round(clip_end, 3),
            "review_group": "Model suggestion · verify with final audio/video", "review_caption": "", "review_note": "",
        })
    csv_path = project / "SDH_Sound_Candidates.csv"
    fields = ["start", "end", "caption", "selection_reason", "review_status", "clip_file", "clip_start", "clip_end", "review_group", "review_caption", "review_note"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (project / "qwen_sound_run.json").write_text(json.dumps({"status": "candidates_unreviewed", "video": video.name, "model": args.model, "chunks": chunks, "candidate_count": len(rows), "note": "Candidates are not final SDH. A human must compare each cue with final audio and picture."}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(rows)} unreviewed sound candidates to {csv_path}")
    print("The API key was used for this process only and was not written to disk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
