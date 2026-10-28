"""Exact-word temporal matching and word-preserving segmentation."""
import copy,math,re
from fidelity import words
from reconcile_review import wrap

def equivalence(items):
    """Normalize number spelling for timing only; keep the measured time span.

    No fuzzy spelling or phonetic substitution. Multi-token ASR words are
    expanded, then valid cardinal sequences collapsed to the same numeric key.
    Subtitle wording and fidelity baseline are never edited here.
    """
    from fidelity import number_value
    flat=[]
    for item in items:
        for token in words(item['word']):flat.append(dict(item,token=token))
    result=[];i=0
    while i<len(flat):
        match=None
        for j in range(min(len(flat),i+5),i,-1):
            value=number_value([x['token'] for x in flat[i:j]])
            if value is not None:match=(j,value);break
        if match:
            j,value=match;part=flat[i:j];result.append(dict(part[0],token=str(value),end=part[-1].get('end',0),probability=min(x.get('probability',1) for x in part)));i=j
        else:result.append(flat[i]);i+=1
    return result

def display_anchors(text, anchors):
    """Map visible whitespace words to independently matched normalized tokens.

    Hyphenated fractions/names may span several acoustic tokens. Aggregate only
    exact consecutive tokens; never interpolate a timestamp or replace wording.
    """
    parts=text.replace('♪','').split();out=[];offset=0
    for part in parts:
        target=[x['token'] for x in equivalence([{'word':part}])]
        span=anchors[offset:offset+len(target)]
        if not target or [x.get('token') for x in span]!=target:return None
        out.append({'word':part,'start':span[0]['start'],'end':span[-1]['end'],
                    'probability':min(w.get('probability',0) for w in span)})
        offset+=len(target)
    return out if offset==len(anchors) else None


def align(rows,witness,fps):
    anchors=equivalence([w for segment in witness.get('segments',[]) for w in segment.get('words',[])])
    out=[];events=[];used=set()
    for original in rows:
        c=copy.deepcopy(original);tokens=[x['token'] for x in equivalence([{'word':c['text']}])];chosen=None
        for i,w in enumerate(anchors):
            if abs(w['start']-c['start'])>4 or any(j in used for j in range(i,i+len(tokens))):continue
            candidate=anchors[i:i+len(tokens)]
            if tokens and [x['token'] for x in candidate]==tokens and abs(candidate[-1]['end']-c['end'])<4 and all(x.get('probability',0)>=.45 and x['end']>x['start'] for x in candidate) and round(candidate[-1]['end']*fps)>round(candidate[0]['start']*fps):
                chosen=candidate;used.update(range(i,i+len(tokens)));break
        if chosen is None:
            c['timingReview']='pending: no exact independent word-time match';out.append(c);continue
        c.update(start=round(chosen[0]['start']*fps)/fps,end=round(chosen[-1]['end']*fps)/fps,audioStart=chosen[0]['start'],audioEnd=chosen[-1]['end'],timingEvidence='Exact words or equal-value number spelling independently matched to local ASR timestamps; machine evidence',wordAnchors=chosen,timingReview='machine_word_matched',checked=False)
        events.append({'id':c['id'],'before':[original['start'],original['end']],'after':[c['start'],c['end']],'reason':'Exact lexical match in same local scene; no replacement of caption words'})
        # Only split where the visible text maps one-to-one to the real word anchors.
        text=c['text'].replace('♪','').strip();parts=text.split()
        mapped=display_anchors(text,chosen)
        if mapped:chosen=mapped;c['wordAnchors']=mapped
        if len(parts)!=len(chosen) or (len(text)<=84 and c['end']-c['start']<=7):out.append(c);continue
        groups=[];begin=0
        while begin<len(parts):
            stop=begin+1
            while stop<len(parts) and len(' '.join(parts[begin:stop+1]))<=76 and chosen[stop]['end']-chosen[begin]['start']<=6.5:stop+=1
            preferred=[j for j in range(begin+2,stop+1) if re.search(r'[,.;:!?]$',parts[j-1])]
            if stop<len(parts) and preferred:stop=preferred[-1]
            groups.append((begin,stop));begin=stop
        for j,(a,b) in enumerate(groups):
            x=copy.deepcopy(c);t=' '.join(parts[a:b]);x.update(id=c['id']+'-'+str(j+1),sourceGroup=c.get('sourceGroup',c['id']),sourceText=c['sourceText'],text=wrap(('♪ '+t+' ♪') if c.get('kind')=='song' else t),start=round(chosen[a]['start']*fps)/fps,end=round(chosen[b-1]['end']*fps)/fps,audioStart=chosen[a]['start'],audioEnd=chosen[b-1]['end'],wordAnchors=chosen[a:b]);out.append(x)
    return sorted(out,key=lambda c:(c['start'],c['end'])),events


def apply_forced(rows,results,witness,fps):
    """Use fixed-text internal alignment only with independent boundary anchors.

    DTW often assigns the first word to clip time zero and punctuation to silence.
    Never expose those artifacts as measured speech boundaries.
    """
    independent=equivalence([w for s in witness.get('segments',[]) for w in s.get('words',[])])
    out=copy.deepcopy(rows);events=[]
    for c in out:
        r=results.get(c['id'],{})
        if not r or words(r.get('text',''))!=words(c['text']):continue
        anchors=[copy.deepcopy(w) for w in r.get('words',[]) if words(w['word'])]
        target=equivalence([{'word':c['text']}])
        if not anchors or not target:continue
        first=[w for w in independent if w['token']==target[0]['token'] and abs(w['start']-c.get('audioStart',c['start']))<=1.2 and w.get('probability',0)>=.45]
        last=[w for w in independent if w['token']==target[-1]['token'] and abs(w['end']-c.get('audioEnd',c['end']))<=1.2 and w.get('probability',0)>=.45]
        if len(first)!=1 or len(last)!=1:continue
        anchors[0]['start']=first[0]['start'];anchors[-1]['end']=last[0]['end']
        if any(w['end']<=w['start'] for w in anchors):continue
        if any(a['end']>b['start']+.04 for a,b in zip(anchors,anchors[1:])):continue
        if sum(w['probability'] for w in anchors)/len(anchors)<.6:continue
        start,end=anchors[0]['start'],anchors[-1]['end']
        if not start<end or end-start>12:continue
        previous=[c['start'],c['end']]
        c.update(start=round(start*fps)/fps,end=round(end*fps)/fps,audioStart=start,audioEnd=end,wordAnchors=anchors,timingReview='machine_word_matched',timingEvidence='Fixed-transcript internal alignment with independently recognized exact boundary words; not content approval',checked=False)
        c['unresolved']=c.get('unresolved','').replace('时间边界尚无逐词证据，需复核。','').strip()
        events.append({'id':c['id'],'before':previous,'after':[c['start'],c['end']],'reason':c['timingEvidence']})
    return out,events
