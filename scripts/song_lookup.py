"""Reference-only song concordance. Never mutate transcript or infer approval."""
import re
from difflib import SequenceMatcher

def tokens(text):
    return re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower().replace('’', "'"))

def read(path):
    entries=[]
    for line in path.read_text().splitlines():
        cells=[s.strip() for s in line.strip('|').split('|')]
        if len(cells)==3 and re.fullmatch(r'[A-Z0-9_]+_v\d+\.\d+',cells[0]):
            entries.append(dict(id=cells[0],text=cells[1],reference_status=cells[2]))
    return entries

def match(rows,path):
    entries=read(path);matches=[]
    # All matching windows consist solely of consecutive song cues, never dialogue.
    windows=[]
    for i,row in enumerate(rows):
        if row.get('kind')!='song' and '♪' not in row.get('text',''):continue
        for n in range(1,4):
            part=rows[i:i+n]
            if len(part)!=n or any(c.get('kind')!='song' and '♪' not in c.get('text','') for c in part):break
            if any(b['start']-a['end']>2 for a,b in zip(part,part[1:])):break
            windows.append((part,' '.join(c['text'] for c in part)))
    for entry in entries:
        hits=[]
        for part,text in windows:
            score=SequenceMatcher(None,tokens(entry['text']),tokens(text)).ratio()
            if score>=.72:
                hits.append({'cue_ids':[c['id'] for c in part],'start':part[0]['start'],'end':part[-1]['end'],
                             'heard_text':text,'similarity':round(score,3),
                             'status':'exact_text' if tokens(entry['text'])==tokens(text) else 'variant_needs_listening'})
        matches.append({**entry,'candidates':sorted(hits,key=lambda x:(-x['similarity'],x['start'])),
                        'status':'candidate_times_only' if hits else 'not_matched'})
    return {'version':1,'reference':str(path),'human_approved':False,'transcript_modified':False,
            'note':'Repeated lines deliberately retain all candidate occurrences; sequence and word-level alignment must be checked. Unmatched songs may be absent in this episode.',
            'lines':matches,'song_cues':[{'id':c['id'],'start':c['start'],'end':c['end'],'text':c['text']} for c in rows if c.get('kind')=='song' or '♪' in c.get('text','')]}
