"""Repair tiny inter-cue gaps only inside independently measured sync tolerance."""
import copy,math
from fractions import Fraction
from layout_policy import invalidate

def repair_gaps(rows,rate=24,cuts=None):
    """Do not move starts early, cross cuts, alter words or silently approve timing.

    Ends may move at most 3 frames before measured speech end; starts at most
    3 frames after measured speech onset. Missing anchors or genuine overlapping
    dialogue stay unresolved. No repeated drift: caps use immutable audio times.
    """
    out=sorted(copy.deepcopy(rows),key=lambda c:(c['start'],c['end']));events=[]
    fps=float(Fraction(str(rate)));frame=lambda t:math.floor(t*fps+.5)
    dialogue=[c for c in out if c.get('kind')!='sound']
    for a,b in zip(dialogue,dialogue[1:]):
        if a.get('kind')=='sound' or b.get('kind')=='sound' or a.get('checked') or b.get('checked'):continue
        ae,bs=frame(a['end']),frame(b['start']);need=2-(bs-ae)
        if need<=0:continue
        if any(c.get('timingReview')!='machine_word_matched' or not c.get('timingEvidence') for c in (a,b)):continue
        if not isinstance(a.get('audioEnd'),(float,int)) or not isinstance(b.get('audioStart'),(float,int)):continue
        # A large conflict is not rounding noise; preserve it for audiovisual review.
        if frame(a['audioEnd'])-frame(b['audioStart'])>3:continue
        left=max(0,min(ae-frame(a['audioEnd'])+3,ae-frame(a['start'])-20))
        right=max(0,min(frame(b['audioStart'])+3-bs,frame(b['end'])-bs-20))
        if left+right<need:continue
        trim=min(left,need);delay=need-trim;new_end=(ae-trim)/fps;new_start=(bs+delay)/fps
        if cuts is None or any(min(a['end'],new_end)<t<=max(a['end'],new_end) or min(b['start'],new_start)<t<=max(b['start'],new_start) for t in cuts):continue
        before=[a['end'],b['start']];a['end'],b['start']=new_end,new_start
        for c in (a,b):invalidate(c)
        entry={'left':a['id'],'right':b['id'],'before':before,'after':[new_end,new_start],
               'reason':'Two-frame gap inside three-frame original-audio sync tolerance; all words preserved'}
        events.append(entry);a.setdefault('boundaryRepairs',[]).append(entry);b.setdefault('boundaryRepairs',[]).append(entry)
    return out,events
