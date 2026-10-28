"""Apply complete audio-review proposals to an isolated candidate, with audit trail."""
import copy,json,re
from fidelity import words
from timing_review import equivalence
from character_policy import merged_protected_names

def reviewed_candidate(state,files):
 out=copy.deepcopy(state);verdicts={}
 for f in files:
  data=json.loads(f.read_text())
  for v in data['parsed']['verdicts']:
   if v['id'] in verdicts:raise ValueError('Duplicate review ID')
   verdicts[v['id']]=dict(v,evidence=str(f))
 if set(verdicts)!={c['id'] for c in state['standard']}:raise ValueError('Incomplete repair review')
 rows=[];ledger=[]
 for c in out['standard']:
  v=verdicts[c['id']];before=copy.deepcopy(c)
  # Respect locked recordings and names explicitly protected by this project.
  if v['action']=='CORRECT' and not v['uncertain']:
   protected_song=c.get('songMaster') and words(v.get('text',''))!=words(c['text'])
   merged_names=merged_protected_names(c['text'],v.get('text',''),state.get('projectSettings',{}).get('protectedNames',[]))
   if protected_song or merged_names:
    v=copy.deepcopy(v);v['uncertain']=True
    v['reason']=('Locked song recording requires master-version adjudication. ' if protected_song else 'Explicit project registry protects separate names; do not merge them. ')+v.get('reason','')
  if c.get('crossModalConflicts'):
   v=copy.deepcopy(v);v['uncertain']=True
   v['reason']='Existing speech/sound disagreement requires explicit adjudication. '+v.get('reason','')
  if v['action']=='REMOVE' and not v['uncertain']:
   ledger.append({'id':c['id'],'before':before,'after':None,'evidence':v});continue
  if v['action']=='CORRECT' and not v['uncertain']:
   old=[x['token'] for x in equivalence([{'word':c['text']}])];new=[x['token'] for x in equivalence([{'word':v['text']}])]
   # Number styling belongs to deterministic formatter, never model preference.
   if old!=new:
    c['text']=v['text'];c['sourceText']=v['text'].replace('♪','').strip();c['sourceGroup']=c['id'];c.pop('numberFormatting',None);c.pop('wordAnchors',None)
    c['timingReview']='pending: revised words need alignment'
  c['audioAdjudication']=v;c['checked']=False
  if v['uncertain']:c['unresolved']='Targeted audio review remains uncertain: '+v['reason']
  else:c['unresolved']='时间边界尚无逐词证据，需复核。' if c.get('timingReview','').startswith('pending') else ''
  if c.get('crossModalConflicts'):
   from review_conflicts import mark
   c=mark([c],c['crossModalConflicts'])[0]
  ledger.append({'id':c['id'],'before':before,'after':copy.deepcopy(c),'evidence':v});rows.append(c)
 out['standard']=rows;out['sdh']=copy.deepcopy(rows)
 out['sourceManifest']={k:{c.get('sourceGroup',c['id']):c.get('sourceText',c['text'])for c in rows}for k in ('standard','sdh')}
 out['release']['content_verified']=False
 return out,ledger
