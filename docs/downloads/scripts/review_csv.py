#!/usr/bin/env python3
"""MIT. SoloPup SRT-to-review CSV. No edits to source. Requires public_srt.py."""
import argparse,csv,sys
from pathlib import Path
from public_srt import parse

def safe_cell(text):
    # Prefix spreadsheet formula-leading text only in the CSV review copy.
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text

def write_review(text,stream):
    cues=parse(text);w=csv.writer(stream,lineterminator='\r\n')
    w.writerow(['cue_id','start_seconds','end_seconds','source_text','source_review','translation_text','translation_review'])
    for c in cues:w.writerow([c['id'],c['start_ms']/1000,c['end_ms']/1000,safe_cell(c['text']),'pending','','pending'])
    return len(cues)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);args=p.parse_args()
    try:write_review(args.source.read_text(encoding='utf-8-sig'),sys.stdout)
    except (OSError,UnicodeError,ValueError) as e:p.error(str(e))
if __name__=='__main__':main()
