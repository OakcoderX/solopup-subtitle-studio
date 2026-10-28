"""Audio-grounded dialogue + SDH first pass, with compact screenplay names prepared first."""
import argparse,hashlib,base64,concurrent.futures,json,math,os,re,subprocess,urllib.request,zipfile
from pathlib import Path
from character_lookup import extract,hints
from qwen_client import call_json
from audio_clip import extract_clip
ROOT=Path(__file__).resolve().parents[1]
PROMPT='''Transcribe ALL intelligible English speech and song lyrics verbatim from this audio. Preserve small words, repetitions, names, quantities, first/then/together, contractions and negatives. Do not compress, paraphrase, correct grammar, or infer dialogue from context. Split into short natural utterances; give onset/end in seconds RELATIVE TO THIS CLIP. Include non-speech vocalizations as sounds rather than invented words. Also identify important audible non-speech events. You only receive AUDIO, so do not claim visual redundancy or identify a visible speaker. Sound candidates need later video context review. Return JSON only: {"speech_segments":[{"start":0,"end":1,"text":"...","kind":"speech|song"}],"sound_events":[{"start":0,"end":1,"description":"[short lowercase description]","confidence":"high|medium|low"}],"uncertain_speech":[{"start":0,"end":1,"heard":"...","alternatives":[],"reason":"..."}]}. Use exact heard text, even if it differs from expected words. Do not add a character name unless spoken. Timings must be measured in this clip, not guessed from story.''' 

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sdh_policy import prompt_rules
PROMPT += '\n'+prompt_rules()

def validate_response(parsed,length):
 if not isinstance(parsed,dict):raise ValueError('Expected transcript object')
 if not {'speech_segments','sound_events'}<=parsed.keys():raise ValueError('Missing required speech/sound arrays')
 for group,textkey in [('speech_segments','text'),('sound_events','description'),('uncertain_speech','heard')]:
  rows=parsed.get(group,[])
  if not isinstance(rows,list):raise ValueError('Expected array: '+group)
  for c in rows:
   if not isinstance(c,dict) or not isinstance(c.get(textkey),str):raise ValueError('Invalid '+group+' object')
   try:a,b=float(c['start']),float(c['end'])
   except (KeyError,TypeError,ValueError):raise ValueError('Missing numeric clip times in '+group)
   if not all(math.isfinite(t) for t in (a,b)) or not 0<=a<b<=length:raise ValueError('Out-of-clip timing in '+group)
 return parsed

def main():
 p=argparse.ArgumentParser();p.add_argument('video',type=Path);p.add_argument('output',type=Path);p.add_argument('--script',type=Path);p.add_argument('--song-matches',type=Path);p.add_argument('--names',type=Path);p.add_argument('--key-zip',type=Path);p.add_argument('--start',type=float,default=0);p.add_argument('--end',type=float);p.add_argument('--chunk',type=float,default=30);p.add_argument('--workers',type=int,default=2);a=p.parse_args()
 if a.chunk<=2:raise SystemExit('Chunk must exceed overlap (2 seconds)')
 a.output.mkdir(parents=True,exist_ok=True);names=a.names or a.output/'character_lookup.md'
 if a.script:extract(a.script,names)
 locked=json.loads(a.song_matches.read_text()).get('matches',[]) if a.song_matches else []
 prompt=PROMPT+('\n'+hints(names) if names.exists() else '')
 key=os.environ.get('QWEN_API_KEY') or os.environ.get('DASHSCOPE_API_KEY')
 if not key and (ROOT/'config/team_api_key').is_file():key=(ROOT/'config/team_api_key').read_text().strip()
 if not key and a.key_zip:
  with zipfile.ZipFile(a.key_zip) as z:key=z.read(next(n for n in z.namelist() if n.endswith('/config/team_api_key'))).decode().strip()
 if not key:raise SystemExit('API key not configured')
 duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(a.video)]));end=min(a.end or duration,duration)
 fingerprint=hashlib.sha256(json.dumps([str(a.video.resolve()),a.video.stat().st_size,a.video.stat().st_mtime_ns,a.start,end,a.chunk,prompt,locked]).encode()).hexdigest()
 starts=[];t=a.start
 while t<end:starts.append(t);t+=a.chunk-2
 def run(t):
  out=a.output/f'qwen_{t:07.2f}.json'
  if out.exists():
   cached=json.loads(out.read_text())
   if cached.get('input_fingerprint')==fingerprint:
    try:validate_response(cached['parsed'],min(t+a.chunk,end)-t);return str(out.name)+' cached'
    except (ValueError,KeyError):pass
  stop=min(t+a.chunk,end);audio=a.output/f'audio_{t:07.2f}.mp3'
  extraction_error=a.output/f'audio_extraction_error_{t:07.2f}.json'
  try:extract_clip(a.video,t,stop,audio)
  except (OSError,ValueError,subprocess.SubprocessError) as exc:
   extraction_error.write_text(json.dumps({'stage':'audio_extraction','start':t,'end':stop,
       'input_fingerprint':fingerprint,'error':str(exc),'decoder_log':str(audio.with_suffix('.decode.log'))},ensure_ascii=False,indent=2))
   raise
  extraction_error.unlink(missing_ok=True)
  clip_prompt=prompt
  spans=[{'start':max(0,m['start']-t),'end':min(stop-t,m['end']-t),'master':m['master_id']} for m in locked if m['start']<stop and m['end']>t]
  if spans:clip_prompt+='\nThese spans are identified identical fixed recordings with versioned captions. Do not retranscribe their vocals or invent replacement words. Continue reviewing important non-speech sounds and audio outside these spans. Relative spans: '+json.dumps(spans)
  payload={'model':__import__('provider_config').model(),'modalities':['text'],'stream':False,'messages':[{'role':'user','content':[{'type':'input_audio','input_audio':{'data':'data:audio/mpeg;base64,'+base64.b64encode(audio.read_bytes()).decode(),'format':'mp3'}},{'type':'text','text':clip_prompt}]}]}
  url=__import__('provider_config').base_url().rstrip('/')+'/chat/completions'
  for attempt in range(3):
   parsed,usage,raw=call_json(url,key,payload)
   try:validate_response(parsed,stop-t);break
   except ValueError as exc:
    rejected_folder=a.output/'rejected';rejected_folder.mkdir(exist_ok=True)
    rejected=rejected_folder/(out.stem+f'.rejected_{attempt}.json')
    rejected.write_text(json.dumps({'raw':raw,'parsed':parsed,'error':str(exc),'input_fingerprint':fingerprint,'clip_length':stop-t,'usage':usage},ensure_ascii=False,indent=2))
    if attempt==2:raise ValueError(f'Invalid provider transcript {out.name}: {exc}')
    payload['messages'].append({'role':'user','content':f'Previous output failed validation: {exc}. Re-listen to the same supplied audio. Every event must have numeric start/end within 0 to {stop-t:.6f} seconds and the required text/description/heard field. Do not clamp or fabricate a time. Do not place an event beyond the clip. Return only the complete corrected JSON.'})
  tmp=out.with_suffix('.json.tmp');tmp.write_text(json.dumps({'input_fingerprint':fingerprint,'offset_seconds':t,'end_seconds':stop,'parsed':parsed,'usage':usage,'prompt':clip_prompt,'status':'machine_evidence_not_final'},ensure_ascii=False,indent=2));tmp.replace(out);return out.name+' saved'
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
  for result in pool.map(run,starts):print(result,flush=True)
if __name__=='__main__':main()
