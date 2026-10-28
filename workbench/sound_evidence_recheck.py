"""Second original-audio/picture witness for pending sound necessity decisions.

Publishes only agreement on unchanged labels and acoustic anchors. Disagreement
is an explicit task, never a vote or human approval. A finite CLI can be resumed.
"""
import argparse,base64,concurrent.futures,copy,csv,hashlib,json,os,subprocess,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from qwen_client import call_json
from audio_clip import extract_clip
from evidence_gate import SOUND_PROMPT,evidence_flags,signature
from quality_gate import report
from history import record
from timed_text import write_itt
from server import write_srt
PROMPT='''Independently listen to the ORIGINAL audio and inspect sampled frames.
Existing sound labels are hypotheses, not approved captions. For EACH supplied
ID assess whether its omission loses specific story, emotional, or comprehension
information. Routine visible Foley, redundant vocalizations, generic underscore
and music already described by sung lyrics need not be captioned. Never infer a
sound from pictures. Do not rewrite dialogue, lyrics or names. No optimization
for reading speed. Return only JSON {"reviews":[{"id":"...","decision":
"KEEP|REVISE|REMOVE","caption":"[short lowercase caption]","uncertain":false,
"audio_evidence":"what is actually audible","picture_evidence":"what the
sample shows, or insufficient","narrative_value":"specific information lost",
"visual_redundancy":"yes|no|insufficient","reason":"specific reasoning"}]}.
Return all IDs exactly once. If uncertain mark uncertain=true. Absolute candidate
acoustic bounds are provided; do not invent a new onset/end. Samples are not
continuous video. This is machine evidence, not human approval.'''+SOUND_PROMPT

def validate(parsed,ids):
    rows=parsed.get('reviews') if isinstance(parsed,dict) else None
    if not isinstance(rows,list):raise ValueError('Missing reviews array')
    got=[str(r.get('id')) for r in rows]
    if len(set(got))!=len(got) or set(got)!=set(ids):raise ValueError('Incomplete/duplicate sound IDs')
    for r in rows:
        if r.get('decision') not in {'KEEP','REVISE','REMOVE'} or not isinstance(r.get('uncertain'),bool):raise ValueError('Invalid decision/uncertainty')
        for key in ('caption','audio_evidence','picture_evidence','narrative_value','reason'):
            if not isinstance(r.get(key),str):raise ValueError('Missing '+key)
    return rows

def apply_agreements(state,decisions,candidates,results):
    out=copy.deepcopy(state);updated=copy.deepcopy(decisions);ledger=[];tasks=[]
    for ident,(proposal,evidence,clip) in results.items():
        d=updated.get(ident,{})
        if d.get('humanApproved') or d.get('uncertain') or d.get('confirmedPrior'):continue
        cues=[c for c in out['sdh'] if str(c.get('sourceSoundId'))==ident]
        if len(cues)!=1 or cues[0].get('checked') or cues[0].get('crossModalConflicts'):continue
        c=cues[0];row=candidates[int(ident)-1]
        # First witness must be an actual stored original-audio review.
        prior=Path(d.get('evidence',''))
        if not prior.is_file() or not d.get('audioEvidence') or str(prior)==str(evidence):continue
        same=(proposal['decision']==d.get('status') and proposal['caption'].strip()==c['text'].strip()
              and proposal['caption'].strip()==d.get('caption','').strip())
        third=proposal.get('adjudication') or {}
        settled=(not third.get('uncertain',True) and not proposal['uncertain']
                 and third.get('decision')==proposal['decision']
                 and (third['decision']=='REMOVE' or third.get('caption','').strip()==proposal['caption'].strip())
                 and bool(third.get('audio_evidence')) and bool(third.get('reason')))
        if settled and third['decision']=='REMOVE':
            out['sdh']=[x for x in out['sdh'] if x is not c]
            d.update(status='REMOVE',uncertain=False,humanApproved=False,reviewer='assistant',
                     removalAdjudication={'prior':copy.deepcopy(decisions[ident]),'second':proposal,
                                           'third':third,'evidence':[str(evidence),proposal['adjudication_evidence']]})
            ledger.append({'id':c['id'],'candidate':ident,'removed':True,
                           'reason':'Explicit third original-audio/picture adjudication resolves prior editorial inclusion disagreement',
                           'evidence':d['removalAdjudication']['evidence']})
            continue
        if settled and third['decision'] in {'KEEP','REVISE'}:
            label=third['caption'].strip()
            if not (label.startswith('[') and label.endswith(']')):settled=False
            else:
                if label!=c['text'] and c.get('speedReview'):c['speedReview'].update(accepted=False,invalidated=True)
                c['text']=label;d.update(status=third['decision'],caption=label)
                same=True
        if proposal['uncertain'] or not same:
            tasks.append({'id':c['id'],'start':c['start'],'end':c['end'],'cue_ids':[c['id']],
                          'action':'sound_necessity_disagreement','proposal':proposal,'evidence':str(evidence)})
            continue
        if not proposal['audio_evidence'].strip() or not proposal['narrative_value'].strip():continue
        sem={'status':'machine_reviewed','caption':c['text'],'decision':d['status'],
             'start':float(row['start']),'end':float(row['end']),
             'audioEvidence':proposal['audio_evidence'],'pictureEvidence':proposal['picture_evidence'],
             'narrativeValue':proposal['narrative_value'],'visualRedundancy':proposal.get('visual_redundancy','insufficient'),
             'evidence':([str(evidence),proposal['adjudication_evidence']] if settled else [str(prior),str(evidence)]),
             'clip':clip,'uncertain':False,'humanApproved':False}
        probe=dict(c,semanticReview=sem,sourceDecision=dict(d,semanticReview=sem))
        if any(f!='review_evidence_stale' for f in evidence_flags(probe)):continue
        # Only clear the obsolete generic candidate notice. Specific doubts stay.
        c['unresolved']=c.get('unresolved','').replace('SDH 系统建议，待视听确认。','').strip()
        c['semanticReview']=sem;c['reviewState']='machine_reviewed_not_human_approved'
        d['semanticReview']=copy.deepcopy(sem);c['sourceDecision']=copy.deepcopy(d)
        # An unchanged sound label with a fresh full-bound witness can be rebound.
        c.pop('reviewInvalidated',None);c['reviewBinding']=signature(c)
        c['checked']=False
        ledger.append({'id':c['id'],'candidate':ident,'evidence':sem['evidence'],
                       'reason':'Two stored original-audio/picture reviews agree on unchanged sound meaning and bounds; no human approval'})
    # A partial window or failed response must not erase doubts in other
    # windows. Replace only tasks explicitly settled or reassessed this round.
    handled={x['id'] for x in ledger+tasks}
    retained=[copy.deepcopy(t) for t in state.get('soundEvidenceRecheckTasks',[])
              if t.get('id') not in handled]
    tasks=retained+tasks
    out['soundEvidenceRecheckTasks']=tasks
    out.setdefault('release',{})['content_verified']=False
    return out,updated,ledger,tasks

def main():
    p=argparse.ArgumentParser();p.add_argument('--episode',type=Path,required=True)
    p.add_argument('--video',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--key-zip',type=Path)
    p.add_argument('--workers',type=int,default=3);p.add_argument('--only',type=int);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True);target=a.episode/'workbench_state.json';decisionfile=a.episode/'sound_review_state.json'
    # A disconnected source volume is one batch-level dependency, not dozens
    # of transcription failures. Wait without sending any provider requests.
    waitfile=a.output/'waiting_for_media.json';deadline=time.monotonic()+3500
    while not a.video.is_file():
        waitfile.write_text(json.dumps({'status':'waiting_for_media','video':str(a.video),
                                       'reason':'Source volume/file unavailable; no provider requests sent'}))
        if time.monotonic()>deadline:raise FileNotFoundError('Source media still unavailable; successful evidence retained')
        time.sleep(20)
    waitfile.unlink(missing_ok=True)
    saved=target.read_bytes();dsaved=decisionfile.read_bytes();state=json.loads(saved);decisions=json.loads(dsaved)
    candidates=list(csv.DictReader((a.episode/'SDH_Sound_Candidates.csv').open(encoding='utf-8-sig')))
    needs=[c for c in state['sdh'] if c.get('kind')=='sound' and not c.get('checked')
           and ('SDH 系统建议' in c.get('unresolved','') or evidence_flags(c))]
    windows=sorted({int(c['start']//60)*60 for c in needs})
    if a.only is not None:windows=[t for t in windows if t==a.only]
    key=os.environ.get('QWEN_API_KEY') or os.environ.get('DASHSCOPE_API_KEY')
    if not key and (ROOT/'config/team_api_key').exists():key=(ROOT/'config/team_api_key').read_text().strip()
    if not key and a.key_zip:
        with zipfile.ZipFile(a.key_zip) as z:key=z.read(next(n for n in z.namelist() if n.endswith('/config/team_api_key'))).decode().strip()
    if not key:raise ValueError('No configured provider credential')
    url=__import__('provider_config').base_url().rstrip('/')+'/chat/completions'
    names=(a.episode/'character_lookup.md').read_text() if (a.episode/'character_lookup.md').exists() else ''
    experience=a.episode/'project_notes.md'
    knowledge=experience.read_text() if experience.exists() else ''
    script_reference=''
    script_report=a.episode/'script_sources.json'
    if script_report.exists():
        from character_lookup import script_text
        script_reference='\n\n'.join(script_text(Path(x['path'])) for x in json.loads(script_report.read_text())['sources'])
    def run(start):
        own=[c for c in needs if int(c['start']//60)*60==start]
        refs=[{'id':str(c['sourceSoundId']),'caption':c['text'],
               'start':float(candidates[int(c['sourceSoundId'])-1]['start']),
               'end':float(candidates[int(c['sourceSoundId'])-1]['end'])} for c in own if c.get('sourceSoundId')]
        if not refs:return None
        off=max(state['scope'][0],min(r['start'] for r in refs)-2)
        end=min(state['scope'][1],max(r['end'] for r in refs)+2)
        context={'audio_offset':off,'audio_end':end,'sounds':refs,'character_registry':names,
                 'project_knowledge':knowledge,'earlier_script_not_acoustic_evidence':script_reference}
        stamp=hashlib.sha256(json.dumps([PROMPT,context,str(a.video),a.video.stat().st_mtime_ns],sort_keys=True).encode()).hexdigest()
        dest=a.output/f'sounds_{start:04d}.json'
        cached=None
        if dest.exists():
            d=json.loads(dest.read_text())
            if d.get('fingerprint')==stamp:validate(d['parsed'],[r['id'] for r in refs]);cached=d
        audio=a.output/f'audio_{start:04d}.mp3'
        extract_clip(a.video,off,end,audio)
        content=[{'type':'input_audio','input_audio':{'data':'data:audio/mpeg;base64,'+base64.b64encode(audio.read_bytes()).decode(),'format':'mp3'}}]
        times=sorted({(r['start']+r['end'])/2 for r in refs})
        if len(times)>8:times=[times[round(i*(len(times)-1)/7)] for i in range(8)]
        for i,t in enumerate(times):
            frame=a.output/f'frame_{start:04d}_{i}.jpg'
            subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',str(a.video),'-frames:v','1','-vf','scale=384:-2','-q:v','5','-y',str(frame)],check=True)
            content.extend([{'type':'text','text':f'Sampled picture at absolute {t:.3f} seconds'},
                            {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(frame.read_bytes()).decode()}}])
        content.append({'type':'text','text':PROMPT+'\n'+json.dumps(context,ensure_ascii=False)})
        if cached:proposal=cached;parsed=cached['parsed']
        else:
            payload={'model':__import__('provider_config').model(),'modalities':['text'],'messages':[{'role':'user','content':content}]}
            for attempt in range(2):
                parsed,usage,raw=call_json(url,key,payload)
                proposal={'fingerprint':stamp,'parsed':parsed,'raw':raw,'usage':usage,'clip':[off,end],'picture_times':times,'humanApproved':False}
                (a.output/f'proposal_{start:04d}.json').write_text(json.dumps(proposal,ensure_ascii=False,indent=2))
                (a.output/f'proposal_{start:04d}_attempt_{attempt}.json').write_text(json.dumps(proposal,ensure_ascii=False,indent=2))
                try:validate(parsed,[r['id'] for r in refs]);break
                except ValueError as exc:
                    if attempt==1:raise
                    payload['messages'].append({'role':'user','content':'The response failed schema validation: '+str(exc)+'. Return the complete reviews array for every supplied ID. decision must be KEEP/REVISE/REMOVE. uncertain must explicitly be JSON true or false, never null or omitted. Re-listen to the same original audio and retain genuine uncertainty; do not turn null into false just to pass validation.'})
        disagreements=[r for r in parsed['reviews'] if not r['uncertain'] and
                       (r['decision']!=decisions.get(str(r['id']),{}).get('status') or
                        r['caption'].strip()!=decisions.get(str(r['id']),{}).get('caption','').strip())]
        if disagreements:
            thirdfile=a.output/f'adjudication_{start:04d}.json'
            comparison={'disputed':disagreements,'earlier_decisions':{r['id']:decisions.get(str(r['id']),{}) for r in disagreements}}
            thirdstamp=hashlib.sha256(json.dumps([stamp,comparison],sort_keys=True).encode()).hexdigest()
            third=None
            if thirdfile.exists():
                third=json.loads(thirdfile.read_text())
                if third.get('fingerprint')!=thirdstamp:third=None
            if third is None:
                instruction='Explicitly adjudicate these prior editorial disagreements against the SAME ORIGINAL AUDIO and sampled pictures. Do not vote or defer to earlier models. Explain the specific audible and story evidence that supports or rejects the earlier reasoning. Keep significant unseen sounds, danger/weather cues and meaningful reactions. Do not delete something just because it is short, visible, fast, or convenient. Return the same reviews schema only for disputed IDs. If the disagreement cannot be resolved mark uncertain=true. Do not transcribe or revise lyrics or dialogue. If KEEP/REVISE return a concise lowercase bracketed caption. If REMOVE explain why no narrative/emotional/comprehension information is lost. '+SOUND_PROMPT
                schema='Return JSON {"reviews":[{"id":"...","decision":"KEEP|REVISE|REMOVE","caption":"[concise label]","uncertain":false,"audio_evidence":"specific audible event","picture_evidence":"sample facts or insufficient","narrative_value":"information lost or why none","reason":"specific resolution"}]}. Return only these IDs: '+json.dumps([r['id'] for r in disagreements])
                thirdcontent=copy.deepcopy(content[:-1])+[{'type':'text','text':instruction+'\n'+schema+'\n'+json.dumps({'context':context,'disagreements':comparison},ensure_ascii=False)}]
                payload={'model':__import__('provider_config').model(),'modalities':['text'],'messages':[{'role':'user','content':thirdcontent}]}
                for attempt in range(2):
                    tp,tu,tr=call_json(url,key,payload)
                    third={'fingerprint':thirdstamp,'parsed':tp,'raw':tr,'usage':tu,'humanApproved':False}
                    (a.output/f'adjudication_proposal_{start:04d}_{attempt}.json').write_text(json.dumps(third,ensure_ascii=False,indent=2))
                    try:validate(tp,[r['id'] for r in disagreements]);break
                    except ValueError as exc:
                        if attempt==1:raise
                        payload['messages'].append({'role':'user','content':'Schema validation failed: '+str(exc)+'. Re-listen; preserve genuine uncertainty. '+schema})
                thirdfile.write_text(json.dumps(third,ensure_ascii=False,indent=2))
            adjudicated={str(r['id']):r for r in third['parsed']['reviews']}
            for r in parsed['reviews']:
                if str(r['id']) in adjudicated:r.update(adjudication=adjudicated[str(r['id'])],adjudication_evidence=str(thirdfile))
        dest.write_text(json.dumps(proposal,ensure_ascii=False,indent=2));print(dest.name,flush=True);return dest
    results={};errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(run,t):t for t in windows}
        for future in concurrent.futures.as_completed(futures):
            try:
                f=future.result()
                if f:
                    d=json.loads(f.read_text())
                    for r in d['parsed']['reviews']:results[str(r['id'])]=(r,f,d['clip'])
            except Exception as exc:errors.append({'window':futures[future],'type':type(exc).__name__,'message':str(exc)[:300]})
    candidate,decisions,ledger,tasks=apply_agreements(state,decisions,candidates,results)
    q=report(candidate,candidate['scope'][1])
    # State and decision tokens guard a user saving while requests were running.
    if target.read_bytes()!=saved or decisionfile.read_bytes()!=dsaved:raise RuntimeError('Live revision changed; proposals retained, no publication')
    if ledger or tasks:
        record(a.episode,'sound_evidence_recheck',state,candidate,actor='assistant',reason='Original audio and sampled picture second witness; only unchanged agreements resolved',details={'output':str(a.output),'resolved':len(ledger),'disagreements':len(tasks)})
        for path,value in [(target,candidate),(decisionfile,decisions),(a.episode/'quality_gate.json',q)]:
            tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));tmp.replace(path)
        write_itt(candidate['sdh'],a.episode/'REVIEW_DRAFT_sdh.itt',candidate['frameRate'],candidate.get('targetLanguage','en-US'))
        write_srt(candidate['sdh'],a.episode/f"{candidate.get('targetLanguage','en-US')}_sdh.srt")
    summary={'resolved':len(ledger),'disagreements':len(tasks),'errors':errors,'status':q['status'],'elapsed_scope':'second witness only; no final approval'}
    (a.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
