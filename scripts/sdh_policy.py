"""Generic editorial policy; title-specific knowledge is supplied per project."""
from pathlib import Path
POLICY_ID='public_sdh_evidence_v1'
def prompt_rules():
    return (Path(__file__).resolve().parents[1]/'references/SDH_EDITORIAL_RULES.md').read_text()
