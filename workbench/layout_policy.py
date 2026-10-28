"""Word-preserving line layout and explicit unresolved segmentation queue."""
import copy,re

def wrap(text):
    text=' '.join(text.split())
    if len(text)<=42:return text
    words=text.split();choices=[]
    for i in range(1,len(words)):
        a,b=' '.join(words[:i]),' '.join(words[i:])
        if max(len(a),len(b))<=42:
            penalty=40 if words[i-1].lower().strip(',.!?') in {'a','an','the','to','of','and','or','my','our','some'} else 0
            choices.append((abs(len(a)-len(b))+penalty,a+'\n'+b))
    return min(choices)[1] if choices else text

def invalidate(c):
    c['checked']=False
    if c.get('speedReview'):
        c['speedReview']['accepted']=False;c['speedReview']['invalidated']=True

def prepare(state, preserve_checked=False):
    """Run at every production/save/SDH merge boundary; never guess timecodes."""
    out=copy.deepcopy(state);tasks=[];changed=False
    from number_policy import normalize
    for track in ('standard','sdh'):
        rows=normalize(out.get(track,[]))
        if preserve_checked:
            prior={c['id']:c for c in out.get(track,[]) if c.get('checked')}
            rows=[copy.deepcopy(prior.get(c['id'],c)) for c in rows]
        if rows!=out.get(track,[]):changed=True
        out[track]=rows
    for track in ('standard','sdh'):
        for c in out.get(track,[]):
            formatted=wrap(c['text'])
            if c.get('kind')=='song':formatted=re.sub(r'(?<!\.)\.(\s*♪?\s*)$',r'\1',formatted)
            if formatted!=c['text'] and not (preserve_checked and c.get('checked')):
                c['text']=formatted;invalidate(c);changed=True
            else:formatted=c['text']
            lengths=[len(x) for x in formatted.splitlines()]
            if max(lengths,default=0)>42 or len(lengths)>2:
                tasks.append({'track':track,'id':c.get('id'),'start':c['start'],'end':c['end'],
                    'lineLengths':lengths,'action':'split_at_verified_audio_boundary','status':'needs_audio_timing',
                    'reason':'Cannot fit two 42-character lines without splitting; preserve all words.'})
    from presentation import visible_events,layout_parts
    from fractions import Fraction
    import math
    def frame(t,rate):return math.floor(float(t)*float(Fraction(str(rate)))+.5)
    for track in ('standard','sdh'):
        seen=set()
        for a,b,group in visible_events(out.get(track,[]),frame,out.get('frameRate','24')):
            ids=tuple(c.get('id') for c in group)
            if ids in seen:continue
            seen.add(ids);lines=layout_parts(group)
            if len(lines)>2:
                tasks.append({'track':track,'cue_ids':list(ids),'start':a/float(Fraction(str(out.get('frameRate','24')))),
                    'action':'resolve_simultaneous_layout','status':'needs_audio_timing','lineCount':len(lines),
                    'reason':'Sound and dialogue share the two-line budget; do not hide labels or rewrite speech.'})
    from presentation import position_changes
    out['presentationTasks']=[dict(item,track=track,action='review_vertical_jump') for track in ('standard','sdh') for item in position_changes(out.get(track,[]),frame,out.get('frameRate','24'))]
    out['layoutTasks']=tasks
    if changed:out.setdefault('release',{})['content_verified']=False
    from evidence_gate import refresh
    return refresh(out)


def split_verified(cue,prefix,witness,rate='24'):
    """Resolve a queued phrase split using exact local audio-word evidence.

    Caller chooses a grammatical prefix; never estimate time from text length.
    The original cue's whole word sequence must occur in a nearby witness,
    while the internal boundary word requires >=0.8 confidence. Uncertain
    utterance-leading tokens cannot veto a reliable internal anchor.
    """
    from fidelity import words
    from fractions import Fraction
    import math
    text=' '.join(cue['text'].split());prefix=' '.join(prefix.split())
    if not text.startswith(prefix+' '):raise ValueError('Split must preserve an exact text prefix')
    from timing_review import equivalence
    verbatim=words(text)
    target=[x['token'] for x in equivalence([{'word':text}])]
    position=len(equivalence([{'word':prefix}]));matches=[]
    # ASR segment boundaries are not acoustic sentence boundaries. Search the
    # consecutive local word stream without dropping, sorting or deduplicating
    # tokens; overlapping/repeated witnesses must still fail uniqueness.
    local=[w for segment in witness.get('segments',[])
          if segment['end']>=cue['start']-2 and segment['start']<=cue['end']+2
          for w in segment.get('words',[])]
    flat=[(w['token'],w) for w in equivalence(local)]
    tokens=[t for t,w in flat]
    for j in range(len(tokens)-len(target)+1):
        if tokens[j:j+len(target)]!=target:continue
        span=[w for _,w in flat[j:j+len(target)]]
        if any(w['end']<=w['start'] for w in span):continue
        if any(a['start']>b['start'] or b['start']-a['end']>2
               for a,b in zip(span,span[1:])):continue
        word=flat[j+position][1]
        previous=flat[j+position-1][1]
        if word.get('probability',0)<.8 or previous.get('probability',0)<.6:continue
        if cue['start']<word['start']<cue['end']:matches.append((word,previous))
    if len(matches)!=1:raise ValueError('Needs original-audio review: missing or ambiguous internal anchor')
    word,previous=matches[0]
    fps=float(Fraction(str(rate)));boundary=math.floor(word['start']*fps+.5)/fps
    left_end=min(math.floor(previous['end']*fps+.5)/fps,boundary-2/fps)
    if previous['end']-left_end>3/fps+.001:
        raise ValueError('Split cannot cut audible words to create a gap')
    if (left_end-cue['start'])*fps<20 or (cue['end']-boundary)*fps<20:
        raise ValueError('Split would produce a cue shorter than 20 frames')
    a,b=copy.deepcopy(cue),copy.deepcopy(cue)
    a.update(id=str(cue['id'])+'-L1',text=wrap(prefix),end=left_end,audioEnd=previous['end'])
    b.update(id=str(cue['id'])+'-L2',text=wrap(text[len(prefix)+1:]),start=boundary,audioStart=word['start'])
    for child in (a,b):
        invalidate(child);child.pop('wordAnchors',None)
        child['layoutSplit']={'parent':cue['id'],'prefix':prefix,'boundary':boundary,'next_word':word,'previous_word':previous,
                              'reason':'Exact original-audio internal anchor; all words preserved; two-frame gap'}
    assert words(a['text']+' '+b['text'])==verbatim
    return [a,b]


def resolve_long_cues(rows,witness,rate='24'):
    """Only split at punctuation backed by unique exact audio-word evidence."""
    result=[];changes=[]
    for cue in rows:
        text=' '.join(cue['text'].split());choices=[]
        if len(text)>84:
            tokens=text.split()
            for i in range(1,len(tokens)):
                if not tokens[i-1].endswith((',', '.', '?', '!', ';', ':')):continue
                try:parts=split_verified(cue,' '.join(tokens[:i]),witness,rate)
                except ValueError:continue
                if all(len(p['text'].splitlines())<=2 and all(len(l)<=42 for l in p['text'].splitlines())for p in parts):
                    choices.append((abs(len(parts[0]['text'])-len(parts[1]['text'])),parts))
        if choices:
            parts=min(choices,key=lambda x:x[0])[1];result.extend(parts)
            changes.append({'id':cue['id'],'children':[p['id'] for p in parts],'reason':'Punctuation and exact audio anchor; no word edits'})
        else:result.append(cue)
    return result,changes


def repair_legacy_split_anchors(rows,witness,rate='24',cuts=None):
    """Restore the true left word-end in old exact-prefix splits.

    Older ledgers used the NEXT word onset as the previous clause's audioEnd.
    That turns silence into speech evidence and can legitimize an excessive
    tail. Recover only a full exact lexical witness; do not infer a word time.
    """
    from fractions import Fraction
    import math
    out=copy.deepcopy(rows);events=[];parents={}
    for c in out:
        l=c.get('layoutSplit',{})
        if l.get('next_word') and not l.get('previous_word'):
            parents.setdefault(l['parent'],[]).append(c)
    fps=float(Fraction(str(rate)))
    for parent,pair in parents.items():
        pair.sort(key=lambda c:c['start'])
        if len(pair)!=2 or any(c.get('checked') for c in pair):continue
        left,right=pair;prefix=left['layoutSplit']['prefix']
        merged=copy.deepcopy(left);merged.update(id=parent,text=' '.join(left['text'].split())+' '+' '.join(right['text'].split()),end=right['end'])
        try:verified=split_verified(merged,prefix,witness,rate)
        except ValueError:continue
        measured=verified[0]['audioEnd'];old=left.get('audioEnd')
        if cuts is None:continue
        limit=measured+.5
        following_cuts=[t-2/fps for t in cuts if measured<t<=left['end']]
        if following_cuts:limit=min(limit,min(following_cuts))
        end=min(left['end'],math.floor(limit*fps+1e-7)/fps,right['start']-2/fps)
        if (end-left['start'])*fps<20:continue
        before=[left['end'],old];left.update(end=end,audioEnd=measured)
        for c in pair:
            c['layoutSplit']['previous_word']=verified[0]['layoutSplit']['previous_word']
            invalidate(c)
        events.append({'parent':parent,'left':left['id'],'before':before,'after':[end,measured],
                       'reason':'Restore independently recognized last-word end; next-word onset is not speech-end evidence'})
    return out,events


def split_anchored(rows,rate=24):
    """Split an overlong sentence at a measured clause boundary, never rewrite."""
    from fidelity import words
    out=[];changes=[];fps=float(rate)
    for c in rows:
        text=' '.join(c['text'].split());parts=text.split();anchors=c.get('wordAnchors',[]);options=[]
        if len(text)>84 and len(parts)==len(anchors) and words(text)==words(' '.join(w['word']for w in anchors)):
            for i in range(2,len(parts)-1):
                if parts[i].lower() not in {'and','but','because','so','while'} and not parts[i-1].endswith((',', ';', ':')):continue
                if anchors[i].get('probability',0)<.6:continue
                left,right=wrap(' '.join(parts[:i])),wrap(' '.join(parts[i:]))
                if any(len(line)>42 for t in (left,right)for line in t.splitlines()):continue
                end=round(anchors[i-1]['end']*fps)/fps;start=max(round(anchors[i]['start']*fps)/fps,end+2/fps)
                # At most two-frame delayed appearance, never early words or cut speech.
                if start-anchors[i]['start']>2/fps+.001 or (end-c['start'])*fps<20 or (c['end']-start)*fps<20:continue
                a,b=copy.deepcopy(c),copy.deepcopy(c)
                a.update(id=c['id']+'-A',text=left,end=end,audioEnd=anchors[i-1]['end'],wordAnchors=anchors[:i])
                b.update(id=c['id']+'-B',text=right,start=start,audioStart=anchors[i]['start'],wordAnchors=anchors[i:])
                for x in (a,b):invalidate(x);x['layoutSplit']={'parent':c['id'],'boundary_word':anchors[i],'reason':'Measured clause boundary, preserve every word, <=2-frame onset delay'}
                options.append((abs(len(left)-len(right)),[a,b]))
        if options:
            children=min(options,key=lambda x:x[0])[1];out.extend(children);changes.append({'parent':c['id'],'children':[x['id']for x in children]})
        else:out.append(copy.deepcopy(c))
    return out,changes


def display_word_anchors(text, anchors):
    """Map exact ASR tokens to displayed words, including hyphenated names.

    Never infer words or times from text length; mismatches fail closed.
    """
    from fidelity import words
    result=[];cursor=0
    for part in text.split():
        target=words(part);collected=[];selected=[]
        while cursor<len(anchors) and len(collected)<len(target):
            item=anchors[cursor];cursor+=1
            collected.extend(words(item['word']));selected.append(item)
        if collected!=target or not selected:return []
        result.append({'word':part,'start':selected[0]['start'],'end':selected[-1]['end'],
                       'probability':min(w.get('probability',0) for w in selected)})
    return result if cursor==len(anchors) else []


def fit_sound_dialogue(rows,sound_spans,fps=24):
    """Reserve one of the two lines for a concurrent sound using real word times."""
    from fidelity import words
    out=[];events=[]
    for c in rows:
        text=' '.join(c['text'].split());parts=text.split();anchors=display_word_anchors(text,c.get('wordAnchors',[]));choices=[]
        overlap=any(a<c['end'] and c['start']<b for a,b in sound_spans)
        if overlap and not c.get('checked') and 42<len(text)<=84 and c.get('kind')!='song' and len(parts)==len(anchors) and words(text)==words(' '.join(w['word']for w in anchors)):
            for i in range(2,len(parts)-1):
                left,right=' '.join(parts[:i]),' '.join(parts[i:])
                if max(len(left),len(right))>42:continue
                if parts[i-1].lower().strip(',.!?') in {'a','an','the','to','of','and','or','my','our','some','your','his','her'}:continue
                if anchors[i].get('probability',0)<.6:continue
                start=round(anchors[i]['start']*fps)/fps;end=min(round(anchors[i-1]['end']*fps)/fps,start-2/fps)
                if anchors[i-1]['end']-end>3/fps+.001 or abs(start-anchors[i]['start'])>1/fps or (end-c['start'])*fps<20 or (c['end']-start)*fps<20:continue
                a,b=copy.deepcopy(c),copy.deepcopy(c)
                a.update(id=c['id']+'-S1',text=left,end=end,audioEnd=anchors[i-1]['end'],wordAnchors=anchors[:i])
                b.update(id=c['id']+'-S2',text=right,start=start,audioStart=anchors[i]['start'],wordAnchors=anchors[i:])
                for child in (a,b):invalidate(child);child['layoutSplit']={'parent':c['id'],'reason':'One dialogue line plus one sound line; measured word boundary; no word edits'}
                punctuation=0 if parts[i-1].endswith((',', ';', ':')) or parts[i].lower() in {'and','but','except','because','while','can'} else 20
                choices.append((punctuation+abs(len(left)-len(right)),[a,b]))
        if choices:
            children=min(choices,key=lambda x:x[0])[1];out.extend(children);events.append({'parent':c['id'],'children':[x['id']for x in children]})
        else:out.append(copy.deepcopy(c))
    return out,events


def split_internal_evidence(rows, forced, witness, rate=24):
    """Recover a phrase split from corroborated internal words, keeping outer doubts.

    The full utterance need not match ASR (often a sung opening is uncertain).
    Three consecutive exact words, one unique local witness, positive durations,
    and agreement with fixed-text alignment within 250ms are required. This does
    not approve whole-cue timing or wording.
    """
    from fidelity import words
    from fractions import Fraction
    fps=float(Fraction(str(rate)));ind=[w for s in witness.get('segments',[]) for w in s.get('words',[]) if words(w['word'])]
    out=[];changes=[]
    for original in rows:
        raw=original['text'].replace('♪','').strip();parts=raw.split();target=words(raw)
        f=forced.get(original['id'],{});anchors=[w for w in f.get('words',[]) if words(w['word'])]
        if len(parts)!=len(target) or len(anchors)!=len(parts) or words(f.get('text',''))!=target:
            out.append(copy.deepcopy(original));continue
        if len(original['text'])<=84 and original['end']-original['start']<=7:
            out.append(copy.deepcopy(original));continue
        boundaries={}
        for i in range(1,len(parts)-2):
            if not (parts[i-1].endswith((',', ';', '.', '?', '!')) or parts[i].lower() in {'and','but','when','while','because'}):continue
            forced_word=anchors[i];previous=anchors[i-1]
            if forced_word['end']<=forced_word['start'] or previous['end']<=previous['start'] or previous.get('probability',0)<.6:continue
            found=[]
            for j in range(len(ind)-2):
                span=ind[j:j+3]
                if words(' '.join(w['word'] for w in span))!=target[i:i+3]:continue
                if abs(span[0]['start']-forced_word['start'])>.25:continue
                if any(w['end']<=w['start'] or w.get('probability',0)<.6 for w in span):continue
                if sum(w.get('probability',0) for w in span)/3<.85:continue
                aligned=anchors[i:i+3]
                if any(w['end']<=w['start'] or abs(w['start']-v['start'])>.25 for w,v in zip(span,aligned)):continue
                found.append(span[0])
            if len(found)!=1:continue
            start=round(found[0]['start']*fps)/fps;end=round(previous['end']*fps)/fps
            if end>start-2/fps+1e-6:continue
            boundaries[i]=(start,end,found[0],previous)
        def partition(a,b,start,end):
            text=' '.join(parts[a:b]);display=('♪ '+text+' ♪') if original.get('kind')=='song' else text
            if len(display)<=84 and end-start<=7:return [(a,b,start,end)]
            opts=[]
            for i,(right_start,left_end,_,_) in boundaries.items():
                if not a<i<b or left_end-start<20/fps or end-right_start<20/fps:continue
                left=partition(a,i,start,left_end);right=partition(i,b,right_start,end)
                if left and right:opts.append(left+right)
            return min(opts,key=lambda p:(len(p),max(y[3]-y[2] for y in p))) if opts else None
        groups=partition(0,len(parts),original['start'],original['end'])
        if not groups:out.append(copy.deepcopy(original));continue
        children=[]
        for k,(a,b,start,end) in enumerate(groups,1):
            child=copy.deepcopy(original);text=' '.join(parts[a:b]);child.update(id=original['id']+'-I'+str(k),start=start,end=end,text=wrap(('♪ '+text+' ♪') if original.get('kind')=='song' else text));child.pop('wordAnchors',None)
            # A verified internal boundary does not verify the parent's outer edges.
            # Never carry the entire utterance's audioEnd into an earlier child.
            if a in boundaries:child['audioStart']=boundaries[a][2]['start']
            if b in boundaries:child['audioEnd']=boundaries[b][3]['end']
            child['timingReview']='pending: internal split verified; outer phrase timing requires review'
            child['timingEvidence']=''
            child['unresolved']=child.get('unresolved') or '时间边界尚无逐词证据，需复核。'
            child['internalSplitEvidence']={'parent':original['id'],'left_boundary':boundaries.get(a),'right_boundary':boundaries.get(b),'reason':'Three exact independently recognized words corroborate forced internal boundary; outer uncertainty retained'}
            invalidate(child);children.append(child)
        assert words(' '.join(c['text'] for c in children))==target
        out.extend(children);changes.append({'id':original['id'],'children':[c['id'] for c in children]})
    return out,changes


def recover_standard_layout(rows,rate=24):
    """Undo legacy SDH-only splits in English, retaining every source word/anchor."""
    from fidelity import audit
    out=[];changes=[];i=0
    while i<len(rows):
        first=rows[i];split=first.get('layoutSplit',{});parent=split.get('parent')
        if not parent or not str(split.get('reason','')).startswith('One dialogue line plus one sound line'):
            out.append(copy.deepcopy(first));i+=1;continue
        group=[first];j=i+1
        while j<len(rows) and rows[j].get('layoutSplit',{}).get('parent')==parent:group.append(rows[j]);j+=1
        text=wrap(' '.join(c['text'] for c in group))
        eligible=(len(group)>1 and not any(c.get('id')==parent for c in rows) and not any(c.get('checked') for c in group)
                  and len({c.get('sourceGroup') for c in group})==1
                  and len({c.get('presentation') for c in group})==1
                  and group[-1]['end']-first['start']<=7
                  and len(text.splitlines())<=2 and max(map(len,text.splitlines()))<=42
                  and not audit(group))
        if not eligible:out.extend(copy.deepcopy(group));i=j;continue
        merged=copy.deepcopy(first);merged.update(id=parent,text=text,end=group[-1]['end'],audioEnd=group[-1].get('audioEnd',group[-1]['end']))
        merged['wordAnchors']=[copy.deepcopy(w) for c in group for w in c.get('wordAnchors',[])]
        merged['unresolved']=' '.join(dict.fromkeys(c.get('unresolved','') for c in group)).strip()
        merged['numberFormatting']=[copy.deepcopy(x) for c in group for x in c.get('numberFormatting',[])]
        merged['legacyLayoutRecovery']={'children':[c['id']for c in group],'reason':'Recover two-line English from old SDH-only one-line splits; no word edits'}
        merged.pop('layoutSplit',None);invalidate(merged)
        if any(c.get('timingReview')!='machine_word_matched' for c in group):merged['timingReview']='pending: merged original phrase retains timing doubts';merged['timingEvidence']=''
        if audit([merged]):out.extend(copy.deepcopy(group))
        else:out.append(merged);changes.append(merged['legacyLayoutRecovery'])
        i=j
    return out,changes


def fit_simultaneous_dialogue(rows, fps=24):
    """Budget concurrent dialogue with SDH; preserve source words and styles."""
    from presentation import visible_events, layout_parts
    import math
    frame=lambda t,rate:math.floor(t*fps+.5)
    crowded={c['id'] for a,b,g in visible_events(rows,frame,fps)
             if len(layout_parts(g))>2 for c in g
             if c.get('kind') not in {'sound','song'} and len(c['text'])>42}
    out=[];changes=[]
    for c in rows:
        if c['id'] in crowded:
            parts,events=fit_sound_dialogue([c],[(c['start'],c['end'])],fps)
            for part in parts:
                if events:part['layoutSplit']['reason']='Concurrent captions share two lines; measured word boundary; no word edits'
            out.extend(parts);changes.extend(events)
        else:out.append(copy.deepcopy(c))
    return sorted(out,key=lambda c:(c['start'],c['end'])),changes
