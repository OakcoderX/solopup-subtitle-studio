#!/usr/bin/env python3
"""Configure local Qwen access without putting a key in commands, logs, or ZIPs."""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from provider_config import ROOT, base_url, model, validate_endpoint

def save_configuration(root, key, endpoint, audio_model=None, text_model=None):
    endpoint = validate_endpoint(endpoint)
    if not key.strip() or any(c.isspace() for c in key.strip()):
        raise ValueError("Enter a non-empty API key without whitespace.")
    folder = Path(root) / "config"
    folder.mkdir(parents=True, exist_ok=True)
    secret = folder / "team_api_key"
    # O_NOFOLLOW prevents writing through a pre-existing symlink.
    fd = os.open(str(secret), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w") as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(key.strip() + "\n")
    settings={"base_url":endpoint}
    for name,value in [("audio_model",audio_model),("text_model",text_model)]:
        if value:settings[name]=value.strip()
    (folder / "provider.json").write_text(json.dumps(settings, indent=2) + "\n")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Qwen OpenAI-compatible HTTPS base URL; not a key")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("Run in an interactive terminal. Never put the key in chat or command arguments.")
    endpoint = args.base_url or input("Qwen API base URL [" + base_url() + "]: ").strip() or base_url()
    audio_model=input("Audio/vision model ["+model()+"]: ").strip() or model()
    text_model=input("Text/translation model ["+model('text')+"]: ").strip() or model('text')
    key = getpass.getpass("Qwen API key (hidden, stored only on this computer): ")
    try:
        save_configuration(ROOT, key, endpoint, audio_model, text_model)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print("Local Qwen configuration saved. Key was not printed. Restart the workbench to apply it.")
    print("No API request was made; model access and billing have not been tested.")
if __name__ == "__main__":
    main()
