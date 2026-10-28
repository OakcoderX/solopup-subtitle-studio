"""MIT. SoloPup strict SRT helpers. No network, AI calls, storage or implicit file access."""
import re
STAMP = r'(\d{2,}):([0-5]\d):([0-5]\d)[,.](\d{3})'
TIMING = re.compile(r'^'+STAMP+r'\s+-->\s+'+STAMP+r'$')

def parse(text):
    text = str(text).lstrip('\ufeff').replace('\r\n','\n').replace('\r','\n').strip('\n')
    if not text.strip():
        raise ValueError('Empty SRT')
    cues, previous = [], -1
    for i, block in enumerate(re.split(r'\n[ \t]*\n',text),1):
        lines=block.split('\n')
        if not lines[0].strip().isdigit() or int(lines[0].strip()) != i:
            raise ValueError('Cue %d: sequential IDs beginning at 1 required' % i)
        m=TIMING.fullmatch(lines[1].strip()) if len(lines)>1 else None
        if not m: raise ValueError('Cue %d: invalid or unsupported timestamp' % i)
        def ms(n):
            h,minute,sec,milli=map(int,m.groups()[n:n+4]);return ((h*60+minute)*60+sec)*1000+milli
        start,end=ms(0),ms(4);caption='\n'.join(lines[2:])
        if not caption.strip():raise ValueError('Cue %d: empty text' % i)
        if end<=start:raise ValueError('Cue %d: nonpositive duration' % i)
        if start<previous:raise ValueError('Cue %d: overlapping or out-of-order timing' % i)
        cues.append({'id':i,'start_ms':start,'end_ms':end,'text':caption});previous=end
    return cues

def timestamp(ms):
    if not isinstance(ms,int) or ms<0:raise ValueError('Timestamp must be a nonnegative integer number of milliseconds')
    sec,milli=divmod(ms,1000);minute,sec=divmod(sec,60);hour,minute=divmod(minute,60)
    return '%02d:%02d:%02d,%03d' % (hour,minute,sec,milli)
