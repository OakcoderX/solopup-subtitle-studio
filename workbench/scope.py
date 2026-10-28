"""Explicit production range; never silently infer that titles should be excluded."""
import math

def seconds(value):
    if isinstance(value,(float,int)):n=float(value)
    else:
        parts=str(value).strip().replace(',','.').split(':')
        if not 1<=len(parts)<=3:raise ValueError('Use seconds or HH:MM:SS')
        n=0
        for i,p in enumerate(parts):
            v=float(p)
            if v<0 or (i>0 and v>=60):raise ValueError('Invalid timecode')
            n=n*60+v
    if not math.isfinite(n) or n<0:raise ValueError('Invalid timecode')
    return n

def validate(value,duration=None):
    value=value or {'mode':'full'}
    mode=value.get('mode','full')
    if mode=='full':return {'mode':'full','start':0.0,'end':duration,'confirmed':True}
    if mode!='custom':raise ValueError('Scope must be full or custom')
    a,b=seconds(value.get('start','')),seconds(value.get('end',''))
    if b<=a or (duration is not None and b>duration+.001):raise ValueError('Scope must be inside the video with end after start')
    return {'mode':'custom','start':a,'end':b,'confirmed':True}
