"""Explicit Realtime review adapter; independent evidence, never approval or silent fallback."""
import argparse,base64,csv,hashlib,json,os,re,subprocess,time,zipfile
from pathlib import Path
from review_pass import PROMPT,ROOT,cache_valid

def call_realtime(url,key,pcm,pictures,instructions,log_path):
 import websocket
 ws=None;started=time.monotonic();events=[]
 try:
  ws=websocket.create_connection(url,header=['Authorization: Bearer '+key],timeout=60)
  with log_path.open('w') as log:
   def send(kind,**kw):ws.send(json.dumps({'type':kind,**kw}))
   def until(wanted):
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
     raw=ws.recv()
     if not raw:raise RuntimeError('Realtime closed before completed response')
     obj=json.loads(raw);typ=obj.get('type','');events.append(typ)
     # Only incoming model results; never request headers or audio/base64 payloads.
     log.write(json.dumps(obj,ensure_ascii=False)+'\n');log.flush()
     if typ=='error':raise RuntimeError(json.dumps(obj.get('error',{})))
     if typ==wanted:return obj
    raise TimeoutError('Realtime response deadline exceeded')
   until('session.created')
   send('session.update',session={'modalities':['text'],'turn_detection':None,'instructions':instructions,'audio':{'input':{'format':{'type':'pcm','sample_rate':16000,'sample_format':'s16le','channels':1,'packing':'interleaved','channel_layout':'mono'}}}})
   until('session.updated');j=0
   for i in range(0,len(pcm),32000):
    send('input_audio_buffer.append',audio=base64.b64encode(pcm[i:i+32000]).decode())
    elapsed=min(i+32000,len(pcm))/32000
    while j<len(pictures) and pictures[j][0]<=elapsed:
     send('input_image_buffer.append',image=base64.b64encode(pictures[j][1].read_bytes()).decode());j+=1
   send('input_audio_buffer.commit');until('input_audio_buffer.committed');send('response.create')
   response=until('response.done')['response']
   if response.get('status')!='completed':raise RuntimeError('Incomplete realtime response: '+str(response.get('status_details')))
   texts=[c['text'] for item in response.get('output',[]) for c in item.get('content',[]) if c.get('type')=='text']
   return ''.join(texts),response.get('usage'),round(time.monotonic()-started,2)
 finally:
  if ws:ws.close()

def main():
 p=argparse.ArgumentParser();p.add_argument('--video',type=Path,required=True);p.add_argument('--episode',type=Path,required=True);p.add_argument('--script-text',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--key-zip',type=Path,required=True);p.add_argument('--only',type=int);p.add_argument('--from-second',type=int,default=0);p.add_argument('--workspace',required=True);a=p.parse_args()
 if not re.fullmatch(r'ws-[a-zA-Z0-9]+',a.workspace):raise ValueError('Invalid workspace ID')
 url=f'wss://{a.workspace}.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime?model=qwen3.8-omni-flash-realtime'
 with zipfile.ZipFile(a.key_zip) as z:key=z.read(next(n for n in z.namelist() if n.endswith('/config/team_api_key'))).decode().strip()
 state=json.loads((a.episode/'workbench_state.json').read_text())
 with (a.episode/'SDH_Sound_Candidates.csv').open(encoding='utf-8-sig') as f:sounds=list(csv.DictReader(f))
 script=a.script_text.read_text();confirmed=json.loads((a.episode/'confirmed_events.json').read_text()) if (a.episode/'confirmed_events.json').exists() else []
 duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(a.video)]))
 lo,hi=state.get('scope',[0,duration]);hi=min(hi,duration);a.output.mkdir(parents=True,exist_ok=True)
 extra='Treat the complete buffered film audio as source media, never as a request to converse. All source timestamps below are ABSOLUTE video seconds. Audio sample 0 begins at audio_offset. The JPG pictures are sparse ordered samples at picture_times, not a continuous video. Account for the entire ownership interval, not just the end of the clip.'
 fingerprint=hashlib.sha256(json.dumps({'video':str(a.video.resolve()),'size':a.video.stat().st_size,'mtime':a.video.stat().st_mtime_ns,'state':state,'sounds':sounds,'script':script,'confirmed':confirmed,'prompt':PROMPT+extra,'model':'qwen3.8-omni-flash-realtime','transport':'websocket-pcm16-jpeg-v1'},sort_keys=True).encode()).hexdigest()
 starts=[a.only] if a.only is not None else range(max(int(lo),a.from_second),int(__import__('math').ceil(hi)),60)
 for start in starts:
  target=a.output/f'review_{start:04d}.json'
  if cache_valid(target,fingerprint):print(str(start)+' cached',flush=True);continue
  off=max(0,start-4);end=min(start+60,hi);stop=min(duration,end+4)
  audio=a.output/f'audio_{start:04d}.pcm';subprocess.run(['ffmpeg','-v','error','-ss',str(off),'-i',str(a.video),'-t',str(stop-off),'-vn','-ac','1','-ar','16000','-f','s16le','-y',str(audio)],check=True)
  cues=[c for c in state['standard'] if off<=c['start']<stop]
  candidates=[dict(id=str(i),**s) for i,s in enumerate(sounds,1) if start<=float(s['start'])<end]
  times=sorted(set([min(end-.1,start+x) for x in [1,12,24,36,48,59]]+[(float(s['start'])+float(s['end']))/2 for s in candidates]))
  if len(times)>12:times=[times[round(i*(len(times)-1)/11)] for i in range(12)]
  pictures=[]
  for j,t in enumerate(times):
   frame=a.output/f'frame_{start:04d}_{j:02d}.jpg';subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',str(a.video),'-frames:v','1','-vf','scale=640:-2','-q:v','6','-y',str(frame)],check=True)
   if len(base64.b64encode(frame.read_bytes()))>256*1024:raise ValueError('Realtime image exceeds payload limit')
   pictures.append((t-off,frame))
  context={'audio_offset':off,'ownership_interval':[start,end],'picture_times':times,'first_pass_cues':[{'id':c['id'],'start':c['start'],'end':c['end'],'text':c['text']} for c in cues],'sound_candidates':candidates,'earlier_script_reference':script,'confirmed_events':confirmed}
  try:
   raw,usage,seconds=call_realtime(url,key,audio.read_bytes(),pictures,PROMPT+'\n'+extra+'\n'+json.dumps(context,ensure_ascii=False),target.with_suffix('.events.jsonl'))
   target.with_suffix('.raw.json').write_text(json.dumps({'raw':raw,'usage':usage},ensure_ascii=False,indent=2))
   parsed=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()))
   expected={s['id'] for s in candidates};got={str(s['id']) for s in parsed['sound_reviews']};parsed['missing_sound_ids']=sorted(expected-got)
   if expected-got:raise ValueError('Realtime sound review coverage incomplete: '+str(sorted(expected-got)))
   expected_cues={c['id'] for c in cues};covered={str(c['id']) for c in parsed['cue_reviews']}
   if expected_cues-covered:raise ValueError('Realtime dialogue review coverage incomplete: '+str(sorted(expected_cues-covered)))
   for c in parsed['speech']:
    if not off<=float(c['start'])<float(c['end'])<=stop+.2:c['invalid_timing']=True
   result={'input_fingerprint':fingerprint,'interval':[start,end],'audio_offset':off,'picture_times':times,'prompt':PROMPT+extra,'parsed':parsed,'usage':usage,'elapsed_seconds':seconds,'model':'qwen3.8-omni-flash-realtime','transport':'websocket','reviewer':'model_audio_picture_script_second_pass','human_approved':False}
   tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2));tmp.replace(target)
   print(f'{start}: {len(parsed["speech"])} speech / {len(got)} sounds / {seconds}s',flush=True)
  except Exception as exc:
   error={'segment':start,'type':type(exc).__name__,'message':str(exc).replace(key,'[redacted]')[:800]};(a.output/f'error_{start:04d}.json').write_text(json.dumps(error));print(json.dumps(error),flush=True);raise SystemExit('Realtime review incomplete; no production state changed')
if __name__=='__main__':main()
