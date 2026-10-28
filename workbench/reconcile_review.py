"""Build a reviewable revision from independent witnesses, preserving the audit trail."""
import copy,difflib,json,math,re
from pathlib import Path
from fidelity import words,audit
from timed_text import check
from tail_room import extend_tails

from layout_policy import wrap

def unique_review_key(index, used):
    """Allocate a second-pass ID outside the source draft's ID namespace."""
    n=index
    while True:
        key=f'Q{n:04d}'
        if key not in used:
            used.add(key)
            return key
        n+=1

def restore_matching_anchors(rows, prior):
    """Use prior audio anchors only for the same words in the same local scene.

    No lexical similarity threshold: exact normalized word sequences are required.
    A new utterance may match up to four old phrases or vice versa. This restores
    measured segmentation without replacing words with a screenplay or old draft.
    """
    out=[];events=[];i=0
    while i<len(rows):
        found=None
        for n in range(1,min(4,len(rows)-i)+1):
            group=rows[i:i+n];tokens=words(' '.join(c['text'] for c in group))
            for j,o in enumerate(prior):
                if abs(group[0]['start']-o['start'])>4:continue
                for m in range(1,min(4,len(prior)-j)+1):
                    old=prior[j:j+m]
                    if abs(group[-1]['end']-old[-1]['end'])>4:continue
                    if tokens and tokens==words(' '.join(c['text'] for c in old)) and all(c.get('audioStart') is not None and c.get('audioEnd') is not None and c.get('timingEvidence') for c in old):
                        found=(n,group,old);break
                if found:break
            if found:break
        if not found:out.append(rows[i]);i+=1;continue
        n,group,old=found
        # Reuse boundaries, keeping this revision's source wording/punctuation.
        text=' '.join(c['sourceText'] for c in group);w=text.split()
        # Segmentation requires a one-to-one lexical whitespace map. Otherwise
        # retain the new segmentation and restore only the outer timing anchors.
        if len(words(text))!=len(w):
            if len(group)==len(old)==1:
                c=copy.deepcopy(group[0]);c.update(sourceGroup=old[0].get('sourceGroup',c['sourceGroup']),sourceText=old[0].get('sourceText',c['sourceText']),start=old[0]['start'],end=old[0]['end'],audioStart=old[0]['audioStart'],audioEnd=old[0]['audioEnd'],timingEvidence='exact-word match to retained original-audio anchors');out.append(c)
                events.append({'new_ids':[x['id'] for x in group],'prior_ids':[old[0]['id']],'reason':'Same words and local time; preserve parent source group despite hyphenated tokens'})
            else:out.extend(group)
            i+=n;continue
        cursor=0
        prior_groups={str(c.get('sourceGroup')) for c in old if c.get('sourceGroup')}
        matched_prior_group=len(prior_groups)==1
        source_group=old[0].get('sourceGroup') if matched_prior_group else group[0]['sourceGroup']
        source_text=old[0].get('sourceText',text) if matched_prior_group else text
        witnesses=[x for c in group for x in c.get('witnessIds',[])]
        for k,o in enumerate(old):
            count=len(words(o['text']));part=' '.join(w[cursor:cursor+count]);cursor+=count
            c=copy.deepcopy(group[0]);c.update(id=group[0]['id']+('-'+str(k+1) if len(old)>1 else ''),sourceGroup=source_group,sourceText=source_text,witnessIds=witnesses,text=wrap(('♪ '+part+' ♪')if c['kind']=='song' else part),start=o['start'],end=o['end'],audioStart=o['audioStart'],audioEnd=o['audioEnd'],timingEvidence='exact-word match to retained original-audio anchors')
            if any(x.get('unresolved') for x in group):c['unresolved']='; '.join(dict.fromkeys(x['unresolved'] for x in group if x.get('unresolved')))
            out.append(c)
        events.append({'new_ids':[c['id'] for c in group],'prior_ids':[c['id'] for c in old],'reason':'Same words and local time; reuse preserved original-audio timing and segmentation'})
        i+=n
    return out,events

def deduplicate_review_witnesses(rows):
    """Collapse duplicate or boundary-truncated witnesses only with shared source IDs."""
    out=[];removed=[]
    for cue in sorted(rows,key=lambda c:(c['start'],c['end'])):
        duplicate=next((c for c in out[-4:]
            if c.get('kind')==cue.get('kind')
            and set(c.get('witnessIds',[])) & set(cue.get('witnessIds',[]))
            and abs(c['start']-cue['start'])<=.5
            and min(c['end'],cue['end'])-max(c['start'],cue['start']) >= .5*min(c['end']-c['start'],cue['end']-cue['start'])
            and (words(c['text'])==words(cue['text'])
                 or words(c['text'])==words(cue['text'])[:len(words(c['text']))]
                 or words(cue['text'])==words(c['text'])[:len(words(cue['text']))])),None)
        if duplicate is None:out.append(cue)
        else:
            short,long=(duplicate,cue) if len(words(duplicate['text']))<=len(words(cue['text'])) else (cue,duplicate)
            if short is duplicate:
                duplicate.update({k:v for k,v in long.items() if k not in {'id','sourceGroup'}})
                duplicate['witnessIds']=list(dict.fromkeys(short.get('witnessIds',[])+long.get('witnessIds',[])))
            else:
                duplicate['witnessIds']=list(dict.fromkeys(duplicate.get('witnessIds',[])+cue.get('witnessIds',[])))
            removed.append({'removed':short['id'],'retained':long['id'],'reason':'Overlapping duplicate/prefix text and shared first-pass witness'})
    return out,removed

def reconcile(state, reviews, prior=None, cuts=None, duration=660, cut_scope_end=None, fps=24):
    originals={c['id']:c for c in state['standard']};rows=[];cue_verdicts={};sounds={};ledger=[]
    used_review_keys=set(originals)
    used_review_keys.update(str(c.get('sourceGroup')) for c in state['standard'] if c.get('sourceGroup'))
    for path in sorted(reviews):
        d=json.loads(Path(path).read_text());p=d['parsed'];a,b=d['interval']
        for r in p['cue_reviews']:cue_verdicts.setdefault(r['id'],[]).append(dict(r,evidence=str(path)))
        for r in p['sound_reviews']:
            if str(r['id']) in sounds:raise ValueError('Duplicate sound review ID')
            sounds[str(r['id'])]=dict(r,evidence=str(path))
        for r in p['speech']:
            start=float(r['start']);end=float(r['end'])
            # Keep a complete utterance that starts just before an ownership
            # boundary when it continues into this window and cites source cues.
            boundary_context=(start<a and end>a and a-start<=2
                             and bool(set(r.get('source_cue_ids',[])) & set(originals)))
            if not (a<=start<b or boundary_context) or not state.get('scope',[0,duration])[0]<=start<state.get('scope',[0,duration])[1]:continue
            if r.get('invalid_timing'):continue
            text=r['text'].replace('♪','').strip();review_key=unique_review_key(len(rows)+1,used_review_keys);c={'id':review_key,'start':round(r['start']*fps)/fps,'end':round(r['end']*fps)/fps,'audioStart':r['start'],'audioEnd':r['end'],'text':wrap(('♪ '+text+' ♪') if r['kind']=='song' else text),'kind':r['kind'],'italic':r['kind']=='song','region':'bottom','checked':False,'sourceText':text,'sourceGroup':review_key,'witnessIds':r.get('source_cue_ids',[]),'sourceEvidence':str(path),'timingEvidence':'second-pass Qwen approximate timing; requires alignment','scriptComparison':r.get('script_comparison'),'reviewReason':r.get('reason','')}
            c['presentation']=r.get('presentation','song' if r['kind']=='song' else 'unknown');c['presentationEvidence']=r.get('presentation_evidence','');c['italic']=c['presentation'] in {'song','voiceover','device'}
            witness_text=' '.join(originals[k]['text'] for k in c['witnessIds'] if k in originals)
            if witness_text and words(witness_text)!=words(text):c['unresolved']='Independent passes disagree; compare original audio before accepting wording.'
            if r.get('uncertain') or r.get('script_comparison')=='uncertain':c['unresolved']='Second-pass audio/script uncertainty: '+r.get('reason','')
            rows.append(c);ledger.append({'id':c['id'],'first_pass_ids':c['witnessIds'],'first_pass_texts':[originals[k]['text']for k in c['witnessIds'] if k in originals],'revised_text':text,'reason':r.get('reason'),'evidence':str(path)})
    # Missing adjudication is a hard gate, not silent deletion.
    missing=set(originals)-set(cue_verdicts)
    if missing:raise ValueError('Unreviewed original cues: '+','.join(sorted(missing)))
    covered={i for c in rows for i in c.get('witnessIds',[])}
    for i,c in originals.items():
        if i not in covered:
            decisions=cue_verdicts[i]
            if not any(words(c['text']) and ' '.join(words(c['text'])) in ' '.join(words(x['text'])) and min(c['end'],x['end'])>max(c['start'],x['start']) for x in rows):
                keep=copy.deepcopy(c);keep['id']='P'+i;keep['unresolved']='Not represented in second-pass output; preserve for listening';rows.append(keep)
            ledger.append({'removed_first_pass_id':i,'reviews':decisions,'requires_content_review':True})
    rows.sort(key=lambda c:(c['start'],c['end']))
    # Resolve cross-window duplicate/prefix witnesses before restoring old
    # segmentation; anchoring a truncated row first can freeze the truncation.
    rows,duplicate_reviews=deduplicate_review_witnesses(rows)
    anchors=[]
    if prior:
        rows,anchors=restore_matching_anchors(rows,prior)
        for c in rows:
            # A new confident model answer cannot silently settle a prior conflict.
            known=[o.get('unresolved') for o in prior if o.get('unresolved') and min(c['end'],o['end'])>max(c['start'],o['start'])]
            if known:c['unresolved']='; '.join(dict.fromkeys(([c['unresolved']] if c.get('unresolved') else [])+known))
    # Approximate model boundaries are insufficient evidence for tail extension.
    safe=[]
    for c in rows:
        cc=copy.deepcopy(c)
        if (cut_scope_end is not None and cc['end']>cut_scope_end) or 'approximate' in cc.get('timingEvidence',''):cc['timingEvidence']=''
        safe.append(cc)
    extended,tails=extend_tails(safe,cuts,rate=str(fps),scope_end=duration)
    for c,before in zip(extended,rows):c['timingEvidence']=before.get('timingEvidence','')
    state=copy.deepcopy(state);state['standard']=extended;state['sdh']=copy.deepcopy(extended)
    state['sourceManifest']={k:{c['sourceGroup']:c['sourceText']for c in state[k] if c.get('sourceText')}for k in ['standard','sdh']}
    state['revision']='Independent audio/script review'
    state['release']={'content_verified':False,'blockers':['Independent model audio/picture/script pass completed; remaining timing, lyrics and reading-speed conflicts need review. System sound decisions are not human approval.']}
    for k in ['standard','sdh']:
        if audit(state[k],state['sourceManifest'][k]):raise ValueError('Post-review formatting changed source words')
    from layout_policy import prepare
    state=prepare(state)
    return state,{'cue_reviews':cue_verdicts,'sound_reviews':sounds,'changes':ledger,'anchor_restorations':anchors,'tail_extensions':tails,'duplicate_review_witnesses':duplicate_reviews}
