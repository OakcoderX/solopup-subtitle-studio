#!/usr/bin/env python3
"""MIT. SoloPup cue-by-position SRT revision summary. Requires public_srt.py. No caption text is printed."""
import argparse,json
from pathlib import Path
from public_srt import parse

def summarize(before,after):
    a,b=parse(before),parse(after);text=[];timing=[]
    for i,(old,new) in enumerate(zip(a,b),1):
        if old['text']!=new['text']:text.append(i)
        if (old['start_ms'],old['end_ms'])!=(new['start_ms'],new['end_ms']):timing.append(i)
    return {'before_cues':len(a),'after_cues':len(b),'text_changed_at_positions':text,'timing_changed_at_positions':timing,'extra_after_positions':list(range(len(a)+1,len(b)+1)),'missing_after_positions':list(range(len(b)+1,len(a)+1)),'method':'Compare corresponding numeric positions only; not semantic matching. Text changes may shift later positions.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('before',type=Path);p.add_argument('after',type=Path);args=p.parse_args()
    try:r=summarize(args.before.read_text(encoding='utf-8-sig'),args.after.read_text(encoding='utf-8-sig'))
    except (OSError,UnicodeError,ValueError) as e:p.error(str(e))
    print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
