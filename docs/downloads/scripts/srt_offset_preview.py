#!/usr/bin/env python3
"""MIT. SoloPup uniform millisecond-offset preview to stdout. Requires public_srt.py. Does not rewrite the input file."""
import argparse,sys
from pathlib import Path
from public_srt import parse,timestamp

def preview(text,offset_ms):
    if not isinstance(offset_ms,int):raise ValueError('Offset must be integer milliseconds')
    cues=parse(text);blocks=[]
    for c in cues:
        start,end=c['start_ms']+offset_ms,c['end_ms']+offset_ms
        if start<0:raise ValueError('Offset would make cue %d negative; no clamping is performed' % c['id'])
        blocks.append('%d\n%s --> %s\n%s' % (c['id'],timestamp(start),timestamp(end),c['text']))
    return '\n\n'.join(blocks)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--offset-ms',type=int,required=True);args=p.parse_args()
    try:result=preview(args.source.read_text(encoding='utf-8-sig'),args.offset_ms)
    except (OSError,UnicodeError,ValueError) as e:p.error(str(e))
    sys.stdout.write(result)
if __name__=='__main__':main()
