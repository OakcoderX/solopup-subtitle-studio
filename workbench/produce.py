"""Build an isolated, unapproved episode draft from cached audio evidence."""
import argparse,copy,csv,json,math,re,subprocess,sys,time
from pathlib import Path
from timed_text import check
from server import write_srt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from character_lookup import extract
from character_lookup import script_text
from song_lookup import match as match_songs
from script_compare import compare as compare_script
from fidelity import words
from scope import validate as validate_scope
from history import record

def same_boundary_witness(a,b):
    """Deduplicate punctuation-only variants from different overlapping chunks."""
    return (a['evidence']!=b['evidence'] and a['kind']==b['kind']
            and words(a['text'])==words(b['text']) and bool(words(a['text']))
            and min(a['end'],b['end'])-max(a['start'],b['start'])
                >= .5*min(a['end']-a['start'],b['end']-b['start']))

def atomic(path, value):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));tmp.replace(path)

from layout_policy import wrap

def assemble(files, fps, duration):
    speech=[];sounds=[];uncertain=[]
    for path in sorted(files):
        data=json.loads(path.read_text());off=data['offset_seconds'];parsed=data['parsed']
        for group,target,textkey in [('speech_segments',speech,'text'),('sound_events',sounds,'description'),('uncertain_speech',uncertain,'heard')]:
            for c in parsed.get(group,[]):
                relative_start=float(c['start']);relative_end=float(c['end'])
                clip_end=float(data.get('end_seconds',duration))
                if not all(math.isfinite(x) for x in (relative_start,relative_end,clip_end)) or not 0<=relative_start<relative_end<=clip_end-off:
                    raise ValueError('Model timestamp outside supplied audio clip: '+path.name)
                start=off+relative_start;end=off+relative_end;text=str(c.get(textkey,'')).strip()
                if not text or end<=start:continue
                # Only identical overlapping witnesses are deduplicated. Conflicts remain for review.
                item={'start':start,'end':end,'text':text,'kind':c.get('kind','speech'),'evidence':path.name}
                duplicate=next((x for x in target if (x['text']==text and min(end,x['end'])>max(start,x['start'])) or (group=='speech_segments' and same_boundary_witness(x,item))),None)
                if duplicate is not None:
                    duplicate.setdefault('boundaryWitnesses',[]).append(item);continue
                target.append(item)
    speech.sort(key=lambda c:(c['start'],c['end']));sounds.sort(key=lambda c:c['start'])
    rows=[]
    for i,c in enumerate(speech):
        cue={'id':f'D{i+1:04d}','start':round(c['start']*fps)/fps,'end':round(c['end']*fps)/fps,
             'text':wrap(('♪ '+c['text']+' ♪') if c['kind']=='song' else c['text']),
             'sourceText':c['text'],'sourceGroup':f'D{i+1:04d}',
             'sourceEvidence':'Machine transcript pending audiovisual review: '+c['evidence'],
             'audioStart':c['start'],'audioEnd':c['end'],'timingEvidence':'Qwen approximate timing; not forced alignment',
             'checked':False,'italic':c['kind']=='song','kind':c['kind'],'region':'bottom'}
        if c.get('boundaryWitnesses'):cue['boundaryWitnesses']=c['boundaryWitnesses']
        if cue['end']<=cue['start']:cue['end']=cue['start']+1/fps
        if any(min(c['end'],u['end'])>max(c['start'],u['start']) for u in uncertain):cue['unresolved']='Recognition uncertainty: compare original audio.'
        if i and c['start']<speech[i-1]['end']:cue['unresolved']='Overlapping recognition witnesses: reconcile against original audio.'
        rows.append(cue)
    return rows,sounds

def main():
    p=argparse.ArgumentParser();p.add_argument('--video',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--series',type=Path,required=True);p.add_argument('--script',type=Path);p.add_argument('--key-zip',type=Path);a=p.parse_args()
    out=a.output;out.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((out/'production_config.json').read_text()) if (out/'production_config.json').exists() else {}
    project_policy=cfg.get('projectSettings') or (json.loads((a.series/'project.json').read_text()) if (a.series/'project.json').exists() else {})
    if project_policy.get('workflow')=='bilingual':
        from localization import run
        return run(a.video,out,project_policy,cfg,a.script)
    if (out/'workbench_state.json').exists():return 0
    started=time.time()
    last_stage=[None]
    def progress(stage,**kw):
        atomic(out/'progress.json',{'stage':stage,**kw})
        if stage!=last_stage[0]:
            record(out,'stage_started',reason='Production stage entered',details={'stage':stage,'elapsed_seconds':time.time()-started});last_stage[0]=stage
    try:
        progress('prepare')
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=r_frame_rate,codec_type','-of','json',str(a.video)]))
        duration=float(probe['format']['duration']);rate=next(x['r_frame_rate']for x in probe['streams']if x['codec_type']=='video')
        num,den=map(int,rate.split('/'));fps=num/den
        config=json.loads((out/'production_config.json').read_text()) if (out/'production_config.json').exists() else {}
        series_config=config.get('projectSettings') or (json.loads((a.series/'project.json').read_text()) if (a.series/'project.json').exists() else {})
        if series_config.get('targetLanguage','en-US') not in {'en-US','en-GB'}:raise ValueError('English production only; target language profile unsupported.')
        scope=validate_scope(config.get('scope'),duration);scope_start,scope_end=scope['start'],scope['end']
        record(out,'scope_confirmed',after=scope,reason='Explicit full-video or user-selected range; absolute video timecodes retained.')
        names=out/'character_lookup.md'
        shared_names=a.series/'character_lookup.md'
        if shared_names.exists():names.write_text(shared_names.read_text())
        if a.script:extract(a.script,names)
        from song_library import identify as identify_songs, apply as apply_songs
        song_library=a.series/'songs'
        song_recordings={'matches':[]}
        if (song_library/'registry.json').exists():
            progress('identifying_fixed_songs')
            song_recordings=identify_songs(a.video,song_library)
            song_recordings['matches']=[m for m in song_recordings['matches'] if scope_start<=m['start'] and m['end']<=scope_end]
            atomic(out/'song_recording_matches.json',song_recordings)
        evidence=out/'evidence';evidence.mkdir(exist_ok=True)
        command=[sys.executable,str(ROOT/'scripts/qwen_transcribe.py'),str(a.video),str(evidence),'--workers','3','--start',str(scope_start),'--end',str(scope_end)]
        if names.exists():command+=['--names',str(names)]
        if song_recordings['matches']:command+=['--song-matches',str(out/'song_recording_matches.json')]
        if a.key_zip:command+=['--key-zip',str(a.key_zip)]
        total=math.ceil((scope_end-scope_start)/28)
        transcription_started=time.time();proc=subprocess.Popen(command)
        while proc.poll() is None:
            progress('transcribing',completed=len(list(evidence.glob('qwen_*.json'))),total=total)
            time.sleep(.5)
        if proc.returncode:
            extraction_errors=[p for p in evidence.glob('audio_extraction_error_*.json') if p.stat().st_mtime>=transcription_started]
            if extraction_errors:
                err=json.loads(extraction_errors[0].read_text())
                raise RuntimeError(f"Original audio extraction/decoding failed at {err['start']:.3f}–{err['end']:.3f}s. Successful chunks retained. Decoder evidence: {err['decoder_log']}")
            raise RuntimeError('Transcription did not complete; successful chunks and worker diagnostics retained. Review provider or evidence errors before retrying.')
        progress('formatting')
        files=list(evidence.glob('qwen_*.json'))
        if len(files)!=total:raise RuntimeError('Incomplete evidence coverage; retry missing chunks.')
        rows,sounds=assemble(files,fps,duration)
        rows,_,song_changes=apply_songs(rows,{c['sourceGroup']:c['sourceText'] for c in rows},song_recordings,fps)
        record(out,'song_masters_reused',reason='Original audio fingerprint locates this episode; fixed words retained, unresolved master issues stay open.',details={'changes':song_changes})
        if not rows and not sounds:raise RuntimeError('No speech or sound recognized. Review the input audio before retrying.')
        if a.script:
            progress('script_comparison')
            atomic(out/'script_comparison.json',compare_script(rows,script_text(a.script)))
        progress('sound_clips',completed=0,total=len(sounds))
        clips=out/'clips';clips.mkdir(exist_ok=True);candidates=[]
        for i,s in enumerate(sounds,1):
            start=max(0,s['start']-2);end=min(duration,s['end']+2);clip=clips/f'{i:04d}.mp3'
            if not clip.exists():subprocess.run(['ffmpeg','-v','error','-ss',str(start),'-i',str(a.video),'-t',str(end-start),'-vn','-ac','1','-ar','24000','-b:a','64k','-y',str(clip)],check=True)
            text=s['text'];text=text if text.startswith('[') else '['+text+']'
            candidates.append(dict(start=s['start'],end=s['end'],caption=text,clip_file=f'clips/{clip.name}',clip_start=start,clip_end=end,
                                   selection_reason='Qwen audio candidate; visual context not reviewed',review_group='Audio candidate · review required'))
            progress('sound_clips',completed=i,total=len(sounds))
        fields=['start','end','caption','clip_file','clip_start','clip_end','selection_reason','review_group']
        with (out/'SDH_Sound_Candidates.csv').open('w',encoding='utf-8-sig',newline='')as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(candidates)
        state={'reviewPolicy':series_config.get('reviewPolicy',{}),'preferredSpellings':series_config.get('preferredSpellings',{}),'standard':rows,'sdh':copy.deepcopy(rows),'subtitleSpec':series_config.get('subtitleSpec','prime'),'targetLanguage':series_config.get('targetLanguage','en-US'),'projectSettings':series_config,'frameRate':rate,
               'scope':[scope_start,scope_end],'revision':'Machine draft '+time.strftime('%Y-%m-%d %H:%M'),
               'pipeline':{'recognition':True,'script_text_compared':bool(a.script),'boundary_reconciliation':False,'word_alignment':False,'sound_editorial_review':False,'stage':'first_pass'},
               'release':{'content_verified':False,'blockers':['Machine draft: verify speech, timing, SDH candidates and recipient delivery requirements.']},
               'sourceManifest':{k:{c['sourceGroup']:c['sourceText']for c in rows}for k in ['standard','sdh']}}
        state['songLibrary']=song_recordings
        previous=out/'first_pass/workbench_state.json'
        if previous.exists():
            prior=json.loads(previous.read_text())
            # A wall-clock label must not invalidate identical model evidence on retry.
            if prior.get('standard')==state['standard'] and prior.get('scope')==state['scope']:
                state['revision']=prior.get('revision',state['revision'])
                if prior.get('songLibrary',{}).get('matches',[])==song_recordings['matches']:
                    state['songLibrary']=prior.get('songLibrary',song_recordings)
        record(out,'first_pass_created',after=state,reason='Raw machine transcript retained before independent review.')
        from finish_pipeline import run as finish
        checkpoint=out/'repair_input.json'
        if checkpoint.exists() and previous.exists() and prior.get('standard')==state['standard'] and prior.get('scope')==state['scope']:
            policy=state['reviewPolicy'];state=json.loads(checkpoint.read_text());state['reviewPolicy']=policy
            record(out,'post_review_checkpoint_resumed',reason='Identical first-pass captions and source scope; reuse completed audio/timing review, resume repair.')
        else:
            state=finish(a.video,out,state,script_text(a.script) if a.script else '',fps,rate,duration,progress,a.key_zip)
        song_reference=a.series/'song_lookup.md'
        if song_reference.exists():
            (out/'song_lookup.md').write_text(song_reference.read_text())
            atomic(out/'song_matches.json',match_songs(state['standard'],out/'song_lookup.md'))
            record(out,'song_reference_compared',reason='Project song concordance created; original words retained; candidate timing is not approval.')
        from repair_pipeline import run as repair
        state=repair(a.video,out,state,progress,a.key_zip)
        # Reconcile against the locked master after AI review; a model cannot
        # silently rewrite a matched recording. All replacements retain history.
        for track in ('standard','sdh'):
            state[track],state['sourceManifest'][track],changes=apply_songs(state[track],state['sourceManifest'][track],song_recordings,fps)
            record(out,'song_master_final_reconciliation',reason='Fixed recording wording restored after review; episode time measured from PCM.',details={'track':track,'changes':changes})
        state['songLibrary']=song_recordings
        from song_library import repair_short_exposures
        cuts=[float(x) for x in re.findall(r'pts_time:([\d.]+)',(out/'scene_changes.txt').read_text())]
        for track in ('standard','sdh'):
            state[track],changes=repair_short_exposures(state[track],cuts,rate,scope_end)
            record(out,'song_master_exposure_checked',reason='Minimum display time checked after final master reuse; original audio and words preserved.',details={'track':track,'changes':changes})
        from layout_policy import prepare
        state=prepare(state)
        # Refresh screenplay comparison after reconciliation and song-master
        # reuse. The early first-pass comparison is evidence, not the final
        # caption set that is exported.
        if a.script:
            state['scriptComparison']=compare_script(state['standard'],script_text(a.script))
            atomic(out/'script_comparison.json',state['scriptComparison'])
            record(out,'final_script_comparison',reason='Compared post-review, post-song-master captions; screenplay remains reference only.',details={'cues':len(state['scriptComparison'])})
        progress('checking')
        from quality_gate import report
        from timed_text import write_itt
        atomic(out/'quality_gate.json',report(state,duration))
        for track in ('standard','sdh'):write_itt(state[track],out/f'REVIEW_DRAFT_{track}.itt',rate,state.get('targetLanguage','en-US'))
        atomic(out/'preflight.json',{k:check(state[k],rate,duration,state['sourceManifest'][k],state.get('reviewPolicy',{}).get('songSpeedAdvisory',False),state.get('preferredSpellings'),__import__('project_policy').profile(state))for k in ['standard','sdh']})
        # A published or manually created review is never silently replaced on retry.
        if not (out/'workbench_state.json').exists():
            for k in ['standard','sdh']:write_srt(state[k],out/f"{state.get('targetLanguage','en-US')}_{k}.srt")
            atomic(out/'workbench_state.json',state)
            record(out,'review_draft_published',after=state,reason='All required automatic stages executed; unresolved findings remain visible and final delivery blocked.')
            atomic(out/'run_summary.json',{'elapsed_seconds':time.time()-started,'scope':state['scope'],'pipeline':state['pipeline'],'cue_count':len(state['standard']),'human_approved':False})
        (out/'error.json').unlink(missing_ok=True)
        progress('review',completed=total,total=total)
        return 0
    except Exception as exc:
        import traceback
        traceback.print_exc()
        message=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__+': '+str(exc)[:300]
        atomic(out/'error.json',{'error':message});record(out,'production_failed',reason=message);return 1
if __name__=='__main__':sys.exit(main())
