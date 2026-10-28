#!/usr/bin/env python3
"""Create an unreviewed subtitle translation while preserving cue IDs and times."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import urllib.request
from pathlib import Path
from provider_config import base_url

LANGUAGES = {"en": "English", "ko": "Korean", "ja": "Japanese", "zh": "Simplified Chinese"}
KIT_ROOT = Path(__file__).resolve().parents[1]


def parse_srt(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    rows = []
    for block in re.split(r"\n\s*\n", text.strip()):
        match = re.search(r"(\d{2,}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{2,}:\d{2}:\d{2}[,.]\d{1,3})[^\n]*\n([\s\S]*)", block)
        if match:
            rows.append({"start": match.group(1), "end": match.group(2), "text": match.group(3).strip()})
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--target", choices=LANGUAGES, required=True)
    p.add_argument("--model", default=__import__("provider_config").model("text"))
    p.add_argument("--base-url", default=base_url())
    p.add_argument("--batch-size", type=int, default=18)
    args = p.parse_args()
    cues = parse_srt(args.input)
    if not cues:
        p.error("No SRT cues found")
    bundled_key = KIT_ROOT / "config" / "team_api_key"
    key = os.environ.get("QWEN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY") or (bundled_key.read_text(encoding="utf-8").strip() if bundled_key.is_file() else "") or getpass.getpass("Qwen API key (input hidden): ").strip()
    if not key:
        p.error("Set QWEN_API_KEY or DASHSCOPE_API_KEY, or enter a key when prompted")
    translations = []
    for offset in range(0, len(cues), args.batch_size):
        batch = cues[offset:offset + args.batch_size]
        prompt = (
            f"Translate these subtitle cues into {LANGUAGES[args.target]}. Return only a JSON array of strings, "
            "one translation per input cue, in the same order. Preserve meaning, tone, names, wordplay, and all meaningful "
            "words. Do not merge, split, omit, or add cues. Do not change cue timing. Preserve bracketed SDH sound descriptions "
            "as concise natural sound captions in the target language. Use natural subtitle punctuation and avoid colons unless "
            "the target-language style guide requires them. Do not invent context. Cues:\n" +
            json.dumps([c["text"] for c in batch], ensure_ascii=False)
        )
        payload = {"model": args.model, "messages": [{"role": "user", "content": prompt}], "stream": False}
        url = args.base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"
        req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"]
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(content).strip(), flags=re.I)
        parsed = json.loads(content)
        if not isinstance(parsed, list) or len(parsed) != len(batch) or not all(isinstance(x, str) for x in parsed):
            raise ValueError(f"Translation response for batch {offset // args.batch_size + 1} did not preserve cue count")
        translations.extend(parsed)
        print(f"Translated cues {offset + 1}-{offset + len(batch)}; verify every cue against audio and target-language style guidance")
    out = []
    for i, (cue, text) in enumerate(zip(cues, translations), 1):
        out.extend((str(i), f"{cue['start']} --> {cue['end']}", text, ""))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(out), encoding="utf-8")
    print(f"Saved unreviewed {LANGUAGES[args.target]} draft to {args.output}; timings were copied from the source SRT.")
    print("The API key was used for this process only and was not written to disk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
