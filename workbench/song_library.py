"""Versioned, audio-identified song masters. No fuzzy lyric replacement."""
import copy, hashlib, json, subprocess
from pathlib import Path
import numpy as np
RATE = 2000

def decode(video):
    raw = subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-vn','-ac','1','-ar',str(RATE),'-f','f32le','-'])
    return np.frombuffer(raw, dtype='<f4').astype(float)

def locate(template, target, rate=RATE):
    """Normalized PCM correlation plus per-block checks reject remixes/edits."""
    t = np.asarray(template, dtype=float); y = np.asarray(target, dtype=float)
    n = len(t)
    if n < rate or len(y) < n or np.std(t) < 1e-7:
        return None
    centered = t - t.mean(); size = 1 << (len(y)+n-2).bit_length()
    corr = np.fft.irfft(np.fft.rfft(y,size)*np.fft.rfft(centered[::-1],size),size)[n-1:len(y)]
    sums = np.r_[0,np.cumsum(y)]; squares = np.r_[0,np.cumsum(y*y)]
    energy = squares[n:]-squares[:-n]-(sums[n:]-sums[:-n])**2/n
    score = corr / np.sqrt(np.maximum(energy,1e-20)*np.dot(centered,centered))
    index = int(np.argmax(score)); selected = y[index:index+n]
    confidence = float(score[index]); fractional = 0.0
    # MP4 sample offsets need not land on the downsampled PCM grid. Refine phase,
    # never stretch time: otherwise the same recording can score only .90.
    pad = 32
    if index >= pad and index+n+pad <= len(y) and confidence >= .7:
        padded = y[index-pad:index+n+pad]
        spectrum = np.fft.rfft(padded); frequencies = np.fft.rfftfreq(len(padded))
        for shift in np.linspace(-.5,.5,41):
            shifted = np.fft.irfft(spectrum*np.exp(2j*np.pi*frequencies*shift),n=len(padded))[pad:-pad]
            value = float(np.corrcoef(t,shifted)[0,1])
            if value > confidence: confidence=value; fractional=float(shift); selected=shifted
    blocks = []
    for start in range(0,n,rate*2):
        a=t[start:start+rate*2]; b=selected[start:start+rate*2]
        if len(a)>=rate//2 and np.std(a)>1e-5 and np.std(b)>1e-5:
            blocks.append(float(np.corrcoef(a,b)[0,1]))
    weakest = min(blocks, default=0)
    return {'start':(index+fractional)/rate,'end':(index+fractional+n)/rate,'correlation':confidence,
            'weakest_block':weakest,'verified_same_recording':confidence>=.995 and weakest>=.98}

def identify(video, library, audio=None):
    library=Path(library); registry=json.loads((library/'registry.json').read_text())
    target=decode(video) if audio is None else audio; matches=[]; rejected=[]
    for master in registry['masters']:
        if not master.get('fingerprint'):continue
        path=library/master['fingerprint']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=master['fingerprint_sha256']:
            raise ValueError('Song fingerprint changed: '+master['id'])
        with np.load(path,allow_pickle=False) as data: template=data['pcm'].copy()
        remaining=target.copy()
        for occurrence in range(20):
            found=locate(template,remaining)
            if not found:break
            item={**found,'master_id':master['id'],'lyric_status':master['status'],
                  'master_digest':hashlib.sha256(json.dumps(master,sort_keys=True).encode()).hexdigest(),
                  'lines':copy.deepcopy(master['lines']),'issues':copy.deepcopy(master.get('issues',[]))}
            if not found['verified_same_recording']:
                if not occurrence:rejected.append(item)
                break
            matches.append(item)
            remaining[max(0,int(found['start']*RATE)):min(len(remaining),int(found['end']*RATE)+1)]=0
    return {'version':1,'library':str(library.resolve()),'matches':matches,'rejected':rejected,
            'human_approved':False,'method':'PCM correlation >= .995 and every 2-second block >= .98; edited mixes require a new version'}

def apply(rows, manifest, matches, fps=24):
    """Replace only complete locked recording spans, preserving unrelated cues.

    Masters carry acoustic line times relative to their own recording. Position is
    measured against THIS episode's PCM, never copied from another episode.
    """
    from layout_policy import wrap
    out=copy.deepcopy(rows); source=copy.deepcopy(manifest); changes=[]
    for m in matches['matches']:
        if m['lyric_status'] not in ('audio_verified','user_confirmed','audio_reviewed_pending'):continue
        a,b=m['start'],m['end']
        touched=[c for c in out if c.get('kind')!='sound' and c['start']<b and c['end']>a]
        if any(c['start']<a-.5 or c['end']>b+.5 for c in touched):
            changes.append({'master_id':m['master_id'],'status':'boundary_conflict'});continue
        # Never silently erase manually confirmed or unrelated dialogue.
        if any(c.get('checked') for c in touched):
            changes.append({'master_id':m['master_id'],'status':'manual_review_preserved'});continue
        # Legacy ASR times can put the spoken recipe answer inside a song.
        # Audio identity proves the master, not the old cue's guessed time.
        from fidelity import words
        master_words=words(' '.join(line['text'] for line in m['lines'] if line.get('kind')!='animal_effect'))
        unrelated=[]
        for cue in touched:
            if cue.get('kind')=='song':continue
            tokens=words(cue['text'])
            if not tokens or not any(master_words[i:i+len(tokens)]==tokens for i in range(len(master_words)-len(tokens)+1)):
                unrelated.append(cue['id'])
        if unrelated:
            changes.append({'master_id':m['master_id'],'status':'unmatched_dialogue_preserved','cue_ids':unrelated})
            continue
        groups={c.get('sourceGroup',c['id']) for c in touched}
        if any(c not in touched and c.get('sourceGroup',c['id']) in groups for c in out):
            changes.append({'master_id':m['master_id'],'status':'source_group_crosses_boundary'});continue
        out=[c for c in out if c not in touched]
        for g in groups:source.pop(g,None)
        for index,line in enumerate(m['lines'],1):
            if line.get('kind')=='animal_effect':continue
            key=f"SONG_{m['master_id']}_{round(a*fps)}_{index:02d}"
            sung=line.get('kind','song')=='song';text=line['text'];start=round((a+line['start'])*fps)/fps;end=round((a+line['end'])*fps)/fps
            cue={'id':key,'sourceGroup':key,'sourceText':text,'text':wrap(('♪ '+text+' ♪') if sung else text),
                 'start':start,'end':end,'audioStart':a+line['start'],'audioEnd':a+line['end'],
                 'kind':'song' if sung else 'speech','italic':sung,'region':'bottom','checked':False,
                 'songMaster':m['master_id'],'songMasterDigest':m['master_digest'],
                 'sourceEvidence':'Versioned original-audio song master; '+m['master_id'],
                 'timingEvidence':'This-episode PCM alignment to reviewed reference audio',
                 'songRecordingMatch':{k:m[k] for k in ('start','correlation','weakest_block')}}
            issues=[x for x in m.get('issues',[]) if (index == x.get('line_index',1))]
            if issues:cue['unresolved']='固定歌曲母版：'+'；'.join(x['text'] for x in issues)
            cue['songMasterStatus']=m['lyric_status']
            out.append(cue);source[key]=text
        changes.append({'master_id':m['master_id'],'status':'reused','replaced_ids':[c['id']for c in touched]})
    return sorted(out,key=lambda c:(c['start'],c['end'])),source,changes

def audit(rows, matches):
    """Validate whole ordered text, including repeats and missing last lines."""
    from fidelity import words
    issues=[]
    for m in matches['matches']:
        actual=[c for c in rows if c.get('songMaster')==m['master_id'] and m['start']<=c['start']<m['end']]
        if not actual:
            issues.append({'master_id':m['master_id'],'rule':'song_master_missing'})
            continue
        expected=words(' '.join(l['text']for l in m['lines'] if l.get('kind')!='animal_effect'))
        if words(' '.join(c['text']for c in sorted(actual,key=lambda c:c['start'])))!=expected:
            issues.append({'master_id':m['master_id'],'rule':'song_master_text_mismatch'})
    return issues


def repair_short_exposures(rows, cuts, rate=24, scope_end=None):
    """Master reuse still obeys minimum exposure; preserve original audio anchors.

    Apply only measured, non-regressing extensions to unconfirmed master cues.
    Song speed advisories never waive the 20-frame minimum.
    """
    from tail_room import extend_tails
    from display_repair import metrics
    from fractions import Fraction
    planned,ledger=extend_tails(rows,cuts,rate,scope_end,minimum_only=True)
    out=copy.deepcopy(rows);changes=[];fps=float(Fraction(str(rate)))
    for index,(old,new) in enumerate(zip(rows,planned)):
        if not old.get('songMaster') or old.get('checked') or new['end']==old['end']:continue
        before=metrics(out,fps);out[index]=new
        if any(a>b for a,b in zip(metrics(out,fps),before)):
            out[index]=copy.deepcopy(old);continue
        changes.append({'id':old['id'],'before_end':old['end'],'end':new['end'],
                        'reason':'Master exposure below 20 frames; measured tail and cut bounds; no screen regression'})
    return out,changes
