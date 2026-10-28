"""Evidence-led P1/P2 recovery. Content resolutions and physical edits stay separate."""
import copy,json,re,hashlib,math
from pathlib import Path
from fractions import Fraction
from fidelity import words
from evidence_gate import signature
from timing_review import equivalence,display_anchors
from layout_policy import wrap,prepare
from issue_triage import build
from quality_gate import report
from whole_episode_repair import assert_fidelity,TIMING_NOTE


def resolve_superseded_findings(state,registry):
 out=copy.deepcopy(state);kept=[];closed=[];masters={m['id']:m for m in registry.get('masters',[])}
 for f in out.get('latestReviewFindings',[]):
  # Unlocated sound/speech proposals and model uncertainty never disappear.
  if f.get('action') in {'missing_sound_review','missing_speech_review'}:kept.append(f);continue
  track=f.get('track');candidates=[c for t in ('standard','sdh') if not track or track==t for c in out[t] if str(c['id'])==str(f.get('id')) and c.get('kind')!='sound'];reasons=[]
  for c in candidates:
   orth=c.get('orthographicResolution',{})
   if orth.get('evidence') and Path(orth['evidence']).is_file() and words(orth.get('before',''))==words(orth.get('after',''))==words(c['text']) and _matches_preferred(c['text'],out):
    reasons.append({'type':'canonical_token_identical_spelling','evidence':orth['evidence']});continue
   review=c.get('wholeEpisodeAudioReview',{});v=review.get('verdict',{});path=review.get('evidence');exact=words(review.get('input_text',''))==words(c['text'])
   if exact and path and Path(path).is_file() and v.get('verdict')=='agree' and v.get('uncertain') is False and v.get('resolves_prior_disagreement') is True and len(v.get('prior_reason_addressed',''))>=20 and (v.get('audio_evidence') or v.get('specific_audio_evidence')) and not c.get('crossModalConflicts') and not re.search(r'听辨疑点|Targeted audio review remains uncertain',c.get('unresolved','')):
    reasons.append({'type':'explicit_audio_adjudication_already_applied','evidence':path,'reason':v['prior_reason_addressed']});continue
   m=masters.get(c.get('songMaster'),{});canonical=any(words(c['text'])==words(l['text']) for l in m.get('lines',[]))
   # User fixes a single lyric text; this settles wording only, never recording/timing.
   if m.get('status')=='user_confirmed' and m.get('content_variants_allowed') is False and canonical and f.get('source')!='whole_episode_recheck' and not c.get('unresolved') and not c.get('crossModalConflicts'):
    reasons.append({'type':'user_canonical_lyric_already_applied','master':m['id'],'authority':m.get('authority'),'timing_approved':False})
  if candidates and len(reasons)==len(candidates):closed.append({'finding':f,'resolutions':reasons})
  else:kept.append(f)
 out['latestReviewFindings']=kept
 out.setdefault('supersededFindingResolutions',[]).extend(closed)
 return out,closed


def canonical_orthography(state,verdict_paths):
 """Only token-identical punctuation/hyphen corrections explicitly proposed by audio review."""
 out=copy.deepcopy(state);events=[];updates={}
 for path in verdict_paths:
  if not Path(path).is_file():continue
  data=json.loads(Path(path).read_text());vs=data.get('parsed',{}).get('cue_reviews',[])
  for c in out['standard']:
   if c.get('checked') or c.get('kind')=='song' or c.get('crossModalConflicts'):continue
   v=next((v for v in vs if str(v.get('id'))==str(c['id'])),{});text=v.get('corrected_text','')
   # This is spelling/layout equivalence, not correction of a different spoken word.
   if not text or v.get('verdict')!='correct' or v.get('uncertain') is not False or words(text)!=words(c['text']) or wrap(text)==c['text']:continue
   if any(x.get('checked') for x in out['sdh'] if x['id']==c['id']):continue
   if not _matches_preferred(text,out) or not _matches_preferred(c['text'],out):continue
   before=c['text'];c['text']=wrap(text);c['checked']=False;c.pop('reviewBinding',None)
   c['orthographicResolution']={'evidence':str(path),'before':before,'after':text,'canonical':'project preferred spelling'}
   c['unresolved']=TIMING_NOTE if c.get('timingReview','').startswith('pending') else ''
   updates[c['id']]=(before,copy.deepcopy(c));events.append({'id':c['id'],'before':before,'after':text,'evidence':str(path),'authority':'Explicit project preferred spelling; identical spoken tokens'})
 for c in out['sdh']:
  if c.get('kind')!='sound' and c['id'] in updates and words(c['text'])==words(updates[c['id']][0]):c['text']=updates[c['id']][1]['text'];c['checked']=False;c.pop('reviewBinding',None);c['orthographicResolution']=updates[c['id']][1]['orthographicResolution'];c['unresolved']=TIMING_NOTE if c.get('timingReview','').startswith('pending') else ''
 out.setdefault('orthographyRecovery',[]).extend(events)
 return out,events


def unique_word_alignment(c,witness):
 target=[x['token'] for x in equivalence([{'word':c['text']}])];flat=equivalence([w for s in witness.get('segments',[]) for w in s.get('words',[])])
 matches=[]
 for i,w in enumerate(flat):
  if not all(math.isfinite(float(w.get(k,float('nan')))) for k in ('start','end','probability')) or abs(w['start']-c['start'])>4:continue
  span=flat[i:i+len(target)]
  if not target or [x['token'] for x in span]!=target or abs(span[-1]['end']-c['end'])>4:continue
  if any(not all(math.isfinite(float(x.get(k,float('nan')))) for k in ('start','end','probability')) or x.get('probability',0)<.45 or x['end']<=x['start'] for x in span):continue
  if any(a['start']>b['start'] or b['start']-a['end']>2 for a,b in zip(span,span[1:])):continue
  mapped=display_anchors(c['text'],span)
  if mapped:matches.append(mapped)
 return matches[0] if len(matches)==1 else None


def issue_metrics(state):
 q=report(state);t=build(state,q);counts={track:t['tracks'][track]['by_priority'] for track in ('standard','sdh')}
 from collections import Counter
 from issue_triage import TECHNICAL
 flags=Counter((track,f) for track in ('standard','sdh') for x in q['tracks'][track]['issues'] for f in x.get('blocking_flags',[]) if f in TECHNICAL)
 return counts,flags


def technical_nonregression(before,after):
 """No new rule on any cue; aggregate gains cannot conceal displaced defects."""
 from collections import Counter
 from issue_triage import TECHNICAL
 for track in ('standard','sdh'):
  after_by_id={str(c['id']):c for c in after.get(track,[])}
  if any(c.get('checked') and c!=after_by_id.get(str(c['id'])) for c in before.get(track,[])):return False
 def keys(state):
  q=report(state);counts=Counter();pairs=set()
  for track in ('standard','sdh'):
   for issue in q['tracks'][track]['issues']:
    for flag in set(issue.get('blocking_flags',[])) & TECHNICAL:
     counts[(track,flag)]+=1
     for ident in issue.get('cue_ids') or str(issue.get('id','')).split('+'):pairs.add((track,str(ident),flag))
  return counts,pairs
 old,oldkeys=keys(before);new,newkeys=keys(after)
 return newkeys<=oldkeys and all(n<=old.get(k,0) for k,n in new.items())


def recover_timing(state,witness,witness_path,cuts):
 from tail_room import extend_tails
 from boundary_policy import repair_gaps
 from layout_policy import recover_standard_layout,split_anchored,fit_simultaneous_dialogue
 from song_library import repair_short_exposures
 from display_repair import repair as repair_display
 out=copy.deepcopy(state);events=[];fps=float(Fraction(str(state.get('frameRate','24'))));rate=state.get('frameRate','24')
 def attempt(trial,entry):
  nonlocal out
  if technical_nonregression(out,trial):out=trial;events.append(entry);return True
  return False
 # Evaluate edits independently: one failed sound edit no longer discards unrelated improvements.
 for track in ('standard','sdh'):
  for old in list(out[track]):
   if old.get('checked') or old.get('kind') in {'song','sound'}:continue
   if old.get('timingReview')=='machine_word_matched' and old.get('timingEvidence') and old.get('wordAnchors'):continue
   anchors=unique_word_alignment(old,witness)
   if not anchors:continue
   a=round(anchors[0]['start']*fps)/fps;b=round(anchors[-1]['end']*fps)/fps
   if b<=a:continue
   new=copy.deepcopy(old);new.update(start=a,end=b,audioStart=anchors[0]['start'],audioEnd=anchors[-1]['end'],wordAnchors=anchors,timingReview='machine_word_matched',timingEvidence='Unique exact consecutive original-audio words from '+str(witness_path),checked=False)
   new['unresolved']=new.get('unresolved','').replace(TIMING_NOTE,'').strip();new.pop('reviewBinding',None)
   # Retain old review invalidation unless fresh wording proof applies to the exact words.
   fresh=new.get('wholeEpisodeAudioReview',{});v=fresh.get('verdict',{})
   if words(fresh.get('input_text',''))==words(new['text']) and v.get('uncertain',v.get('verdict')=='uncertain') is False and v.get('verdict')=='agree' and not new.get('unresolved') and not new.get('crossModalConflicts'):
    new.pop('reviewInvalidated',None);new['reviewBinding']=signature(new)
   trial=copy.deepcopy(out);trial[track]=[new if c['id']==old['id'] else c for c in out[track]]
   # Preserve useful existing tail where legal; then fill only measured permitted room.
   trial[track],tails=extend_tails(trial[track],cuts,rate,scope_end=out.get('scope',[0,660])[1]);trial[track],gaps=repair_gaps(trial[track],rate,cuts)
   attempt(trial,{'action':'independent_exact_word_alignment','track':track,'id':old['id'],'before':[old['start'],old['end']],'after':[new['start'],new['end']],'evidence':str(witness_path)})
 for track in ('standard','sdh'):
  trial=copy.deepcopy(out);trial[track],gaps=repair_gaps(trial[track],rate,cuts)
  if gaps:attempt(trial,{'action':'measured_two_frame_gaps','track':track,'changes':gaps})
  trial=copy.deepcopy(out);trial[track],tails=extend_tails(trial[track],cuts,rate,scope_end=out.get('scope',[0,660])[1]);changed=[e for e in tails if e['added_frames']>0]
  if changed:attempt(trial,{'action':'measured_tail_room','track':track,'changes':changed})
  trial=copy.deepcopy(out);trial[track],short=repair_short_exposures(trial[track],cuts,rate,scope_end=out.get('scope',[0,660])[1])
  if short:attempt(trial,{'action':'song_short_exposure','track':track,'changes':short})
 trial=copy.deepcopy(out);trial['standard'],merges=recover_standard_layout(trial['standard'],rate)
 if merges:attempt(trial,{'action':'recover_normal_from_legacy_sdh_splits','changes':merges})
 for track in ('standard','sdh'):
  trial=copy.deepcopy(out);trial[track],splits=split_anchored(trial[track],fps)
  if splits:attempt(trial,{'action':'word_anchored_long_cue_split','track':track,'changes':splits})
 trial=copy.deepcopy(out);trial['sdh'],splits=fit_simultaneous_dialogue(trial['sdh'],fps)
 if splits:attempt(trial,{'action':'shared_two_line_budget','changes':splits})
 trial=copy.deepcopy(out);trial['sdh'],display=repair_display(trial['sdh'],cuts,fps)
 if display:attempt(trial,{'action':'sound_display','changes':display})
 out,rebindings=rebind_measured_machine_evidence(out)
 if rebindings:events.append({'action':'rebind_measured_machine_evidence','changes':rebindings})
 out=prepare(out,preserve_checked=True);assert_fidelity(out)
 return out,events


def remove_corroborated_false_interjections(state,prior_path,current_path):
 """Honor compact first-pass nonlexical verdicts formerly skipped by schema code.

 Two distinct original-audio passes must explicitly identify the same animal
 vocalization. Names/onomatopoeia and actual narrator words stay untouched.
 """
 if not Path(prior_path).is_file() or not Path(current_path).is_file():return copy.deepcopy(state),[]
 a=Path(prior_path).read_bytes();b=Path(current_path).read_bytes()
 if hashlib.sha256(a).digest()==hashlib.sha256(b).digest():return copy.deepcopy(state),[]
 old={str(v.get('id')):v for v in json.loads(a).get('parsed',{}).get('cue_reviews',[])};new={str(v.get('id')):v for v in json.loads(b).get('parsed',{}).get('cue_reviews',[])}
 out=copy.deepcopy(state);events=[];removed=set();proposals=[]
 for c in state['standard']:
  v=new.get(str(c['id']),{});p=old.get(str(c['id']),{});tokens=words(c['text'])
  if c.get('checked') or c.get('kind') in {'song','sound'} or c.get('crossModalConflicts') or not tokens or set(tokens)-{'yeah','wow'}:continue
  if any(x.get('checked') for x in state['sdh'] if x['id']==c['id']):continue
  if p.get('verdict') not in {'remove','correct','nonlexical'} or p.get('uncertain') is True:continue
  if not re.search(r'non.?verbal|non.?lexical|cat squeak',p.get('reason',''),re.I):continue
  if v.get('verdict')!='nonlexical' or v.get('uncertain') is not False or v.get('confidence')!='high' or v.get('presentation')!='onscreen' or v.get('resolves_prior_disagreement') is not True:continue
  acoustic=v.get('audio_evidence') or v.get('specific_audio_evidence','')
  if len(acoustic)<30 or not re.search(r'squeak|chirp|vocalization|chewing',acoustic,re.I) or len(v.get('prior_reason_addressed',''))<20:continue
  removed.add(str(c['id']));events.append({'id':c['id'],'before':copy.deepcopy(c),'action':'remove_false_lexical_interjection','evidence':[str(prior_path),str(current_path)],'acoustic_reason':acoustic,'prior_verdict':p,'current_verdict':v})
  covered=any(x.get('kind')=='sound' and x['start']<c['end'] and c['start']<x['end'] for x in state['sdh'])
  # User explicitly excludes sub-0.8-second labels. Longer meaningful vocal
  # sounds remain an honest separate SDH task, never silently dropped.
  if not covered and c['end']-c['start']>=.8:
   proposals.append({'start':c['start'],'end':c['end'],'action':'missing_sound_review','source':'corroborated_nonlexical_recovery','caption':v.get('replacement_sound_caption') or '[squeaking]','audio_evidence':acoustic,'reason':'False English interjection removed after two audio passes; evaluate meaningful nonlexical SDH replacement against existing candidates.','evidence':[str(prior_path),str(current_path)]})
 if removed:
  affected={str(c.get('sourceGroup',c['id'])) for c in state['standard'] if str(c['id']) in removed}
  for track in ('standard','sdh'):
   out[track]=[c for c in out[track] if c.get('kind')=='sound' or str(c['id']) not in removed]
   for group in affected:
    rows=[c for c in out[track] if c.get('kind')!='sound' and str(c.get('sourceGroup',c['id']))==group]
    if rows:
     text=' '.join(c['text'].replace('♪','').strip() for c in sorted(rows,key=lambda c:c['start']));out['sourceManifest'][track][group]=text
     for c in rows:c.setdefault('originalSourceText',c.get('sourceText'));c['sourceText']=text
    else:out.get('sourceManifest',{}).get(track,{}).pop(group,None)
  out['latestReviewFindings']=[f for f in out.get('latestReviewFindings',[]) if str(f.get('id')) not in removed or f.get('action') in {'missing_sound_review','missing_speech_review'}]+proposals
  out['wholeEpisodeReviewPending']=[f for f in out.get('wholeEpisodeReviewPending',[]) if str(f.get('id')) not in removed]
  out.setdefault('corroboratedNonlexicalCorrections',[]).extend(events)
 assert_fidelity(out)
 return out,events


def constraint_diagnostics(state):
 """Explain remaining work without weakening any gate or claiming audible truth."""
 from collections import Counter
 from whole_episode_repair import acoustic_match
 q=report(state);triage=build(state,q);result={}
 for track in ('standard','sdh'):
  cues={str(c['id']):c for c in state[track]};items=triage['tracks'][track]['items'];second=[x for x in items if x['priority']==2];counts=Counter();fixed_wording_limits=[]
  for item in second:
   fs=set(item['flags'])
   if fs & {'timing_evidence_unresolved','song_timing_unresolved','evidence_outside_clip'}:counts['needs_timing_evidence']+=1
   if fs & {'cps_over_17','line_limit','simultaneous_line_limit','simultaneous_text_load','duration_short','duration_long','time_bounds','gap_under_2_frames','overlap','simultaneous_dialogue_overlap','export_event_short','composite_duration_long'}:counts['calculated_display_or_rate_violation']+=1
   c=cues[item['id']]
   if c.get('kind') not in {'song','sound'} and acoustic_match(c) and 'cps_over_17' in fs:
    # Generous upper bound: ignore next-cue and cut restrictions, giving the
    # unchanged text all the space available up to audioEnd+0.5 and 7 seconds.
    start=c['audioStart'];maximum=min(7,c['audioEnd']+.5-start)
    if maximum>0:
     lower=len(' '.join(c['text'].splitlines()))/maximum
     if lower>17+1e-6:fixed_wording_limits.append({'id':c['id'],'text':c['text'],'start':c['start'],'end':c['end'],'best_case_cps_unchanged_words':round(lower,2),'max_display_seconds':maximum,'reason':'Even ignoring next cues and cuts, measured phrase plus 0.5s tail exceeds 17 CPS. Splitting alone cannot reduce its aggregate character rate; do not delete words.'})
  result[track]={'priority_2_affected_cues':len(second),'diagnostic_counts_overlap':dict(counts),'unchanged_wording_rate_lower_bounds':fixed_wording_limits,'note':'Evidence gaps are not confirmed timing errors. Diagnostic groups overlap. A generous reading-rate bound is a constraint under unchanged words, not permission to remove words, hide captions or relax the gate.'}
 return result


def rebind_measured_machine_evidence(state):
 """Bind existing full-audio wording proof to independently measured final timing.

 This is a new machine-evidence binding, never transfer of human signoff. A
 permitted tail/gap repair must not create a permanent stale-review task.
 """
 from whole_episode_repair import acoustic_match
 out=copy.deepcopy(state);events=[];fps=float(Fraction(str(state.get('frameRate','24'))))
 for track in ('standard','sdh'):
  for c in out[track]:
   if c.get('kind') in {'sound','song'} or c.get('checked') or c.get('unresolved') or c.get('crossModalConflicts') or not acoustic_match(c):continue
   review=c.get('wholeEpisodeAudioReview',{});v=review.get('verdict',{});path=review.get('evidence')
   if not path or not Path(path).is_file() or words(review.get('input_text',''))!=words(c['text']):continue
   if v.get('verdict')!='agree' or v.get('uncertain',v.get('verdict')=='uncertain') is not False:continue
   if c.get('presentation') not in {None,'unknown',v.get('presentation')} and v.get('presentation'):continue
   if not all(isinstance(c.get(k),(int,float)) and math.isfinite(c[k]) for k in ('audioStart','audioEnd')):continue
   if not c['audioStart']-1/fps-1e-6<=c['start']<=c['audioStart']+3/fps+1e-6:continue
   if not c['audioEnd']-3/fps-1e-6<=c['end']<=c['audioEnd']+.5+1e-6:continue
   if c['end']-c['start']>7+1e-6:continue
   if c.get('reviewBinding')==signature(c) and not c.get('reviewInvalidated'):continue
   entry={'track':track,'id':c['id'],'wording_evidence':path,'word_timing_evidence':c['timingEvidence'],'before_binding':c.get('reviewBinding'),'new_binding':signature(c),'reason':'Unchanged audio-reviewed words, exact independent word anchors, final bounded onset and tail; new machine binding only','humanApproved':False}
   c.pop('reviewInvalidated',None);c['reviewBinding']=signature(c);c['measuredMachineReviewBinding']=entry;events.append(entry)
 out.setdefault('measuredEvidenceRebindings',[]).extend(events)
 return out,events


def _matches_preferred(text,state):
    tokens=words(text)
    values=state.get('projectSettings',{}).get('preferredSpellings',{}).values()
    for value in values:
        term=words(str(value))
        if term and any(tokens[i:i+len(term)]==term for i in range(len(tokens)-len(term)+1)):return True
    return False
