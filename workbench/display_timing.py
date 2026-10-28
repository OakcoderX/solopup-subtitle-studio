"""Bounded sound-label synchronization; never move dialogue or add blank slots."""
import copy,math,re
from presentation import visible_events,layout_parts,position_changes

def score(rows,fps):
 def frame(t,rate):return math.floor(t*fps+.5)
 events=visible_events(rows,frame,fps)
 return sum(10*(len(layout_parts(g))>2)+3*(b-a<20) for a,b,g in events)+2*len(position_changes(rows,frame,fps))+sum(10*(c['end']-c['start']>7+.001) for c in rows)

def optimize(rows,cuts=None,fps=24):
 out=copy.deepcopy(rows);cuts=cuts or []
 for c in out:
  if c.get('kind')!='sound' or c.get('displayTimingLock'):continue
  original_start=c.get('soundAudioStart',c['start']);original_end=c.get('soundAudioEnd',c.get('soundOriginalEnd',c['end']))
  needed=max(20/fps,len(c['text'])/17,len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",c['text']))/2)
  # Sound descriptions can end before a continuing audible event; no repeated label.
  proposals=[]
  if c['end']-c['start']>7 and needed<=7:proposals.append((c['start'],c['start']+7))
  for d in out:
   if d.get('kind')=='sound':
    if 0<c['end']-d['start']<=.5 and c['start']<d['start']:proposals.append((c['start'],d['start']-2/fps))
    continue
   if not (d['start']<c['end'] and c['start']<d['end']):continue
   start=c['start'];end=c['end']
   if 0<d['start']-start<=.5 and d['start']-original_start<=.5:start=d['start']
   if abs(d['end']-end)<=.5 and d['end']<=original_end+.5:end=d['end']
   if not any((min(c['end'],end)<t<=max(c['end'],end)) or (c['start']<t<=start) for t in cuts):proposals.append((start,end))
  best=score(out,fps);chosen=None
  for start,end in proposals:
   start=round(start*fps)/fps;end=round(end*fps)/fps
   if not needed<=end-start<=7:continue
   before=c['start'],c['end'];c['start'],c['end']=start,end;value=score(out,fps);c['start'],c['end']=before
   if value<best:best=value;chosen=(start,end)
  if chosen:
   before=[c['start'],c['end']];c['soundAudioStart']=original_start;c['soundAudioEnd']=original_end;c['start'],c['end']=chosen
   c['checked']=False;c['displayTimingLock']=True
   c['displaySynchronization']={'before':before,'after':list(chosen),'reason':'Sound label only: <=0.5s delayed onset/shared exit or maximum 7s exposure; dialogue untouched; screen violations decrease'}
   if c.get('speedReview'):c['speedReview'].update(accepted=False,invalidated=True)
 return out
