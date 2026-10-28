"""Independent audio + sampled-picture review; emits proposals, never human approvals."""
import argparse,hashlib,base64,concurrent.futures,csv,json,os,re,subprocess,urllib.request,urllib.error,zipfile,time,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'scripts'))
class ProviderRejected(RuntimeError):pass

def cache_valid(target,fingerprint,cue_ids=None,sound_ids=None):
 try:
  d=json.loads(target.read_text());parsed=d.get('parsed',{})
  if d.get('input_fingerprint')!=fingerprint or parsed.get('missing_sound_ids'):return False
  if any(x.get('decision') not in {'KEEP','REVISE','REMOVE'} or not isinstance(x.get('caption'),str) for x in parsed.get('sound_reviews',[])):return False
  if cue_ids is not None and cue_ids-{str(x['id']) for x in parsed.get('cue_reviews',[])}:return False
  if sound_ids is not None and sound_ids!={str(x['id']) for x in parsed.get('sound_reviews',[])}:return False
  return True
 except (OSError,ValueError,KeyError,TypeError):return False

def episode_picture_times(start,end,sounds,limit=200):
 """Choose episode-wide visual witnesses, prioritizing candidate-centered frames."""
 candidates=[(float(s['start'])+float(s['end']))/2 for s in sounds]
 anchors=[start+1]+[start+x for x in range(20,int(end-start),20)]+[end-.1]
 values=sorted(set(round(max(start,min(end-.1,t)),3) for t in candidates+anchors))
 if len(values)<=limit:return values
 # Preserve sound-candidate frames first; fill remaining slots uniformly.
 priority=sorted(set(round(max(start,min(end-.1,t)),3) for t in candidates))
 if len(priority)>=limit:
  return [priority[round(i*(len(priority)-1)/(limit-1))] for i in range(limit)]
 chosen=set(priority);remaining=limit-len(chosen)
 pool=[t for t in values if t not in chosen]
 if remaining>0 and pool:
  chosen.update(pool[round(i*(len(pool)-1)/max(1,remaining-1))] for i in range(remaining))
 return sorted(chosen)

def extract_picture(video,t,frame):
 subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',str(video),'-frames:v','1','-vf','scale=384:-2','-q:v','5','-y',str(frame)],check=True)
 if not frame.exists() or not frame.stat().st_size:raise ValueError(f'No picture extracted at {t:.3f}s')
 return frame

def archive_other_review_windows(output,episode_start):
 """Keep one current episode result from being mixed with stale chunk results."""
 target=f'review_{episode_start:04d}.json';archive=Path(output)/'incomplete'
 for path in (Path(output)).glob('review_????.json'):
  if path.name==target:continue
  archive.mkdir(exist_ok=True)
  path.replace(archive/(path.name+'_'+str(time.time_ns())))

def review_starts(scope_start,scope_end,granularity,only=None,skip=None):
 if only is not None:return [only]
 if granularity=='episode':return [int(scope_start)]
 return [t for t in range(int(scope_start),int(__import__('math').ceil(scope_end)),60) if t!=skip]
PROMPT='''Review the actual audio and sampled video pictures independently against the earlier screenplay and first-pass candidates. The screenplay is reference, never evidence that words were spoken. Pictures are sparse samples, not continuous video. All supplied timestamps and all returned timestamps must be ABSOLUTE video seconds; audio starts at audio_offset below. Do not compress, paraphrase, improve grammar, or remove first/then/together/repeated words for reading speed. Do not optimize CPS. Resolve duplicate/partial witnesses at chunk boundaries. Return complete natural utterances starting in ownership interval, preserving every audible lexical word. If unclear, retain the best heard text and explicitly mark uncertainty; never invent certainty. Distinguish nonverbal vocalizations from speech. For each first-pass cue, explain agreement or change with audible evidence and screenplay differences.
For EVERY sound candidate supplied, decide KEEP, REVISE or REMOVE as an editorial proposal. Include only meaningful audible narrative, emotional or comprehension information. Remove duplicate/continuous background music re-labels, routine visible action sounds, incidental Foley, and empty vague descriptions. Keep offscreen/story-significant sounds and meaningful human/character vocalizations. Do not infer a sound from pictures. Use concise familiar lowercase English in brackets, normally 1-5 words. Use visual_redundancy only if sampled pictures actually support it; otherwise say visual context insufficient. State audio evidence, picture evidence (or insufficient), and uncertainty. If you cannot resolve a candidate, KEEP as pending with confidence low and uncertainty. Never call your decisions human approved.
JSON only: {"speech":[{"start":0,"end":1,"text":"heard words","kind":"speech|song","source_cue_ids":[],"script_comparison":"agrees|final_audio_differs|not_in_script|uncertain","reason":"specific evidence","uncertain":false}],"cue_reviews":[{"id":"D0001","verdict":"agree|correct|duplicate|partial|uncertain","reason":"..."}],"sound_reviews":[{"id":"1","decision":"KEEP|REVISE|REMOVE","caption":"[concise description]","audio_evidence":"...","picture_evidence":"...","reason":"...","confidence":"high|medium|low","uncertain":false}],"unresolved":[]}. No wholesale screenplay copying. Preserve verbatim lyrics even when fast.'''

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audio_clip import extract_clip
from sdh_policy import prompt_rules
PROMPT += '\n'+prompt_rules()
PROMPT += '''
For every speech item also return presentation: onscreen|voiceover|device|song|unknown, and presentation_evidence. For every sound return narrative_value (specific information lost if omitted) and visual_redundancy (yes|no|insufficient). Include a separate missing_sounds array for meaningful audible events absent from supplied candidates, with absolute start/end, caption, audio_evidence, picture_evidence, narrative_value and uncertainty. Inspect the whole supplied audio, not only the candidate list. Explicitly inspect the first and last 15 seconds of every supplied window, plus any long interval without a caption; confirm whether it is genuinely silent/irrelevant or contains a meaningful closing/opening cue. Never assume that no candidate means no sound.'''

from evidence_gate import SOUND_PROMPT
PROMPT += "\n" + SOUND_PROMPT

AUDIT_PROMPT='''Listen to this COMPLETE episode and inspect the sampled pictures against the supplied current captions, screenplay and approved project references. Audio governs spoken words; the script is reference and pictures are sparse samples, not continuous vision. Review ALL supplied cue IDs and sound candidate IDs. For an unchanged caption do not retranscribe it in a second array: return its ID, verdict agree, and a short acoustic reason. For an actual word error return verdict correct and corrected_text with the complete original utterance. For a nonlexical animal call mislabelled as dialogue use verdict nonlexical and explain the audible source; never invent a catchphrase or delete the narrator's real words. Use verdict uncertain when genuinely unclear. Include presentation onscreen|voiceover|device|song|unknown and brief presentation_evidence for every cue. Preserve every real spoken word, repeat and interjection; do not paraphrase, polish grammar or optimize reading speed. Approved lyrics and canonical song line breaks remain protected; report apparent recording/version conflicts rather than silently changing masters. Every time must be ABSOLUTE video seconds, not time relative to the uploaded audio. Supplied subtitle times are reference, NOT independent acoustic evidence; do not echo them as verified exact timing. For every sound candidate decide KEEP|REVISE|REMOVE, with a short lowercase bracketed caption, audible evidence, picture evidence or insufficient, specific narrative_value, and uncertainty. Remove only when no important narrative/emotional/comprehension information is lost; do not delete just to reduce counts. Review beginning, ending and long caption-free gaps for missing meaningful sounds. Compact JSON only: {"speech":[],"cue_reviews":[{"id":"...","verdict":"agree|correct|nonlexical|uncertain","corrected_text":"only for correct","reason":"short acoustic reason","uncertain":false,"presentation":"voiceover","presentation_evidence":"short source evidence"}],"sound_reviews":[{"id":"1","decision":"KEEP|REVISE|REMOVE","caption":"[brief label]","audio_evidence":"short audible evidence","picture_evidence":"sample facts or insufficient","narrative_value":"information lost or why none","visual_redundancy":"yes|no|insufficient","reason":"short editorial reason","confidence":"high|medium|low","uncertain":false}],"missing_sounds":[],"unresolved":[]}. speech is intentionally empty because all existing dialogue is assessed by cue_reviews; add new missing speech only when actually audible, with absolute start/end and evidence.'''+SOUND_PROMPT
AUDIT_PROMPT+='''\nPrior review decisions and uncertainty are included as historical evidence. Reassess against the complete original audio, not model majority voting. For each cue or sound with a proposed change or previous doubt, return resolves_prior_disagreement=true ONLY when you can explicitly explain in prior_reason_addressed why the old reasoning is supported or rejected by audible/visual evidence. Otherwise keep uncertain=true. A new confident answer alone does not settle a conflict. State no human approval.'''
AUDIT_PROMPT+='''\nREQUIRED EXTRA FIELDS on EVERY cue_reviews and sound_reviews row: "resolves_prior_disagreement": false, "prior_reason_addressed": "". For a disputed item that can be settled from the complete original audio, set the first field true and give the specific acoustic/context reason supporting or rejecting the earlier interpretation in the second field. If it cannot be settled, use uncertain=true. Do not mark settled merely to complete the schema.'''

def main():
 p=argparse.ArgumentParser();p.add_argument('--video',type=Path,required=True);p.add_argument('--episode',type=Path,required=True);p.add_argument('--script-text',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--key-zip',type=Path);p.add_argument('--workers',type=int,default=2);p.add_argument('--granularity',choices=['episode','60s'],default='episode',help='Review each episode in one model request; use 60s only as a fallback.');p.add_argument('--dry-run',action='store_true',help='Build and measure the exact request but do not contact Qwen.');p.add_argument('--only',type=int);p.add_argument('--skip',type=int)
 p.add_argument('--audit-only',action='store_true',help='Full-episode listening with per-ID decisions and corrections only; avoid duplicate full retranscription.')
 # Parse the added production audit mode without changing existing callers.
 a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 a.audit_only=a.audit_only or (a.episode/'whole_episode_audit.mode').exists()
 prompt=AUDIT_PROMPT if a.audit_only else PROMPT
 key=os.environ.get('QWEN_API_KEY') or os.environ.get('DASHSCOPE_API_KEY')
 if not key and (ROOT/'config/team_api_key').exists():key=(ROOT/'config/team_api_key').read_text().strip()
 if not key and a.key_zip:
  with zipfile.ZipFile(a.key_zip)as z:key=z.read(next(n for n in z.namelist() if n.endswith('/config/team_api_key'))).decode().strip()
 if not key and not a.dry_run:raise SystemExit('Qwen key unavailable')
 state=json.loads((a.episode/'workbench_state.json').read_text());sounds=list(csv.DictReader((a.episode/'SDH_Sound_Candidates.csv').open(encoding='utf-8-sig')))
 duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(a.video)]))
 script=a.script_text.read_text()
 names=next((p for p in (a.episode/'character_lookup.md',a.episode.parent/'character_lookup.md') if p.exists()),a.episode/'character_lookup.md')
 from character_lookup import hints
 name_reference=hints(names) if names.exists() else ''
 scope_start,scope_end=state.get('scope',[0,duration]);scope_end=min(scope_end,duration)
 fingerprint=hashlib.sha256(json.dumps({'review_window_version':3,'granularity':a.granularity,'video':str(a.video.resolve()),'size':a.video.stat().st_size,'mtime':a.video.stat().st_mtime_ns,'state':state,'sounds':sounds,'script':script,'character_reference':name_reference,'prompt':prompt,'confirmed_events':(a.episode/'confirmed_events.json').read_text() if (a.episode/'confirmed_events.json').exists() else ''},sort_keys=True).encode()).hexdigest()
 halted=threading.Event()
 def run(start):
  target=a.output/f'review_{start:04d}.json'
  if halted.is_set():return str(start)+' deferred: provider access must be restored'
  end=scope_end if a.granularity=='episode' else min(start+60,scope_end)
  from review_window import complete_window
  off,stop,cues=complete_window(state['standard'],start,end,duration)
  candidates=[dict(id=str(i),**s)for i,s in enumerate(sounds,1)if start<=float(s['start'])<end]
  if cache_valid(target,fingerprint,{str(c['id']) for c in cues},{s['id'] for s in candidates}):return str(start)+' cached'
  if target.exists():
   archive=a.output/'incomplete';archive.mkdir(exist_ok=True);(archive/(target.stem+'_'+str(time.time_ns())+'.json')).write_bytes(target.read_bytes())
  preparation_started=time.monotonic()
  audio=a.output/f'audio_{start:04d}.mp3';extract_clip(a.video,off,stop,audio)
  audio_b64=base64.b64encode(audio.read_bytes()).decode()
  if len(audio_b64.encode())>=10*1024*1024:raise ValueError('Encoded episode audio exceeds Qwen Base64 input limit; use the 60s fallback for this episode')
  content=[{'type':'input_audio','input_audio':{'data':'data:audio/mpeg;base64,'+audio_b64,'format':'mp3'}}]
  if a.granularity=='episode':times=episode_picture_times(start,end,candidates)
  else:
   times=sorted(set([min(end-.1,start+x)for x in [1,12,24,36,48,59]]+[(float(s['start'])+float(s['end']))/2 for s in candidates]))
   if len(times)>12:times=[times[round(i*(len(times)-1)/11)]for i in range(12)]
  # Candidate-centred frames provide evidence without claiming continuous vision.
  def make_frame(item):
   j,t=item;frame=a.output/f'frame_{start:04d}_{j:02d}.jpg';extract_picture(a.video,t,frame)
   if frame.stat().st_size>=10*1024*1024:raise ValueError(f'Encoded picture exceeds Qwen Base64 input limit at {t:.3f}s')
   return j,t,base64.b64encode(frame.read_bytes()).decode()
  with concurrent.futures.ThreadPoolExecutor(max_workers=8)as frame_pool:
   frame_data=sorted(frame_pool.map(make_frame,enumerate(times)))
  for j,t,image_data in frame_data:
   content.extend([{'type':'text','text':f'Picture at absolute video {t:.3f} seconds.'},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+image_data}}])
  context={'audio_offset':off,'ownership_interval':[start,end],'audio_end':stop,'first_pass_cues':[{k:c[k] for k in ('id','start','end','text','kind','songMaster') if k in c}for c in cues],'sound_candidates':candidates,'earlier_script_reference':script,'confirmed_events':json.loads((a.episode/'confirmed_events.json').read_text()) if (a.episode/'confirmed_events.json').exists() else []}
  context['current_sound_displays']=[{k:c[k] for k in ('id','sourceSoundId','start','end','text','soundAudioStart','soundAudioEnd') if k in c} for c in state.get('sdh',[]) if c.get('kind')=='sound']
  context['prior_cue_uncertainty']=[{k:c[k] for k in ('id','unresolved','reviewReason','presentation','presentationEvidence','crossModalConflicts') if k in c} for c in cues if c.get('unresolved') or c.get('crossModalConflicts')]
  context['prior_sound_decisions']=[{'id':c.get('sourceSoundId'),'caption':c['text'],**{k:c.get('sourceDecision',{}).get(k) for k in ('status','note','audioEvidence','pictureEvidence','narrativeValue','uncertain')}} for c in state.get('sdh',[]) if c.get('kind')=='sound']
  context['prior_sound_disagreements']=state.get('soundEvidenceRecheckTasks',[])
  context['approved_song_reference']=state.get('songLibrary',{})
  context['character_spelling_reference']=name_reference
  if target.exists():context['schema_retry_instruction']='Previous response is incomplete or invalid. Every sound_reviews item must include decision KEEP/REVISE/REMOVE and caption. Do not use cue-review verdict agree/correct in place of a sound decision. Review all candidate IDs.'
  content.append({'type':'text','text':prompt+'\n'+json.dumps(context,ensure_ascii=False)})
  payload={'model':__import__('provider_config').model(),'reasoning_effort':'medium','modalities':['text'],'stream':True,'messages':[{'role':'user','content':content}]}
  request_body=json.dumps(payload,ensure_ascii=False).encode()
  request_bytes=len(request_body)
  metrics={'granularity':a.granularity,'review_mode':'audit' if a.audit_only else 'retranscribe','request_count':1,'request_bytes':request_bytes,'audio_bytes':audio.stat().st_size,'image_count':len(times),'local_prepare_seconds':round(time.monotonic()-preparation_started,3)}
  if a.dry_run:
   preflight={'interval':[start,end],'audio_offset':off,'picture_times':times,'request_metrics':metrics,'input_fingerprint':fingerprint,'provider_request_sent':False}
   (a.output/f'preflight_{start:04d}.json').write_text(json.dumps(preflight,ensure_ascii=False,indent=2))
   return f'{start}: preflight only / {len(times)} frames / {request_bytes} request bytes'
  request_started=time.monotonic()
  req=urllib.request.Request(__import__('provider_config').base_url().rstrip('/')+'/chat/completions',data=request_body,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
  for attempt in range(3):
   if halted.is_set():return str(start)+' deferred: provider access must be restored'
   try:
    pieces=[];usage=None;finished=False
    with urllib.request.urlopen(req,timeout=900 if a.granularity=='episode' else 300)as response:
     with target.with_suffix('.stream.jsonl').open('w')as streamlog:
      for line in response:
       if not line.startswith(b'data:'):continue
       data=line[5:].strip()
       if data==b'[DONE]':finished=True;break
       item=json.loads(data);streamlog.write(json.dumps(item,ensure_ascii=False)+'\n');streamlog.flush()
       if item.get('usage'):usage=item['usage']
       for choice in item.get('choices',[]):
        piece=choice.get('delta',{}).get('content')
        if piece:pieces.append(piece)
        if choice.get('finish_reason')=='stop':finished=True
    if not finished:raise OSError('Incomplete streamed response')
    res={'choices':[{'message':{'content':''.join(pieces)}}],'usage':usage}
    break
   except (OSError,ValueError) as exc:
    if isinstance(exc,urllib.error.HTTPError) and exc.code in {400,401,403}:
     try: detail=json.loads(exc.read()).get('error',{});message=str(detail.get('code',''))+': '+str(detail.get('message',''))
     except Exception:message='Provider rejected request'
     halted.set()
     raise ProviderRejected(f'Provider HTTP {exc.code}: {message[:400]}') from None
    if attempt==2:raise
    print(f'{start}: transient {type(exc).__name__}; retry {attempt+1}',flush=True);time.sleep(2)
  raw=res['choices'][0]['message']['content'];target.with_suffix('.raw.json').write_text(json.dumps({'response':res,'interval':[start,end]},ensure_ascii=False,indent=2));normalized=re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip());normalized=re.sub(r'("confidence"\s*:\s*)(high|medium|low)(\s*[,}])',r'\1"\2"\3',normalized);parsed=__import__('provider_json').parse_object(raw)
  expected={s['id']for s in candidates};got={str(s['id'])for s in parsed['sound_reviews']}
  parsed['missing_sound_ids']=sorted(expected-got)
  for c in parsed['speech']:
   if not off<=float(c['start'])<float(c['end'])<=stop+.2:c['invalid_timing']=True
  metrics['provider_elapsed_seconds']=round(time.monotonic()-request_started,3)
  result={'input_fingerprint':fingerprint,'interval':[start,end],'audio_offset':off,'picture_times':times,'request_metrics':metrics,'prompt':prompt,'parsed':parsed,'usage':res.get('usage'),'reviewer':'model_audio_picture_script_second_pass','human_approved':False}
  tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2));tmp.replace(target)
  (a.output/f'error_{start:04d}.json').unlink(missing_ok=True)
  return f'{start}: {len(parsed["speech"])} speech / {len(got)} sounds reviewed / {len(times)} frames / provider {metrics["provider_elapsed_seconds"]:.1f}s'
 starts=review_starts(scope_start,scope_end,a.granularity,a.only,a.skip)
 if a.granularity=='episode' and a.only is None:archive_other_review_windows(a.output,starts[0])
 def safe_run(t):
  try:return run(t)
  except Exception as exc:
   error={'segment':t,'type':type(exc).__name__,'message':str(exc)[:500]};(a.output/f'error_{t:04d}.json').write_text(json.dumps(error));return json.dumps(error)
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers)as pool:
  for result in pool.map(safe_run,starts):print(result,flush=True)
 if not a.dry_run and any(not cache_valid(a.output/f'review_{t:04d}.json',fingerprint) for t in starts):raise SystemExit('Incomplete independent review; retry resumes successful segments')
if __name__=='__main__':main()
