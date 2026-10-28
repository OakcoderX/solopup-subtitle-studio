"""Evidence-bounded second pass after SDH composition, with monotone screen QC."""
import copy, math, re
from presentation import visible_events, layout_parts, position_changes
from layout_policy import invalidate
from evidence_gate import evidence_flags, signature


def metrics(rows, fps):
    frame=lambda t,rate:math.floor(t*fps+.5)
    events=visible_events(rows,frame,fps)
    return (sum((b-a) for a,b,g in events if len(layout_parts(g))>2),
            sum(b-a<20 for a,b,g in events),len(position_changes(rows,frame,fps)))


def repair(rows,cuts=None,fps=24):
    """Optimize machine-owned sound exposure, never dialogue or manual locks.

    No new over-line frames, flash events or vertical jumps are allowed. Keep
    original sound anchors immutable, <=3-frame onset delay, <=0.5s tail,
    min 20 frames and both project reading-speed limits; don't cross cuts.
    A continuing sound may have one readable onset label, not repeated labels.
    """
    out=copy.deepcopy(rows);changes=[]
    if cuts is None:return out,changes
    frame=lambda t:math.floor(t*fps+.5)
    for _ in range(2):
        progress=False
        for c in out:
            if c.get('kind')!='sound' or c.get('checked'):continue
            lock=c.get('displayTimingLock')
            if lock and not (lock is True and (c.get('displaySynchronization') or c.get('displayPolicy'))):continue
            original_start=c.get('soundAudioStart',c.get('audioStart',c['start']))
            original_end=c.get('soundAudioEnd',c.get('soundOriginalEnd',c.get('audioEnd',c['end'])))
            required=max(20,math.ceil(len(c['text'])*fps/17),math.ceil(len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",c['text']))*fps/2))
            starts={frame(c['start'])};ends={frame(c['end'])}
            # A continuing acoustic event does not require a label for its
            # entire duration. Include the shortest readable exposure instead
            # of considering only boundaries close to the old display tail.
            # The sound remains labelled once; no lexical/content deletion.
            ends.add(frame(c['start'])+required)
            for d in out:
                if d is c:continue
                for t in (d['start'],d['end']):
                    f=frame(t)
                    if frame(original_start)<=f<=frame(original_start)+3:starts.add(f)
                    if abs(t-c['end'])<=.5 or (c['start']<t<c['end'] and t<=original_end):ends.update((f,f-2))
            # Only boundaries inside this local window can change; avoid a full-film
            # O(N squared) scan for every candidate. Full-film QC still runs on publication.
            local=[d for d in out if d['start']<c['end']+.6 and d['end']>c['start']-.6]
            best=metrics(local,fps);chosen=None;old=(c['start'],c['end'])
            for a in starts:
                for b in ends:
                    start,end=a/fps,b/fps
                    if b-a<required or b-a>7*fps or end>original_end+.5+1e-7:continue
                    if start<original_start-1/fps or start>original_start+3/fps+1e-7:continue
                    if any(min(old[0],start)<t<=max(old[0],start) or min(old[1],end)<t<=max(old[1],end) for t in cuts):continue
                    c['start'],c['end']=start,end;value=metrics(local,fps);c['start'],c['end']=old
                    if all(x<=y for x,y in zip(value,best)) and value!=best:best=value;chosen=(start,end)
            if chosen:
                valid_semantics=(c.get('semanticReview',{}).get('status')=='machine_reviewed'
                                 and not evidence_flags(c))
                c['soundAudioStart']=original_start;c['soundAudioEnd']=original_end
                c['start'],c['end']=chosen;invalidate(c);c['displayTimingLock']=True
                event={'id':c['id'],'before':list(old),'after':list(chosen),'reason':'Machine-owned sound exposure; immutable audio bounds; no new overlines, flashes or jumps'}
                c.setdefault('displayRepairs',[]).append(event);c.setdefault('displaySynchronization',event)
                # This operation proves display timing against immutable sound
                # anchors. Reuse valid acoustic evidence only if all its other
                # checks still pass; never manufacture a human approval.
                if valid_semantics:
                    probe=copy.deepcopy(c);probe.pop('reviewInvalidated',None)
                    probe['reviewBinding']=signature(probe)
                    if not evidence_flags(probe):
                        c.pop('reviewInvalidated',None);c['reviewBinding']=signature(c)
                        c['displayEvidenceCheck']=copy.deepcopy(event)
                changes.append(event);progress=True
        if not progress:break
    return out,changes
