#!/usr/bin/env python3
"""Verify a distributed kit's manifest without network access or credentials."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def verify(root=ROOT):
    manifest=json.loads((root/'PORTABLE_MANIFEST.json').read_text())
    failed=[]
    for name,expected in manifest['files'].items():
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts: raise ValueError('Unsafe manifest path')
        path=root/rel
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            failed.append(name)
    return failed
if __name__=='__main__':
    failed=verify()
    print(json.dumps({'integrity_ok':not failed,'mismatched_files':failed}))
    raise SystemExit(1 if failed else 0)
