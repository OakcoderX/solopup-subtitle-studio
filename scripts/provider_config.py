"""Read non-secret local provider settings; environment always takes precedence."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"

def validate_endpoint(value):
    endpoint=str(value).strip().rstrip('/')
    parsed=urlsplit(endpoint)
    if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or any(c.isspace() or ord(c)<32 for c in endpoint)
            or '\\' in endpoint):
        raise ValueError('Use an HTTPS API base URL without credentials, query or fragment.')
    parsed.port  # Reject malformed/out-of-range ports before a credential is used.
    return endpoint

def base_url():
    explicit = os.environ.get("QWEN_BASE_URL")
    if explicit:
        return validate_endpoint(explicit)
    path = ROOT / "config/provider.json"
    if path.exists():
        return validate_endpoint(json.loads(path.read_text())["base_url"])
    return DEFAULT_BASE

def load_environment():
    os.environ.setdefault("QWEN_BASE_URL", base_url())


def model(kind='audio'):
    key='text_model' if kind=='text' else 'audio_model'
    env='QWEN_TEXT_MODEL' if kind=='text' else 'QWEN_AUDIO_MODEL'
    if os.environ.get(env): return os.environ[env]
    path=ROOT/'config/provider.json'
    settings=json.loads(path.read_text()) if path.exists() else {}
    return settings.get(key,'qwen3.8-omni-flash')
