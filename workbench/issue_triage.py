"""Review priorities, not delivery exemptions; count affected cues once per track."""
from collections import Counter,defaultdict

LABELS={1:'听写与内容疑点',2:'CPS、超行、时码与闪现',3:'其他问题',4:'单纯 WPM'}
CONTENT={'unresolved_content','name_variant','preferred_spelling','source_words_missing','source_words_changed','semantic_evidence_conflict','lexical_change','source_group_conflict','source_group_missing','source_baseline_changed'}
TECHNICAL={'cps_over_17','line_limit','simultaneous_line_limit','simultaneous_text_load','duration_short','duration_long','time_bounds','gap_under_2_frames','overlap','simultaneous_dialogue_overlap','export_event_short','composite_duration_long','timing_evidence_unresolved','song_timing_unresolved','evidence_outside_clip'}

def priority(flags):
 flags=set(flags)
 if flags & CONTENT:return 1
 if flags & TECHNICAL:return 2
 if flags=={'wpm_over_120'}:return 4
 return 3

def build(state,quality):
 tracks={}
 for track in ('standard','sdh'):
  cues={str(c['id']):c for c in state.get(track,[])};flags=defaultdict(set);notes=defaultdict(list);events=[];unmapped=[]
  for issue in quality['tracks'][track]['issues']:
   blocking=issue.get('blocking_flags',issue.get('flags',[]))
   if not blocking:continue
   ids=issue.get('cue_ids') or str(issue.get('id','')).split('+')
   found=[str(i) for i in ids if str(i) in cues]
   if not found and issue.get('group'):found=[ident for ident,c in cues.items() if str(c.get('sourceGroup'))==str(issue['group'])]
   if not found:unmapped.append(dict(issue,priority=priority(blocking)))
   if len(found)>1:events.append({'cue_ids':found,'start':issue.get('start'),'end':issue.get('end'),'flags':list(blocking)})
   for ident in found:flags[ident].update(blocking)
  for finding in quality.get('review_findings',[]):
   ident=str(finding.get('id',''))
   if finding.get('action') in {'missing_sound_review','missing_speech_review'} and ident not in cues:
    if track=='sdh' or finding.get('action')=='missing_speech_review':
     unmapped.append(dict(finding,priority=3 if finding.get('action')=='missing_sound_review' else 1))
    continue
   if ident not in cues or finding.get('track',track)!=track:continue
   if finding.get('action')=='missing_sound_review':continue
   flags[ident].add('unresolved_content');notes[ident].append(finding.get('reason','需核对原声'))
  if track=='sdh':
   for task in quality.get('sound_evidence_tasks',[]):
    ident=str(task.get('id',''))
    if ident in cues:flags[ident].add('sound_necessity_review');notes[ident].append(task.get('proposal',{}).get('reason','声音重要性或描述需核对'))
  items=[]
  for ident,fs in flags.items():
   c=cues[ident];p=priority(fs)
   items.append({'track':track,'id':ident,'start':c['start'],'end':c['end'],'text':c['text'],'priority':p,'category':LABELS[p],'flags':sorted(fs),'notes':list(dict.fromkeys(notes[ident])),'assessment':'content_question_not_confirmed_error' if p==1 else 'technical_or_evidence_finding' if p==2 else 'reading_speed_constraint' if p==4 else 'other_review_item'})
  items.sort(key=lambda x:(x['priority'],x['start'],x['id']))
  counts=Counter(str(x['priority']) for x in items)
  tracks[track]={'affected_cues':len(items),'by_priority':{str(p):counts[str(p)] for p in LABELS},'items':items,'joint_event_findings':events,'joint_event_count':len(events),'unmapped_findings':unmapped,'unmapped_finding_count':len(unmapped)}
 return {'policy':'content_then_cps_layout_timing_flash_then_other_then_wpm_only','labels':LABELS,'tracks':tracks,'meaning':'Each affected cue is assigned once to its highest review priority. Joint events are separately recorded, not added to affected cue counts. Content doubts are not confirmed errors. Delivery rules and acceptance are unchanged. Ordinary and SDH tracks share dialogue and must not be summed as independent defects.'}
