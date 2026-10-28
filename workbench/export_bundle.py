"""Read-only export snapshots with an explicit, single delivery-time offset."""
import copy
import hashlib
import io
import json
import re
import tempfile
import zipfile
from fractions import Fraction
from pathlib import Path
from quality_gate import report
from timed_text import write_itt


def select_latest(rows):
    groups={}
    for row in rows:
        match=re.search(r'\bEP\s*0*(\d+)',row.get('title',''),re.I)
        groups.setdefault('EP'+str(int(match[1])) if match else row['id'],[]).append(row)
    selected=[]
    for group in groups.values():
        production=[r for r in group if not re.search(r'烟测|smoke|计时测试|无人干预全集测试',r.get('title',''),re.I)]
        pool=production or group
        ready=[r for r in pool if r.get('status')=='ready']
        pool=ready or pool
        selected.append(max(pool,key=lambda r:(float(r.get('created') or 0),r['id'])))
    return sorted(selected,key=lambda r:(int(re.search(r'\bEP\s*0*(\d+)',r.get('title',''),re.I)[1]) if re.search(r'\bEP\s*0*(\d+)',r.get('title',''),re.I) else 100000,r['id']))


def shifted(rows, offset, rate):
    seconds=Fraction(str(offset))
    if not 0<=seconds<=3600:raise ValueError('Offset must be between 0 and 3600 seconds')
    frames=seconds*Fraction(str(rate))
    if frames.denominator!=1:raise ValueError('Offset does not land on a complete frame at this frame rate')
    out=copy.deepcopy(rows)
    for cue in out:
        cue['start']=float(Fraction(str(cue['start']))+seconds)
        cue['end']=float(Fraction(str(cue['end']))+seconds)
    return out


def srt_bytes(rows):
    def stamp(t):
        ms=round(float(t)*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
        return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
    return ('\n\n'.join(f'{i}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}' for i,c in enumerate(rows,1))+'\n').encode()


def bundle(episodes, tracks=('standard','sdh'), fmt='itt', offset='0'):
    if fmt not in {'itt','srt'}:raise ValueError('Unsupported export format')
    if not tracks or set(tracks)-{'standard','sdh'}:raise ValueError('Unsupported tracks')
    if not episodes:raise ValueError('No episodes available')
    dest=io.BytesIO();manifest={'offset_seconds':str(offset),'source_states_modified':False,'source_timecodes_used_in_preview':True,'files':[],'excluded_episodes':[]}
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for e in episodes:
            if e.get('status')!='ready':
                manifest['excluded_episodes'].append({'id':e['id'],'title':e['title'],'reason':'not_ready'});continue
            folder=Path(e['folder']);path=folder/'workbench_state.json'
            if (folder/'sound_composition_pending').exists() and 'sdh' in tracks:raise ValueError(e['title']+': saved sound decisions need composition; open this episode in film review first')
            raw=path.read_bytes();state=json.loads(raw);quality=report(state)
            slug=re.sub(r'[^A-Za-z0-9_-]+','_',e['title']).strip('_')[:70] or 'episode'
            rate=str(state.get('frameRate','24'));language=state.get('targetLanguage','en-US')
            for track in tracks:
                label='NORMAL' if track=='standard' else 'SDH';draft=quality['status']!='READY_FOR_DELIVERY' or not Path(e.get('video','')).is_file()
                # Read-only exports never convert unresolved state into an acceptance.
                rows=shifted(state.get(track,[]),offset,rate)
                if fmt=='itt':
                    with tempfile.TemporaryDirectory() as temp:
                        p=Path(temp)/'track.itt';write_itt(rows,p,rate,language);payload=p.read_bytes()
                else:payload=srt_bytes(rows)
                offset_tag=('_PLUS_'+str(offset).replace('.','p')+'S') if Fraction(str(offset)) else ''
                name=f'{label}/{slug}_{e["id"][:8]}_{label}{offset_tag}_{"REVIEW_DRAFT" if draft else "CHECKED"}.{fmt}'
                z.writestr(name,payload)
                manifest['files'].append({'file':name,'episode_id':e['id'],'episode_title':e['title'],'track':track,'frame_rate':rate,'language':language,'profile':state.get('subtitleSpec','prime'),'project_settings':state.get('projectSettings'),'source_state_sha256':hashlib.sha256(raw).hexdigest(),'quality_status':quality['status'],'source_media_available':Path(e.get('video','')).is_file(),'source_cue_count':len(rows),'sha256':hashlib.sha256(payload).hexdigest()})
        if not manifest['files']:raise ValueError('No ready subtitle tracks to export')
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        z.writestr('README.txt','Normal dialogue/lyrics and SDH are exported separately.\nOffset applies once to delivery files only; source state and video preview are unchanged.\nREVIEW_DRAFT files contain unresolved checks and are not Amazon-approved.\nCHECKED means local checks passed, not platform acceptance. See manifest.json for sources, hashes, and excluded episodes.\n')
    return dest.getvalue()
