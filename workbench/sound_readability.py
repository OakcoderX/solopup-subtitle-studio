"""Bound sound-label tail extensions; never infer or change the sound identity."""
import copy,math,re

def scene_times(path):
    if not path.exists():return None
    text=path.read_text(errors='replace')
    if 'pts_time:' not in text:return None
    return sorted(set(float(x) for x in re.findall(r'pts_time:([0-9.]+)',text)))

def improve(rows,cuts=None,fps=24):
    out=copy.deepcopy(rows)
    sounds=sorted([c for c in out if c.get('kind')=='sound'],key=lambda c:c['start'])
    for i,c in enumerate(sounds):
        if c.get('displayTimingLock'):continue
        text=c['text'];required=max(20/fps,len(text)/17,len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",text))/2)
        anchor=min(c.get('soundOriginalEnd',c['end']),c.get('presentationOriginalEnd',c['end']));target=c['start']+min(required,7)
        cap=anchor+.5
        if i+1<len(sounds):cap=min(cap,sounds[i+1]['start']-2/fps)
        if cuts is not None:
            after=[t for t in cuts if t>anchor+1e-6]
            if after:cap=min(cap,after[0]-2/fps)
        end=max(c['end'],math.floor(min(target,cap)*fps+1e-7)/fps) if cuts is not None else c['end']
        if end>c['end']+1e-6:
            c['soundOriginalEnd']=anchor;c['end']=end;c['checked']=False
            if c.get('speedReview'):c['speedReview'].update(accepted=False,invalidated=True)
            c['soundTimingReview']='Sound-label tail extended at most 0.5s; verify against audio and picture.'
    return out


def music_onsets(rows, fps=24):
    """Music descriptors establish a bed once, rather than covering every lyric.

    Separate audible-event duration from label exposure. No dialogue or lyrics
    are edited. A cue is shortened only if its label can be read in 3-7 seconds.
    Never extend an acoustic event or repeat the same music label.
    """
    out=copy.deepcopy(rows)
    for c in out:
        if c.get('kind')!='sound' or not re.search(r'\bmusic\b',c['text'],re.I):continue
        required=max(3,len(c['text'])/17,len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",c['text']))/2)
        if required>7 or c['end']-c['start']<=required:continue
        original=c['end'];c['audioStart']=c.get('audioStart',c['start']);c['audioEnd']=c.get('audioEnd',original)
        c['end']=math.ceil((c['start']+required)*fps)/fps;c['displayTimingLock']=True;c['checked']=False
        c['displayPolicy']={'rule':'music_onset_label','audibleEnd':original,'reason':'Readable one-time music descriptor; continuous bed need not remain over dialogue/lyrics.'}
        if c.get('speedReview'):c['speedReview'].update(accepted=False,invalidated=True)
    return out


def sustained_onsets(rows, fps=24):
    """Expose a long sustained sound once, retaining its full acoustic interval.

    As with a continuing music bed, a descriptor need not occupy the whole
    audible event. This does not classify sounds or remove narrative events.
    Reviewed/manual display locks and short events remain untouched.
    """
    out=copy.deepcopy(rows)
    for c in out:
        if c.get('kind')!='sound' or c.get('checked') or c.get('displayTimingLock'):continue
        if c['end']-c['start']<=7:continue
        required=max(3,len(c['text'])/17,len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",c['text']))/2)
        if required>7:continue
        end=math.ceil((c['start']+required)*fps)/fps
        c['audioStart']=c.get('audioStart',c['start']);c['audioEnd']=c.get('audioEnd',c['end'])
        c['end']=end;c['displayTimingLock']=True;c['checked']=False
        c['displayPolicy']={'rule':'sustained_sound_onset_label','audibleEnd':c['audioEnd'],
                            'reason':'One readable description of an ongoing sound; acoustic duration retained separately.'}
        if c.get('speedReview'):c['speedReview'].update(accepted=False,invalidated=True)
    return out


def repair_minimum_frames(rows, cuts=None, fps=24):
    """Repair frame-rounding undershoot only, never erase a meaningful sound.

    At 24 fps 0.8 seconds may export as 19 frames. Extend at most two
    frames, bounded by the original sound tail +0.5s, cuts, and next sound.
    Explicit human locks and lack of shot evidence leave a visible QC issue.
    """
    out=copy.deepcopy(rows)
    if cuts is None:return out
    frame=lambda t:math.floor(float(t)*fps+.5)
    sounds=sorted((c for c in out if c.get('kind')=='sound'),key=lambda c:c['start'])
    for i,c in enumerate(sounds):
        if c.get('checked') or isinstance(c.get('displayTimingLock'),dict):continue
        n=frame(c['end'])-frame(c['start'])
        if not 18<=n<20:continue
        end=(frame(c['start'])+20)/fps
        anchor=c.get('soundAudioEnd',c.get('soundOriginalEnd',c.get('audioEnd',c['end'])))
        if end>anchor+.5+1e-7 or any(c['end']<t<=end for t in cuts):continue
        if i+1<len(sounds) and frame(end)+2>frame(sounds[i+1]['start']):continue
        # Do not create a new overlap with previously non-overlapping dialogue.
        if any(d.get('kind')!='sound' and c['end']<=d['start']<end for d in out):continue
        before=c['end'];c['end']=end;c['checked']=False
        c.setdefault('soundOriginalEnd',anchor)
        c['minimumFrameRepair']={'before':before,'after':end,'frames_before':n,'frames_after':20,
                                 'reason':'Frame-rounded minimum exposure; no lexical or semantic change'}
        if c.get('speedReview'):c['speedReview'].update(accepted=False,invalidated=True)
    return out
