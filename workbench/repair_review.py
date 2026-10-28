"""Localized independent audio adjudication. Cached proposals, never approval."""
import copy,math,argparse,base64,concurrent.futures,hashlib,json,os,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from qwen_client import call_json
from audio_clip import extract_clip
PROMPT = 'Listen closely to the supplied original audio. Return exactly one verdict for every cue ID: KEEP, CORRECT with the complete exact heard words, or REMOVE only for an evidenced duplicate or absence of intelligible speech. Do not infer a speaker is nonverbal from appearance. Scripts, names and lyrics are fallible references. Never delete repetitions, paraphrase, invent words or optimize CPS. Check names, quantities, negation, short words and lyrics. Unresolved disagreement stays uncertain and retains the best-supported original text. Return JSON {"verdicts":[{"id":"...","action":"KEEP|CORRECT|REMOVE","text":"...","start":0,"end":1,"uncertain":false,"reason":"specific audio evidence"}]}. Times are relative to the supplied clip. Machine evidence is not human approval.'
from evidence_gate import SOUND_PROMPT
PROMPT += "\n" + SOUND_PROMPT
from sdh_policy import prompt_rules
PROMPT += '\n'+prompt_rules()

def main():
 p=argparse.ArgumentParser();p.add_argument('--episode',type=Path,required=True);p.add_argument('--video',type=Path,required=True);p.add_argument('--key-zip',type=Path);p.add_argument('--state',type=Path);a=p.parse_args()
 state=json.loads((a.state or a.episode/'workbench_state.json').read_text());duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(a.video)]));out=a.episode/'repair_review';out.mkdir(exist_ok=True)
 key=os.environ.get('QWEN_API_KEY') or os.environ.get('DASHSCOPE_API_KEY')
 if not key and (ROOT/'config/team_api_key').exists():key=(ROOT/'config/team_api_key').read_text().strip()
 if not key and a.key_zip:
  with zipfile.ZipFile(a.key_zip) as z:key=z.read(next(n for n in z.namelist() if n.endswith('/config/team_api_key'))).decode().strip()
 if not key:raise ValueError('No provider credential configured')
 names=(a.episode/'character_lookup.md').read_text() if (a.episode/'character_lookup.md').exists() else ''; songs=(a.episode/'song_lookup.md').read_text() if (a.episode/'song_lookup.md').exists() else ''
 def run(start):
  rows=copy.deepcopy([c for c in state['standard'] if start<=c['start']<start+30])
  if not rows:return
  off=max(0,start-3);end=min(duration,max(start+33,max(c['end'] for c in rows)+2));f=out/f'repair_{start:04d}.json'
  # Keep the review payload lexical: word anchors, prior ledgers and UI state are not new audio evidence.
  compact=[{k:c[k] for k in ('id','text','start','end','kind','unresolved') if k in c} for c in rows]
  context={'cues':compact,'spelling_reference':names,'lyrics_reference_not_ground_truth':songs if any(c.get('kind')=='song' for c in rows) else ''}
  stamp=hashlib.sha256(json.dumps([PROMPT,context,str(a.video),a.video.stat().st_mtime_ns]).encode()).hexdigest()
  if f.exists() and json.loads(f.read_text()).get('fingerprint')==stamp:return
  clip=out/f'audio_{start:04d}.mp3';extract_clip(a.video,off,end,clip)
  for c in context['cues']:c['start']-=off;c['end']-=off
  payload={'model':__import__('provider_config').model(),'reasoning_effort':'medium','modalities':['text'],'messages':[{'role':'user','content':[{'type':'input_audio','input_audio':{'data':'data:audio/mpeg;base64,'+base64.b64encode(clip.read_bytes()).decode(),'format':'mp3'}},{'type':'text','text':PROMPT+'\n'+json.dumps(context,ensure_ascii=False)}]}]}
  parsed,usage,raw=call_json(__import__('provider_config').base_url().rstrip('/')+'/chat/completions',key,payload)
  proposals=out/'proposals';proposals.mkdir(exist_ok=True)
  (proposals/f.name).write_text(json.dumps({'fingerprint':stamp,'offset':off,'parsed':parsed,'raw':raw,'usage':usage},ensure_ascii=False,indent=2))
  got=[v['id'] for v in parsed['verdicts']]
  if len(got)!=len(set(got)) or set(got)!={c['id']for c in rows}:raise ValueError('Incomplete adjudication coverage')
  for v in parsed['verdicts']:
   if v['action'] not in {'KEEP','CORRECT','REMOVE'}:raise ValueError('Invalid verdict')
   if v['action']!='REMOVE' and not 0<=v['start']<v['end']<=end-off+.2:
    v['uncertain']=True;v['reason']='Invalid clip-relative timing; original text retained for further review. '+v.get('reason','')
  f.write_text(json.dumps({'fingerprint':stamp,'offset':off,'parsed':parsed,'raw':raw,'usage':usage,'human_approved':False},ensure_ascii=False,indent=2));print(f.name,flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:list(pool.map(run,range(int(state.get('scope',[0,duration])[0]//30)*30,math.ceil(state.get('scope',[0,duration])[1]),30)))
if __name__=='__main__':main()
