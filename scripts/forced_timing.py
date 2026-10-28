"""Align a fixed transcript to audio. Never recognizes/replaces transcript words."""
import argparse,hashlib,json,re,sys
from pathlib import Path
import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
from faster_whisper.tokenizer import Tokenizer
from faster_whisper.audio import pad_or_trim

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from timing_review import equivalence

def already_timed(c):
 anchors=c.get('wordAnchors',[])
 return (c.get('timingReview')=='machine_word_matched' and bool(c.get('timingEvidence')) and bool(anchors)
         and all(w.get('end',0)>w.get('start',0) for w in anchors)
         and [x['token'] for x in equivalence(anchors)]==[x['token'] for x in equivalence([{'word':c['text']}])])

def main():
 p=argparse.ArgumentParser();p.add_argument('--video',required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 s=json.loads(a.state.read_text());audio=decode_audio(a.video,sampling_rate=16000);model=WhisperModel('small.en',device='cpu',compute_type='int8',local_files_only=True)
 tokenizer=Tokenizer(model.hf_tokenizer,model.model.is_multilingual,task='transcribe',language='en');result={}
 if a.output.exists():result=json.loads(a.output.read_text())
 for c in s['standard']:
  if already_timed(c):continue
  text=re.sub(r'♪','',c['text']).replace('\n',' ').strip();off=max(0,c['start']-1);end=min(len(audio)/16000,c['end']+1)
  signature=hashlib.sha256(json.dumps([text,off,end,str(a.video),Path(a.video).stat().st_mtime_ns]).encode()).hexdigest()
  if result.get(c['id'],{}).get('signature')==signature:continue
  if end-off>29:continue
  wave=audio[int(off*16000):int(end*16000)];features=model.feature_extractor(wave);n=features.shape[-1]
  encoded=model.encode(pad_or_trim(features,3000));tokens=tokenizer.encode(' '+text)
  found=model.find_alignment(tokenizer,[tokens],encoded,n)[0]
  anchors=[{'word':w['word'],'start':float(w['start'])+off,'end':float(w['end'])+off,'probability':float(w['probability'])}for w in found]
  valid=bool(anchors) and all(w['end']>w['start'] and off<=w['start']<w['end']<=end+.04 for w in anchors)
  # Strong boundary evidence and average probability; do not accept forced text merely because it can be aligned.
  valid=valid and min(anchors[0]['probability'],anchors[-1]['probability'])>=.45 and sum(w['probability']for w in anchors)/len(anchors)>=.6
  result[c['id']]={'signature':signature,'text':text,'words':anchors,'accepted':valid,'role':'forced timing only; not independent recognition or content approval'}
  tmp=a.output.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2));tmp.replace(a.output)
  print(c['id'],valid,flush=True)
if __name__=='__main__':main()
