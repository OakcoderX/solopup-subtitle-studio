#!/usr/bin/env python3
"""MIT. SoloPup paired-SRT structure comparison. Requires public_srt.py beside this file."""
import argparse,json
from pathlib import Path
from public_srt import parse

def compare(source,target):
    a,b=parse(source),parse(target)
    mismatches=[i+1 for i,(x,y) in enumerate(zip(a,b)) if (x['start_ms'],x['end_ms'])!=(y['start_ms'],y['end_ms'])]
    return {'source_cues':len(a),'target_cues':len(b),'timing_mismatches':mismatches,'aligned':len(a)==len(b) and not mismatches,'audio_and_translation_checked':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('translation',type=Path);args=p.parse_args()
    try:r=compare(args.source.read_text(encoding='utf-8-sig'),args.translation.read_text(encoding='utf-8-sig'))
    except (OSError,UnicodeError,ValueError) as e:p.error(str(e))
    print(json.dumps(r,ensure_ascii=False,indent=2));return 0 if r['aligned'] else 1
if __name__=='__main__':raise SystemExit(main())
