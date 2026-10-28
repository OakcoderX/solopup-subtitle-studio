"""Separate screenplay comparison evidence. Never overwrite heard words."""
import difflib,re
from fidelity import words

def compare(rows, screenplay):
    lines=[x.strip() for x in screenplay.splitlines() if len(words(x))>=2]
    passages=[]
    for i in range(len(lines)):
        for n in range(1,4):
            text=' '.join(lines[i:i+n]);tokens=words(text)
            if 2<=len(tokens)<=100:passages.append((text,tokens))
    result=[]
    for cue in rows:
        tokens=words(cue['text']);best=(0.0,'',[])
        for text,candidate in passages:
            if not tokens:continue
            # Compare short local windows so script page labels do not prevent a match.
            matcher=difflib.SequenceMatcher(None,tokens,candidate,autojunk=False)
            match=matcher.find_longest_match(0,len(tokens),0,len(candidate))
            start=max(0,match.b-match.a);window=candidate[start:start+len(tokens)+2]
            score=difflib.SequenceMatcher(None,tokens,window,autojunk=False).ratio()
            if candidate[start:start+len(tokens)]==tokens:score=1.0
            if score>best[0]:best=(score,text,window)
        score,text,window=best
        classification='exact_or_contained' if score==1 else 'difference_to_review' if score>=.6 else 'no_reliable_match'
        if len(tokens)<3:classification='short_phrase_requires_context'
        result.append({'id':cue['id'],'start':cue['start'],'end':cue['end'],'audio_draft':cue['text'],'script_reference':text if score>=.6 else '', 'similarity':round(score,3),'classification':classification,'text_modified':False})
    return result
