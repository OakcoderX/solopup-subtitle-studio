"""Stable SDH display groups; retain exact onsets and editable source identities."""
import copy

def groups(rows):
    result=[]
    for c in sorted(rows,key=lambda x:(x['start'],x['end'])):
        if result and c['start']<max(x['end'] for x in result[-1]):result[-1].append(c)
        else:result.append([c])
    return result

def stabilize(rows, shot_changes=None):
    """Coalesce only short trailing differences, never advance an onset.

    No chain extension: presentationOriginalEnd is the immutable tail anchor.
    Complex groups retain timing and remain subject to screen QC.
    """
    out=copy.deepcopy(rows)
    for group in groups(out):
        if len(group)<2 or not any(c.get('kind')=='sound' for c in group):continue
        end=max(c['end'] for c in group)
        lines=sum(len(c['text'].splitlines()) for c in group)
        if lines>2 or end-min(c['start'] for c in group)>7:continue
        if any(end-c.get('presentationOriginalEnd',c['end'])>.5+1e-7 for c in group):continue
        if len({c.get('region','bottom') for c in group})>1:continue
        for c in group:
            if c.get('kind')!='sound' or c['end']==end or c.get('displayTimingLock'):continue
            if shot_changes is None or any(c['end']<t<=end for t in shot_changes):continue
            c['presentationOriginalEnd']=c.get('presentationOriginalEnd',c['end'])
            c['end']=end
            c['checked']=False
            if c.get('speedReview'):
                c['speedReview']['accepted']=False
                c['speedReview']['invalidated']=True
            c['presentationReview']='Shared SDH exit; onset and words unchanged; verify against picture cuts.'
            note='SDH 同屏退场时间调整，待视听复核。'
            if note not in c.get('unresolved',''):c['unresolved']=(c.get('unresolved','')+' '+note).strip()
    return out


def visible_events(rows, frame, rate):
    """Frame-disjoint visible blocks, ordered sound first, with no hidden slots."""
    bounds=sorted({frame(c[k],rate) for c in rows for k in ('start','end')})
    events=[]
    for a,b in zip(bounds,bounds[1:]):
        active=[c for c in rows if frame(c['start'],rate)<=a<frame(c['end'],rate)]
        active.sort(key=lambda c:(0 if c.get('kind')=='sound' else 1,c['start'],c['end'],str(c.get('id',''))))
        if active:events.append((a,b,active))
    return events


def layout_parts(group):
    """Explicit lines shared by preview contract, validation and iTT.

    Compact a cue that fits one line; pack adjacent same-kind cues only when
    their visible text fits 42. Never hide a line or change an event's timing.
    Each part retains its source cue for styles and identity.
    """
    from layout_policy import wrap
    lines=[];previous=None
    ordered=sorted(group,key=lambda c:(0 if c.get('kind')=='sound' else 1,c['start'],c['end'],str(c.get('id',''))))
    for c in ordered:
        segments=wrap(c['text']).split('\n')
        compatible=previous is not None and (previous.get('kind')=='sound')==(c.get('kind')=='sound') and previous.get('region','bottom')==c.get('region','bottom')
        if len(segments)==1 and lines and compatible and sum(len(t) for _,t in lines[-1])+1+len(segments[0])<=42:
            lines[-1].append((c,' '+segments[0]))
        else:
            lines.extend([[(c,t)] for t in segments])
        previous=c
    return lines


def position_changes(rows, frame, rate):
    """Detect a still-visible cue changing line slot; not a platform violation.

    Compare each rendered line separately, using the actual compact layout.
    Bottom regions anchor the last line; top regions anchor the first line.
    Gaps and replacement of a cue are not movement of persistent text.
    """
    from fractions import Fraction
    def slots(group):
        lines=layout_parts(group);out={}
        for index,line in enumerate(lines):
            for cue,text in line:
                key=(str(cue.get('id')),text.strip())
                out[key]=index if cue.get('region','bottom')=='top' else index-len(lines)
        return out
    events=visible_events(rows,frame,rate);issues=[]
    for previous,current in zip(events,events[1:]):
        if previous[1]!=current[0]:continue
        a,b=slots(previous[2]),slots(current[2])
        moved=sorted({key[0] for key in a.keys() & b.keys() if a[key]!=b[key]})
        if moved:issues.append({'time':current[0]/float(Fraction(str(rate))),
            'frame':current[0],'cue_ids':moved,'reason':'Persistent text changes vertical line slot'})
    return issues
