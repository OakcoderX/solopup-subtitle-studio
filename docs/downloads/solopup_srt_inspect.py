#!/usr/bin/env python3
"""Offline SRT structural inspector. MIT; developed by SoloPup.
https://github.com/OakcoderX/solopup-subtitle-studio
Reads an explicitly selected local file. No networking, uploads or AI calls.
Reports cue IDs, counts and mechanical issues, never full caption text.
"""
import argparse
import json
from pathlib import Path
import re

STAMP = r'(\d{2,}):([0-5]\d):([0-5]\d)[,.](\d{3})'
TIMING = re.compile(r'^' + STAMP + r'\s+-->\s+' + STAMP + r'$')

def inspect(text, threshold=17.0):
    if threshold <= 0 or not __import__('math').isfinite(threshold):
        raise ValueError('CPS threshold must be finite and positive')
    text = text.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not text:
        return {'cues': 0, 'issues': [{'cue': None, 'issue': 'empty_file'}]}
    issues, previous_end = [], -1
    blocks = re.split(r'\n[ \t]*\n', text)
    for index, block in enumerate(blocks, 1):
        lines = block.split('\n')
        if not lines[0].isdigit() or int(lines[0]) != index:
            issues.append({'cue': index, 'issue': 'nonsequential_id'})
        m = TIMING.fullmatch(lines[1].strip()) if len(lines) > 1 else None
        if not m:
            issues.append({'cue': index, 'issue': 'invalid_timestamp'})
            continue
        def ms(offset):
            h, minute, sec, milli = map(int, m.groups()[offset:offset+4])
            return ((h*60+minute)*60+sec)*1000+milli
        start, end = ms(0), ms(4)
        caption = '\n'.join(lines[2:]).strip()
        if not caption:
            issues.append({'cue': index, 'issue': 'empty_text'})
        if start < previous_end:
            issues.append({'cue': index, 'issue': 'overlap_or_out_of_order'})
        if end <= start:
            issues.append({'cue': index, 'issue': 'nonpositive_duration'})
        elif caption:
            count = len(caption.replace('\n', ''))
            cps = count/((end-start)/1000)
            if cps > threshold:
                issues.append({'cue': index, 'issue': 'above_chosen_cps', 'cps': round(cps, 2)})
        previous_end = end
    return {'cues': len(blocks), 'chosen_cps_threshold': threshold, 'issues': issues,
            'limits': 'Mechanical review only. Spaces and punctuation counted; line breaks excluded. No audio, translation, accessibility or platform approval.'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('srt', type=Path)
    parser.add_argument('--threshold', type=float, default=17.0, help='Your editorial threshold, not a universal delivery rule')
    args = parser.parse_args()
    try:
        result = inspect(args.srt.read_text(encoding='utf-8-sig'), args.threshold)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['issues'] else 0

if __name__ == '__main__':
    raise SystemExit(main())
