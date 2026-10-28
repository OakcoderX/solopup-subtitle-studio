from character_policy import merged_protected_names
"""Conservative repair from a complete-episode witness; never grants approval."""
import copy, json, re
import hashlib
from functools import lru_cache
from collections import Counter, defaultdict
from pathlib import Path
from fractions import Fraction
from fidelity import words, audit
from layout_policy import prepare, wrap
from evidence_gate import signature, evidence_flags
from timing_review import align, apply_forced, equivalence
from tail_room import extend_tails
from sound_evidence_recheck import apply_agreements

TIMING_NOTE='时间边界尚无逐词证据，需复核。'

def grouped(rows):
 out=defaultdict(list)
 for c in rows:
  if c.get('kind')!='sound':out[str(c.get('sourceGroup',c['id']))].append(c)
 for g in out.values():g.sort(key=lambda c:(c['start'],c['end']))
 return out

def drop_exact_duplicate_groups(state):
 """A single narrator's same words at the same acoustic anchors are one event.

 Remove only complete duplicate source groups; this never deduplicates genuine
 sequential repetitions or simultaneous lines from different named speakers.
 """
 out=copy.deepcopy(state);groups=grouped(out.get('standard',[]));removed={};events=[]
 keys=list(groups);fps=float(Fraction(str(state.get('frameRate','24'))))
 for i,key in enumerate(keys):
  if key in removed:continue
  a=groups[key]
  if any(c.get('songMaster') or c.get('kind')=='song' or c.get('checked') or c.get('presentation')!='voiceover' or c.get('timingReview')!='machine_word_matched' for c in a):continue
  for other in keys[i+1:]:
   if other in removed:continue
   b=groups[other]
   if any(c.get('songMaster') or c.get('kind')=='song' or c.get('checked') or c.get('presentation')!='voiceover' or c.get('timingReview')!='machine_word_matched' for c in b):continue
   if not words(' '.join(c['text'] for c in a))==words(' '.join(c['text'] for c in b)):continue
   # Different permitted display tails do not make a second spoken utterance.
   if abs(a[0].get('audioStart',a[0]['start'])-b[0].get('audioStart',b[0]['start']))>3/fps or abs(a[-1].get('audioEnd',a[-1]['end'])-b[-1].get('audioEnd',b[-1]['end']))>3/fps:continue
   if abs(a[0]['start']-b[0]['start'])>.5 or abs(a[-1]['end']-b[-1]['end'])>.5:continue
   if not all(c.get('wordAnchors') and c.get('timingEvidence') for c in a+b):continue
   removed[other]=key;events.append({'rule':'same_narrator_same_acoustic_words','removed_group':other,'retained_group':key,'removed_ids':[c['id'] for c in b],'retained_ids':[c['id'] for c in a],'start':a[0]['start'],'end':a[-1]['end'],'text':' '.join(c['text'] for c in a),'reason':'Complete identical narrator utterance groups at independently matched overlapping audio-word anchors; not sequential repetition'})
 if removed:
  for track in ('standard','sdh'):
   out[track]=[c for c in out.get(track,[]) if c.get('kind')=='sound' or str(c.get('sourceGroup',c['id'])) not in removed]
   for g in removed:out.get('sourceManifest',{}).get(track,{}).pop(g,None)
  out.setdefault('duplicateSourceResolutions',[]).extend(events)
 return out,events

def local_timing(state,witness,forced,cuts):
 """Reuse measured words only for previously pending non-song timing, <=0.5s."""
 out=copy.deepcopy(state);rate=out.get('frameRate','24');fps=float(Fraction(str(rate)));old={c['id']:c for c in out['standard']};events=[]
 matched,_=align(out['standard'],witness,fps);matched,_=apply_forced(matched,forced,witness,fps)
 replacements={}
 for c in matched:
  prior=old.get(c['id'])
  if not prior or prior.get('checked') or prior.get('songMaster') or prior.get('kind')=='song' or prior.get('timingReview')=='machine_word_matched':continue
  if c.get('timingReview')!='machine_word_matched' or words(c['text'])!=words(prior['text']):continue
  if max(abs(c['start']-prior['start']),abs(c['end']-prior['end']))>.5:continue
  c['unresolved']=c.get('unresolved','').replace(TIMING_NOTE,'').strip();replacements[c['id']]=c
  events.append({'id':c['id'],'before':[prior['start'],prior['end']],'after':[c['start'],c['end']],'reason':'Exact independent word evidence; bounded correction; all words retained'})
 for track in ('standard','sdh'):
  out[track]=[copy.deepcopy(replacements[c['id']]) if c['id'] in replacements and c.get('kind')!='sound' and words(c['text'])==words(replacements[c['id']]['text']) else c for c in out.get(track,[])]
 return out,events

def merge_verified_fragments(rows,cuts,rate='24'):
 """Recover one readable normal-subtitle cue from same-utterance fragments."""
 out=copy.deepcopy(rows);events=[];fps=float(Fraction(str(rate)));used={str(c['id']) for c in rows}
 for key,group in grouped(rows).items():
  if len(group)<2 or any(c.get('songMaster') or c.get('kind')=='song' or c.get('checked') or not acoustic_match(c) for c in group):continue
  if len({c.get('presentation') for c in group})!=1 or group[-1]['end']-group[0]['start']>7:continue
  if any(not 0<=b['start']-a['end']<=.4 or any(a['end']<t<b['start'] for t in cuts) for a,b in zip(group,group[1:])):continue
  text=wrap(' '.join(c['text'] for c in group))
  if len(text.splitlines())>2 or max(map(len,text.splitlines()))>42:continue
  if words(text)!=words(group[0].get('sourceText','')):continue
  if key in used and not any(c['id']==key for c in group):continue
  new=copy.deepcopy(group[0]);new.update(id=key,text=text,end=group[-1]['end'],audioEnd=group[-1].get('audioEnd',group[-1]['end']),wordAnchors=[copy.deepcopy(w) for c in group for w in c['wordAnchors']],checked=False)
  new['unresolved']='; '.join(dict.fromkeys(c.get('unresolved','') for c in group if c.get('unresolved')))
  new['verifiedFragmentMerge']={'children':[c['id'] for c in group],'reason':'Same complete source utterance, measured consecutive word boundaries, two readable lines, all words retained'}
  if not new['unresolved'] and all(c.get('wholeEpisodeAudioReview') for c in group):new.pop('reviewInvalidated',None);new['reviewBinding']=signature(new)
  identifiers={c['id'] for c in group};out=[c for c in out if c['id'] not in identifiers]+[new];events.append(new['verifiedFragmentMerge'])
 return sorted(out,key=lambda c:(c['start'],c['end'])),events

def unique_verdicts(rows):
 result={};conflicts=set()
 for v in rows:
  key=str(v['id'])
  if key in result and any(result[key].get(k)!=v.get(k) for k in ('verdict','corrected_text','uncertain')):conflicts.add(key)
  result[key]=v
 for key in conflicts:result[key]={'id':key,'verdict':'uncertain','uncertain':True,'reason':'The whole-episode response contains conflicting verdicts for this ID.'}
 return result

def prior_audio_path(c):
 for candidate in ((c.get('audioAdjudication') or {}).get('evidence'),c.get('sourceEvidence')):
  if candidate and Path(candidate).is_file():return str(candidate)
 return None

def acoustic_match(c):
 anchors=c.get('wordAnchors',[])
 return bool(c.get('timingReview')=='machine_word_matched' and c.get('timingEvidence') and anchors and
  [x['token'] for x in equivalence([{'word':c['text']}])]==[x['token'] for x in equivalence(anchors)])

def corroborated_content_repairs(state,parsed,path,witness):
 """Correct words only with exact independent ASR, or explicit source evidence.

 The model's own approximate timestamps are never used as a replacement for
 current source boundaries. Locked song lyrics and ambiguous character calls
 remain protected and are reported rather than rewritten.
 """
 out=copy.deepcopy(state);verdicts=unique_verdicts(parsed.get('cue_reviews',[]));spoken=defaultdict(list);changes=[];deleted=set();replacements={}
 fps=float(Fraction(str(out.get('frameRate','24'))))
 for s in parsed.get('speech',[]):
  if len(s.get('source_cue_ids',[]))==1:spoken[str(s['source_cue_ids'][0])].append(s)
 for c in out.get('standard',[]):
  v=verdicts.get(str(c['id']),{});reason=str(v.get('reason',''));old=words(c['text'])
  if c.get('checked') or c.get('songMaster') or c.get('kind')=='song' or c.get('crossModalConflicts') or v.get('uncertain') is True or v.get('verdict')=='uncertain':continue
  prior=(c.get('audioAdjudication') or {});prior_reason=prior.get('reason','');prior_path=prior_audio_path(c)
  source_words={'cat','oven','character','animal','friends'}
  shared_source=any(re.search(r'\b'+w+r'\b',reason,re.I) and re.search(r'\b'+w+r'\b',prior_reason,re.I) for w in source_words)
  false_lexical=bool(re.search(r'nonverbal|nonlexical|false lexical',reason,re.I))
  if (v.get('verdict') in {'correct','nonlexical'} and false_lexical and shared_source and prior_path
      and old and len(old)<=6 and not any(w in {str(n).lower() for n in out.get('projectSettings',{}).get('protectedNames',[])} for w in old)
      and not re.search(r'unclear|ambiguous|could be|uncertain',reason,re.I)):
   deleted.add(c['id']);changes.append({'id':c['id'],'action':'remove_false_lexical_animal_vocalization','before':copy.deepcopy(c),'after':None,'evidence':[prior_path,str(path)],'reason':reason});continue
  if v.get('verdict')!='correct':continue
  text=v.get('corrected_text')
  if not text and len(spoken.get(str(c['id']),[]))==1:
   utterance=spoken[str(c['id'])][0]
   if utterance.get('uncertain') is not True:text=utterance.get('text')
  if not text or words(text)==old or not old or abs(len(words(text))-len(old))>5:continue
  counterparts=[x for x in state.get('sdh',[]) if x.get('kind')!='sound' and x.get('id')==c['id']]
  if len(counterparts)!=1 or words(counterparts[0]['text'])!=old:continue
  trial=copy.deepcopy(c);trial['text']=wrap(text);trial.pop('wordAnchors',None)
  aligned,_=align([trial],witness,fps)
  if len(aligned)!=1 or not acoustic_match(aligned[0]):continue
  new=aligned[0]
  if max(abs(new['start']-c['start']),abs(new['end']-c['end']))>1:continue
  new['unresolved']='';new['audioCorrectionEvidence']={'whole_episode':str(path),'independent_source':'word_timestamps.json','reason':reason,'prior_text':c['text']};replacements[c['id']]=new
  changes.append({'id':c['id'],'action':'independently_corroborated_word_correction','before':copy.deepcopy(c),'after':copy.deepcopy(new),'evidence':str(path),'reason':reason})
 if replacements or deleted:
  affected={str(c.get('sourceGroup',c['id'])) for c in state['standard'] if c['id'] in set(replacements)|deleted}
  for track in ('standard','sdh'):
   out[track]=[copy.deepcopy(replacements[c['id']]) if c['id'] in replacements and c.get('kind')!='sound' else c for c in out.get(track,[]) if c.get('kind')=='sound' or c['id'] not in deleted]
   groups=grouped(out[track])
   for g in affected:
    if g not in groups:out.get('sourceManifest',{}).get(track,{}).pop(g,None);continue
    text=' '.join(c['text'].replace('♪','').strip() for c in groups[g]);out.setdefault('sourceManifest',{}).setdefault(track,{})[g]=text
    for c in groups[g]:c.setdefault('originalSourceText',c.get('sourceText'));c['sourceText']=text
  out.setdefault('audioCorrectionLedger',[]).extend(changes)
 return out,changes

def apply_review(state,result,path,decisions,candidates,witness,reviewed_ids=None):
 """Clear only specifically rechecked doubts; disagreements remain explicit."""
 out=copy.deepcopy(state);parsed=result['parsed'];verdicts=unique_verdicts(parsed.get('cue_reviews',[]));events=[];pending=[]
 spoken=defaultdict(list)
 for s in parsed.get('speech',[]):
  for ident in s.get('source_cue_ids',[]):spoken[str(ident)].append(s)
 expected=({str(c['id']) for c in state['standard']} if reviewed_ids is None else set(map(str,reviewed_ids)))
 if expected-set(verdicts):raise ValueError('Whole-episode review omits input cue IDs')
 for track in ('standard','sdh'):
  for c in out.get(track,[]):
   if c.get('kind')=='sound' or str(c['id']) not in verdicts:continue
   if reviewed_ids is not None and str(c['id']) not in expected:continue
   v=verdicts[str(c['id'])];heard=spoken.get(str(c['id']),[])
   uncertain=v.get('uncertain',v.get('verdict')=='uncertain') is not False or any(x.get('uncertain') for x in heard)
   corrected_here=(v.get('verdict')=='correct' and (c.get('audioCorrectionEvidence') or {}).get('whole_episode')==str(path) and words(v.get('corrected_text',''))==words(c['text']))
   exact=corrected_here or (v.get('verdict')=='agree' and (not heard or words(' '.join(x['text'] for x in heard))==words(c['text'])))
   if uncertain or not exact:
    pending.append({'track':track,'id':c['id'],'start':c['start'],'end':c['end'],'text':c['text'],'action':'audio_adjudication_pending','verdict':v,'evidence':str(path)});continue
   before=copy.deepcopy(c);pres=v.get('presentation') or (heard[0].get('presentation') if len(heard)==1 else None)
   pres_evidence=v.get('presentation_evidence') or (heard[0].get('presentation_evidence') if len(heard)==1 else None)
   if pres in {'voiceover','device','song','onscreen'} and pres_evidence:
    if c.get('presentation') in {None,'unknown',pres}:
     c['presentation']=pres;c['presentationEvidence']=pres_evidence;c['italic']=pres in {'voiceover','device','song'}
   c['wholeEpisodeAudioReview']={'status':'machine_reviewed_not_human_approved','verdict':v,'evidence':str(path),'input_text':before['text'],'input_start':before['start'],'input_end':before['end']}
   if acoustic_match(c):c['unresolved']=c.get('unresolved','').replace(TIMING_NOTE,'').strip()
   if (v.get('resolves_prior_disagreement') is True and v.get('prior_reason_addressed') and prior_audio_path(c) and not c.get('crossModalConflicts')):
    timing_pending=c.get('timingReview','').startswith('pending') or TIMING_NOTE in c.get('unresolved','')
    c['resolvedPriorUncertainty']={'note':c.get('unresolved',''),'reason':v['prior_reason_addressed'],'prior_evidence':prior_audio_path(c),'evidence':str(path)}
    # Content agreement is not word-level timing evidence. Settle the spoken
    # wording while retaining the independent timing question in priority 2.
    c['unresolved']=TIMING_NOTE if timing_pending and not acoustic_match(c) else ''
   if acoustic_match(c) and not c.get('unresolved') and not c.get('crossModalConflicts'):
    c.pop('reviewInvalidated',None);c['reviewBinding']=signature(c)
   if any(before.get(k)!=c.get(k) for k in ('presentation','italic','unresolved','reviewInvalidated','reviewBinding')):
    events.append({'track':track,'id':c['id'],'reason':'Fresh complete-episode audio witness plus retained independent timing evidence','evidence':str(path)})
 sound_results={};by_id={str(v['id']):v for v in parsed.get('sound_reviews',[])}
 for ident,v in by_id.items():
  if not all(k in v for k in ('caption','decision','audio_evidence','picture_evidence','reason','narrative_value')):continue
  if v.get('uncertain') is not False:continue
  proposal=copy.deepcopy(v);old=decisions.get(ident,{})
  if v['decision'] in {'KEEP','REVISE'} and old.get('status') in {'KEEP','REVISE'} and v['caption'].strip()==old.get('caption','').strip():proposal['decision']=old['status']
  sound_results[ident]=(proposal,Path(path),result['interval'])
 # Reuse a real stored second proposal and let the full-episode witness explicitly
 # adjudicate it. Never count the same model response as two evidence sources.
 for task in state.get('soundEvidenceRecheckTasks',[]):
  oldp=task.get('proposal',{});ident=str(oldp.get('id',''));v=by_id.get(ident);epath=task.get('evidence')
  if not v or v.get('uncertain') is not False or not v.get('resolves_prior_disagreement') or not v.get('prior_reason_addressed'):continue
  if not epath or not Path(epath).is_file() or str(epath)==str(path):continue
  if oldp.get('decision')!=v.get('decision') or (v['decision']!='REMOVE' and oldp.get('caption','').strip()!=v.get('caption','').strip()):continue
  p=copy.deepcopy(oldp);p.update(adjudication=v,adjudication_evidence=str(path));sound_results[ident]=(p,Path(epath),result['interval'])
 out,new_decisions,sound_events,sound_tasks=apply_agreements(out,decisions,candidates,sound_results)
 retained_pending=([x for x in state.get('wholeEpisodeReviewPending',[]) if str(x.get('id')) not in expected] if reviewed_ids is not None else [])
 out['wholeEpisodeReviewPending']=retained_pending+pending
 existing=[x for x in out.get('latestReviewFindings',[]) if x.get('source')!='whole_episode_recheck' or (reviewed_ids is not None and str(x.get('id')) not in expected)]
 out['latestReviewFindings']=existing+[dict(x,source='whole_episode_recheck',reason=x['verdict'].get('reason','Audio adjudication remains pending')) for x in pending]
 review_record={'evidence':str(path),'coverage':len(expected),'sound_coverage':len(by_id),'humanApproved':False}
 if reviewed_ids is None:out['wholeEpisodeReview']=review_record
 else:out.setdefault('scopedWholeEpisodeFollowups',[]).append(review_record)
 # Newly detected sounds remain concrete review work; never silently discard.
 missing=(state.get('wholeEpisodeMissingSoundCandidates',[]) if reviewed_ids is not None else [])+parsed.get('missing_sounds',[])
 out['wholeEpisodeMissingSoundCandidates']=list({(x.get('start'),x.get('end'),x.get('caption')):x for x in missing}.values())
 for x in parsed.get('missing_sounds',[]):
  out['latestReviewFindings'].append(dict(x,source='whole_episode_recheck',action='missing_sound_review',reason=x.get('reason') or x.get('audio_evidence') or 'Meaningful sound proposed by complete-episode audio review; candidate registration and timing required'))
 out.setdefault('release',{})['content_verified']=False
 return out,new_decisions,{'cue_changes':events,'sound_changes':sound_events,'pending_cues':pending,'pending_sounds':sound_tasks,'missing_sounds':parsed.get('missing_sounds',[])}

def assert_fidelity(state):
 for track in ('standard','sdh'):
  problems=audit(state.get(track,[]),state.get('sourceManifest',{}).get(track,{}))
  if problems:raise ValueError('Word preservation failed: '+json.dumps(problems[:2],ensure_ascii=False))

@lru_cache(maxsize=4096)
def evidence_digest(path):
 p=Path(path)
 return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

def explicit_sound_adjudications(state,decisions,result,path,prior_state=None):
 """Settle an AI proposal only through explicit whole-episode adjudication.

 A distinct stored original-audio witness plus this complete-episode review are
 required, matching the existing two-witness semantic gate. Copied files count
 once; neither majority voting nor model confidence alone suffices. The new
 witness must explicitly address prior reasoning against the actual full mix.
 Manual decisions and actual speech remain protected.
 """
 out=copy.deepcopy(state);updated=copy.deepcopy(decisions);events=[];resolved=set()
 newpath=str(Path(path).resolve());newhash=evidence_digest(newpath)
 if not newhash:return out,updated,events
 proposals={str(v['id']):v for v in result.get('parsed',{}).get('sound_reviews',[])}
 for c in list(out.get('sdh',[])):
  if c.get('kind')!='sound' or c.get('checked') or c.get('crossModalConflicts'):continue
  ident=str(c.get('sourceSoundId',''));d=updated.get(ident,{});v=proposals.get(ident,{})
  if d.get('humanApproved') or d.get('confirmedPrior'):continue
  if (v.get('uncertain') is not False or v.get('confidence')!='high' or v.get('resolves_prior_disagreement') is not True
      or len(str(v.get('prior_reason_addressed','')).strip())<20 or not v.get('audio_evidence') or not v.get('narrative_value')):continue
  if v.get('visual_redundancy')=='yes' and re.search(r'insufficient|not shown|no sample',str(v.get('picture_evidence','')),re.I):continue
  prior_paths=[d.get('evidence')]+list((c.get('semanticReview') or d.get('semanticReview') or {}).get('evidence',[]))
  old_sound=next((x for x in (prior_state or {}).get('sdh',[]) if x.get('kind')=='sound' and str(x.get('sourceSoundId'))==ident),{})
  old_decision=old_sound.get('sourceDecision',{})
  prior_paths.extend([old_decision.get('evidence')]+list((old_sound.get('semanticReview') or old_decision.get('semanticReview') or {}).get('evidence',[])))
  for task in state.get('soundEvidenceRecheckTasks',[])+(prior_state or {}).get('soundEvidenceRecheckTasks',[]):
   if str(task.get('proposal',{}).get('id',''))==ident:
    prior_paths.extend([task.get('evidence'),task.get('proposal',{}).get('adjudication_evidence')])
  witnesses={}
  for p in prior_paths:
   if not p:continue
   h=evidence_digest(str(p))
   if h and h!=newhash:witnesses.setdefault(h,str(Path(p).resolve()))
  if len(witnesses)<1:continue
  evidence=list(witnesses.values())+[newpath];before=copy.deepcopy(c);action=v.get('decision')
  if action=='REMOVE':
   out['sdh'].remove(c);d.update(status='REMOVE',caption=v.get('caption',c['text']),uncertain=False,reviewer='assistant',humanApproved=False,
    removalAdjudication={'prior':copy.deepcopy(decisions.get(ident,{})),'whole_episode':v,'evidence':evidence})
  elif action in {'KEEP','REVISE'}:
   label=str(v.get('caption','')).strip()
   if not re.fullmatch(r'\[[^\[\]\n]+\]',label) or len(label.strip('[]').split())>5:continue
   if re.fullmatch(r'\s*(?:none|nothing|redundant|no additional information)[.!]?\s*',v['narrative_value'],re.I):continue
   start=c.get('soundAudioStart',c['start']);end=c.get('soundAudioEnd',c.get('soundOriginalEnd',c['end']))
   sem={'status':'machine_reviewed','caption':label,'decision':action,'start':start,'end':end,'audioEvidence':v['audio_evidence'],'pictureEvidence':v.get('picture_evidence','insufficient'),'narrativeValue':v['narrative_value'],'visualRedundancy':v.get('visual_redundancy','insufficient'),'evidence':evidence,'clip':result['interval'],'uncertain':False,'humanApproved':False}
   probe=copy.deepcopy(c);probe.update(text=label,semanticReview=sem);probe.pop('reviewInvalidated',None);probe['reviewBinding']=signature(probe)
   if evidence_flags(probe):continue
   c.update(text=label,semanticReview=sem,reviewState='machine_reviewed_not_human_approved',checked=False,unresolved='')
   if c.get('speedReview') and label!=before['text']:c['speedReview'].update(accepted=False,invalidated=True)
   c.pop('reviewInvalidated',None);c['reviewBinding']=signature(c)
   d.update(status=action,caption=label,uncertain=False,reviewer='assistant',humanApproved=False,semanticReview=copy.deepcopy(sem));c['sourceDecision']=copy.deepcopy(d)
   c['resolvedPriorSoundUncertainty']={'note':before.get('unresolved',''),'reason':v['prior_reason_addressed'],'evidence':evidence}
  else:continue
  resolved.add(str(c.get('id')));events.append({'id':c['id'],'candidate':ident,'action':action,'before':before,'after':None if action=='REMOVE' else copy.deepcopy(c),'reason':v['prior_reason_addressed'],'evidence':evidence})
 out['soundEvidenceRecheckTasks']=[t for t in out.get('soundEvidenceRecheckTasks',[]) if str(t.get('id')) not in resolved]
 out.setdefault('release',{})['content_verified']=False
 return out,updated,events

def explicitly_corroborated_words(state,result,path,prior_result,prior_path):
 """Two real audio passes propose the same explicit correction; timing stays open."""
 out=copy.deepcopy(state);changes=[];updates={};prior=unique_verdicts(prior_result.get('parsed',{}).get('cue_reviews',[]));current=unique_verdicts(result.get('parsed',{}).get('cue_reviews',[]))
 if not evidence_digest(str(path)) or not evidence_digest(str(prior_path)) or evidence_digest(str(path))==evidence_digest(str(prior_path)):return out,changes
 for c in state.get('standard',[]):
  v=current.get(str(c['id']),{});old=prior.get(str(c['id']),{});text=v.get('corrected_text');oldtext=old.get('corrected_text')
  if not oldtext:
   speech=[x for x in prior_result.get('parsed',{}).get('speech',[]) if x.get('source_cue_ids')==[c['id']] and x.get('uncertain') is not True]
   if len(speech)==1:oldtext=speech[0].get('text')
  if c.get('checked') or c.get('songMaster') or c.get('kind')=='song' or c.get('crossModalConflicts'):continue
  if v.get('verdict')!='correct' or old.get('verdict')!='correct' or v.get('uncertain') is not False or old.get('uncertain') is True:continue
  if not text or not oldtext or words(text)!=words(oldtext) or words(text)==words(c['text']):continue
  if not v.get('resolves_prior_disagreement') or not v.get('audio_evidence') or len(str(v.get('prior_reason_addressed','')))<20:continue
  if merged_protected_names(c['text'],text,state.get('projectSettings',{}).get('protectedNames',[])):continue
  if abs(len(words(text))-len(words(c['text'])))>5:continue
  counterparts=[x for x in state.get('sdh',[]) if x.get('kind')!='sound' and x.get('id')==c['id']]
  if len(counterparts)!=1 or words(counterparts[0]['text'])!=words(c['text']):continue
  new=copy.deepcopy(c);new.update(text=wrap(text),checked=False,timingReview='pending: explicitly corrected words need independent timing',timingEvidence='',unresolved=TIMING_NOTE);new.pop('wordAnchors',None);new.pop('reviewBinding',None)
  if new.get('speedReview'):new['speedReview'].update(accepted=False,invalidated=True)
  new['audioCorrectionEvidence']={'whole_episode':str(path),'prior_whole_episode':str(prior_path),'prior_text':c['text'],'reason':v['prior_reason_addressed'],'humanApproved':False}
  updates[c['id']]=new;changes.append({'id':c['id'],'before':c['text'],'after':new['text'],'evidence':[str(prior_path),str(path)],'reason':v['prior_reason_addressed']})
 affected={str(c.get('sourceGroup',c['id'])) for c in state.get('standard',[]) if c['id'] in updates}
 for track in ('standard','sdh'):
  out[track]=[copy.deepcopy(updates[c['id']]) if c.get('kind')!='sound' and c['id'] in updates else c for c in out.get(track,[])]
  groups=grouped(out[track])
  for key in affected:
   text=' '.join(c['text'].replace('♪','').strip() for c in groups[key]);out.setdefault('sourceManifest',{}).setdefault(track,{})[key]=text
   for c in groups[key]:c.setdefault('originalSourceText',c.get('sourceText'));c['sourceText']=text
 out.setdefault('explicitAudioCorrectionLedger',[]).extend(changes)
 return out,changes

