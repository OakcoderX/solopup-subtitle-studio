"""Mandatory post-ASR production stages, including explicit incomplete-evidence gates."""
import copy,csv,json,os,re,subprocess,sys,time
from pathlib import Path
from history import record
from confirmed_sounds import media_key,inherit
from sdh_track import compose as compose_sdh
from reconcile_review import reconcile
from timing_review import align
from tail_room import extend_tails
from timed_text import check
from fidelity import audit,words
ROOT=Path(__file__).resolve().parents[1]

def review_worker_count():
    """Allow a bounded concurrency override for unstable Qwen endpoints."""
    try:value=int(os.environ.get('SDH_REVIEW_WORKERS','3'))
    except ValueError:value=3
    return max(1,min(4,value))

def expected_window_coverage(state,start,end,duration,sounds):
    """Use the identical ownership window as review_pass for coverage retries."""
    from review_window import complete_window
    _,_,cues=complete_window(state.get('standard',[]),start,end,duration)
    cue_ids={str(c['id']) for c in cues}
    sound_ids={str(i) for i,c in enumerate(sounds,1) if start<=float(c['start'])<end}
    return cue_ids,sound_ids

def run(video,out,state,script,fps,rate,duration,progress,key_zip=None):
    review=out/'review';review.mkdir(exist_ok=True);stage=out/'first_pass';stage.mkdir(exist_ok=True)
    raw=stage/'workbench_state.json';raw.write_text(json.dumps(state,ensure_ascii=False,indent=2));(stage/'SDH_Sound_Candidates.csv').write_bytes((out/'SDH_Sound_Candidates.csv').read_bytes())
    scriptfile=stage/'script.txt';scriptfile.write_text(script)
    confirmed_path=out.parent.parent/'confirmed_sounds'/(media_key(video)+'.json')
    confirmed=json.loads(confirmed_path.read_text()) if confirmed_path.exists() else []
    (stage/'confirmed_events.json').write_text(json.dumps(confirmed,ensure_ascii=False))
    # Overlap independent local timing work with network-bound audio review.
    witness=out/'word_timestamps.json'
    timing_log=None;timing_proc=None
    if not witness.exists():
        timing_log=(out/'alignment.log').open('a')
        timing_proc=subprocess.Popen([os.environ.get('SDH_ALIGN_PYTHON',sys.executable),str(ROOT/'scripts/timestamp_witness.py'),'--video',str(video),'--output',str(witness),'--start',str(state['scope'][0]),'--end',str(state['scope'][1])],stdout=timing_log,stderr=timing_log)
        record(out,'parallel_timing_started',reason='Independent local word timing overlaps Qwen network review; evidence remains separate.')
    progress('audio_review')
    cmd=[sys.executable,str(ROOT/'workbench/review_pass.py'),'--video',str(video),'--episode',str(stage),'--script-text',str(scriptfile),'--output',str(review),'--workers',str(review_worker_count()),'--granularity','episode']
    if key_zip:cmd+=['--key-zip',str(key_zip)]
    proc=subprocess.Popen(cmd)
    total=1
    while proc.poll() is None:
        progress('audio_review',completed=len(list(review.glob('review_????.json'))),total=total);time.sleep(.5)
    if proc.returncode:raise RuntimeError('Independent review failed; successful chunks are retained for retry.')
    # A parseable response can still omit candidates. Retry only incomplete cached windows.
    from review_pass import cache_valid
    for coverage_attempt in range(2):
        incomplete=[]
        sound_rows=list(csv.DictReader((out/'SDH_Sound_Candidates.csv').open(encoding='utf-8-sig')))
        for path in review.glob('review_????.json'):
            d=json.loads(path.read_text());start,end=d['interval']
            cue_ids,sound_ids=expected_window_coverage(state,start,end,duration,sound_rows)
            if not cache_valid(path,d.get('input_fingerprint'),cue_ids,sound_ids):incomplete.append(start)
        if not incomplete:break
        record(out,'review_coverage_retry',reason='Retry only omitted review evidence; completed windows are cached.',details={'windows':incomplete,'attempt':coverage_attempt+1})
        progress('audio_review_retry',completed=total-len(incomplete),total=total)
        if subprocess.run(cmd).returncode:raise RuntimeError('Review coverage retry failed; cached evidence retained.')
    files=list(review.glob('review_????.json'));reviews=[json.loads(p.read_text()) for p in files]
    missing_sounds=[dict(x,evidence=str(path)) for path,d in zip(files,reviews) for x in d['parsed'].get('missing_sounds',[])]
    (out/'missing_sound_candidates.json').write_text(json.dumps(missing_sounds,ensure_ascii=False,indent=2))
    originals={c['id'] for c in state['standard']};covered={r['id'] for d in reviews for r in d['parsed']['cue_reviews']}
    sound_count=len(list(csv.DictReader((out/'SDH_Sound_Candidates.csv').open(encoding='utf-8-sig'))));sound_ids={str(r['id']) for d in reviews for r in d['parsed']['sound_reviews']}
    if originals-covered or sound_ids!=set(map(str,range(1,sound_count+1))):raise RuntimeError('Independent review coverage incomplete; do not publish a review-ready draft. Retry missing review evidence.')
    progress('reconciling')
    revised,ledger=reconcile(state,files,prior=state['standard'],duration=duration,fps=fps)
    record(out,'audio_script_reconciled',state,revised,'Second original-audio plus sampled-picture pass; disagreements remain unresolved.',details={'coverage':len(originals),'evidence':'review/'})
    rows=revised['standard'];progress('word_timing')
    if timing_proc is not None:
        timing_proc.wait();timing_log.close()
    witness=out/'word_timestamps.json';align_python=os.environ.get('SDH_ALIGN_PYTHON',sys.executable);timing_status='unavailable'
    if not witness.exists():
        cmd=[align_python,str(ROOT/'scripts/timestamp_witness.py'),'--video',str(video),'--output',str(witness),'--start',str(state['scope'][0]),'--end',str(state['scope'][1])]
        with (out/'alignment.log').open('a') as log:
            result=subprocess.run(cmd,stdout=log,stderr=log)
        if result.returncode:record(out,'word_timing_unavailable',reason='Local word timestamp model/runtime unavailable. Approximate times remain explicitly unverified; no automatic extension.')
    if witness.exists():
        before_timing=copy.deepcopy(rows)
        rows,events=align(rows,json.loads(witness.read_text()),fps);ledger['word_timing']=events;timing_status='partial' if any(c.get('timingReview','').startswith('pending') for c in rows) else 'machine_matched'
        from layout_policy import resolve_long_cues
        rows,layout_changes=resolve_long_cues(rows,json.loads(witness.read_text()),rate)
        ledger['automatic_layout_splits']=layout_changes
        record(out,'word_timing_matched',before_timing,rows,details={'matched':len(events),'total':len(rows)},reason='Match exact caption words to an independent local time witness; never substitute its wording.')
    progress('scene_boundaries');scene=out/'scene_changes.txt'
    if not scene.exists():
        result=subprocess.run(['ffmpeg','-hide_banner','-i',str(video),'-vf',"scale=320:-2,select='gt(scene,0.3)',metadata=print",'-an','-f','null','-'],capture_output=True,text=True)
        if result.returncode:raise RuntimeError('Scene-boundary evidence failed; retry before timed review output')
        scene.write_text(result.stderr)
    cuts=[float(x) for x in re.findall(r'pts_time:([\d.]+)',scene.read_text())]
    safe=copy.deepcopy(rows)
    for c in safe:
        if c.get('timingReview')!='machine_word_matched':c['timingEvidence']=''
    progress('timing_check');extended,tails=extend_tails(safe,cuts,rate=rate,scope_end=state['scope'][1]);ledger['tail_extensions']=tails
    for c,previous in zip(extended,rows):
        c['timingEvidence']=previous.get('timingEvidence','')
        if c.get('timingReview')!='machine_word_matched':c['unresolved']=(c.get('unresolved','')+' 时间边界尚无逐词证据，需复核。').strip()
    record(out,'tail_room_applied',rows,extended,reason='Extend within measured audio tail, next cue, scene cut and scope limits; no lexical edits.',details={'evidence':'review_ledger.json','extensions':sum(x['added_frames']>0 for x in tails)})
    revised['standard']=extended;revised['sdh']=copy.deepcopy(extended)
    revised['sourceManifest']={k:{c.get('sourceGroup',c['id']):c.get('sourceText',c['text']) for c in extended} for k in ['standard','sdh']}
    if audit(extended,revised['sourceManifest']['standard']):raise RuntimeError('Word-preservation check failed; review output withheld')
    decisions={}
    for k,r in ledger['sound_reviews'].items():
        pending=bool(r.get('uncertain')) or r.get('confidence')=='low'
        decisions[k]={'status':'' if pending else r['decision'],'recommendation':r['decision'],'caption':r['caption'],'note':r.get('reason',''),'reviewer':'assistant','humanApproved':False,'reviewed':True,'uncertain':pending,'audioEvidence':r.get('audio_evidence'),'pictureEvidence':r.get('picture_evidence'),'evidence':r['evidence'],'narrativeValue':r.get('narrative_value'),'visualRedundancy':r.get('visual_redundancy')}
    decisions,conflicts=inherit(list(csv.DictReader((out/'SDH_Sound_Candidates.csv').open(encoding='utf-8-sig'))),decisions,confirmed)
    revised['confirmedSoundConflicts']=conflicts
    from missing_sounds import register as register_missing, persist as persist_missing
    sound_rows,decisions,missing_ledger=register_missing(list(csv.DictReader((out/'SDH_Sound_Candidates.csv').open(encoding='utf-8-sig'))),decisions,missing_sounds,duration)
    persist_missing(out,video,sound_rows)
    revised['missingSoundResolution']=missing_ledger
    (out/'missing_sound_resolution.json').write_text(json.dumps(missing_ledger,ensure_ascii=False,indent=2))
    (out/'sound_review_state.json').write_text(json.dumps(decisions,ensure_ascii=False,indent=2))
    record(out,'sound_candidates_judged',after=decisions,reason='Automatic editorial proposals from audio and sampled pictures; uncertain items remain pending, no human approval.')
    revised['pipeline']={'recognition':True,'script_text_compared':bool(script),'independent_audio_script_review':True,'boundary_reconciliation':True,'word_alignment':timing_status,'scene_boundaries':True,'tail_room_checked':True,'sound_editorial_review':True,'stage':'review_draft'}
    revised['release']={'content_verified':False,'blockers':['自动复核稿：仍需视听审核；系统声音建议不等于人工批准。','存在疑点或读速冲突时禁止最终交付。声音建议尚未合并进SDH。']+(['已确认声音存在跨版本冲突。'] if conflicts else [])+(['复核发现的漏标声音已加入声音判断，尚待裁决。'] if any(x['status'] in {'registered_pending','invalid_pending'} for x in missing_ledger) else [])}
    before_sdh=copy.deepcopy(revised)
    revised=compose_sdh(revised,list(csv.DictReader((out/'SDH_Sound_Candidates.csv').open(encoding='utf-8-sig'))),decisions,cuts)
    record(out,'sdh_draft_composed',before_sdh,revised,reason='Include decided KEEP/REVISE sound proposals in review SDH; unresolved candidates do not hide all other labels.')
    revised['revision']='Integrated pipeline review '+time.strftime('%Y-%m-%d %H:%M')
    (out/'review_ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2))
    # Suggestions are evidence-based proposals, never silently applied production cuts.
    speech=[c for c in extended if c.get('kind')!='song' and len(words(c['text']))>=5]
    if speech:
        suggestion={'status':'proposal_only','first_dialogue':speech[0]['start'],'last_dialogue':speech[-1]['end'],'start_candidates':[x for x in cuts if max(0,speech[0]['start']-20)<=x<=speech[0]['start']],'end_candidates':[x for x in cuts if speech[-1]['end']<=x<=speech[-1]['end']+20],'reason':'Dialogue and nearby scene boundaries only; titles/credits not independently identified. User must choose production scope.'}
        (out/'scope_suggestion.json').write_text(json.dumps(suggestion,indent=2))
    return revised
