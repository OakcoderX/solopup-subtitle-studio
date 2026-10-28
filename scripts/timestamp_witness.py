"""Optional independent local word-time witness; never substitutes subtitle words."""
import argparse,json
from pathlib import Path
from faster_whisper import WhisperModel
p=argparse.ArgumentParser();p.add_argument('--video',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--start',type=float,default=0);p.add_argument('--end',type=float,required=True);a=p.parse_args()
model=WhisperModel('small.en',device='cpu',compute_type='int8',local_files_only=True)
segments,info=model.transcribe(a.video,language='en',beam_size=5,word_timestamps=True,clip_timestamps=f'{a.start},{a.end}',vad_filter=True)
rows=[]
for s in segments:
 rows.append({'start':s.start,'end':s.end,'text':s.text,'words':[{'start':w.start,'end':w.end,'word':w.word,'probability':w.probability} for w in s.words or []]})
a.output.write_text(json.dumps({'model':'faster-whisper small.en','role':'independent timing witness only','scope':[a.start,a.end],'segments':rows},ensure_ascii=False,indent=2))
