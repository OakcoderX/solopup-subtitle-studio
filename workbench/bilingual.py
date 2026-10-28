"""Isolated bilingual review, immutable source witnesses and revision-bound approval."""
import copy, hashlib, io, json, math, re, time, zipfile, tempfile
from pathlib import Path
from fractions import Fraction
from history import record

class Conflict(Exception): pass

def read(project):
    raw=(Path(project)/'bilingual_state.json').read_bytes()
    result=json.loads(raw);result['_saveToken']=hashlib.sha256(raw).hexdigest();return result

def signature(cue):
    canonical={'start':format(float(cue['start']),'.9f'),'end':format(float(cue['end']),'.9f'),'text':cue['text']}
    return hashlib.sha256(json.dumps(canonical,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def syllables(text,language,lexicon):
    counts=0;unknown=[];variants=[]
    for token in re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?|[\u3400-\u9fff]|\d+",text):
        if '\u3400'<=token[0]<='\u9fff':counts+=1
        elif token.isdigit():
            # Chinese numerals can have many readings; never silently call digit count speech count.
            special={'10':1,'20':2,'100':2,'1000':2}
            counts+=special.get(token,len(token));unknown.append(token+'（数字读法待核）')
        else:
            word=token.lower().replace('’',"'");values=lexicon.get(word)
            if isinstance(values,int):values=[values]
            if values:
                counts+=values[0]
                if len(values)>1:variants.append(token)
            else:
                n=len(re.findall(r'[aeiouy]+',word))
                if word.endswith('e') and not word.endswith(('le','ye')) and n>1:n-=1
                counts+=max(1,n);unknown.append(token)
    return {'count':counts,'unknown':unknown,'variants':variants,'method':'Chinese written-syllable estimate / English CMU dictionary; flags require pronunciation review'}

def cue_metrics(cue,language,policy,lexicon):
    d=cue['end']-cue['start'];lines=cue['text'].splitlines();cps=len(' '.join(lines))/max(d,.001)
    flags=[];warnings=[]
    if d<5/6-.00001:flags.append('显示不足5/6秒')
    if d>7:flags.append('显示超过7秒')
    if len(lines)>2 or any(len(s)>(42 if language=='en' else 16) for s in lines):flags.append('行数或行长超限')
    if language=='en':
        if cps>policy['maxCps']+1e-6:flags.append('超过21 CPS')
        elif cps>policy['targetCps']+1e-6:warnings.append('17–21 CPS需结合画面复核')
    syll=syllables(cue['text'],language,lexicon)
    if syll['unknown'] or syll['variants']:warnings.append('发音计数待核')
    if cue.get('uncertainties'):warnings.extend(cue['uncertainties'])
    approval=cue.get('review',{})
    checked=approval.get('accepted') is True and approval.get('signature')==signature(cue) and approval.get('reviewer')=='user'
    return {'cps':round(cps,2),'duration':round(d,3),'syllables':syll,'flags':flags,'warnings':warnings,'checked':checked}

def metrics(state):
    policy=state['policy'];lex=state.get('syllableLexicon',{});result={'zh':{},'en':{},'pairs':{}}
    for lang in ('zh','en'):
        prev=None
        for cue in sorted(state[lang],key=lambda c:(c['start'],c['end'])):
            row=cue_metrics(cue,lang,policy,lex)
            if prev and cue['start']-prev['end']<2/float(Fraction(str(state['editFrameRate'])))-1e-6:row['flags'].append('重叠' if cue['start']<prev['end'] else '间隔不足2校准帧')
            result[lang][cue['id']]=row;prev=cue
    for group in set(c.get('pairId',c['id']) for lang in ('zh','en') for c in state[lang]):
        z=sum(result['zh'][c['id']]['syllables']['count'] for c in state['zh'] if c.get('pairId',c['id'])==group)
        e=sum(result['en'][c['id']]['syllables']['count'] for c in state['en'] if c.get('pairId',c['id'])==group)
        result['pairs'][group]={'zh':z,'en':e,'delta':e-z,'ratio':round(e/z,3) if z else None,'advisory':abs(e-z)>max(2,z*.2)}
    result['summary']={lang:{'count':len(state[lang]),'reviewed':sum(m['checked'] for m in result[lang].values()),'technicalIssues':sum(bool(m['flags']) for m in result[lang].values())} for lang in ('zh','en')}
    result['status']='REVIEW_DRAFT';return result

def save(project,data,duration):
    old=read(project)
    if not isinstance(data,dict):raise ValueError('Invalid state')
    if data.get('_saveToken')!=old['_saveToken']:raise Conflict()
    # Only editable tracks cross the trust boundary. Policy, evidence and lexicon stay server-owned.
    result=copy.deepcopy(old);result.pop('_saveToken',None)
    changed_sources=set()
    for lang in ('zh','en'):
        incoming=data.get(lang)
        if not isinstance(incoming,list) or len(incoming)>3000:raise ValueError('Invalid track')
        previous={c['id']:c for c in old[lang]};rows=[];ids=set()
        for cue in incoming:
            if not isinstance(cue,dict):raise ValueError('Invalid cue')
            ident=cue.get('id');prior=previous.get(ident)
            if prior is None or ident in ids:raise ValueError('Cue IDs must remain stable')
            ids.add(ident);new=copy.deepcopy(prior)
            a,b=cue.get('start'),cue.get('end');text=cue.get('text')
            if not all(isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x) for x in (a,b)) or not 0<=a<b<=duration+.001:raise ValueError('Invalid time')
            if not isinstance(text,str) or not text.strip() or len(text)>2000:raise ValueError('Invalid text')
            new.update(start=a,end=b,text=text)
            changed=signature(new)!=signature(prior)
            if changed:
                new['review']={'accepted':False,'invalidated':True};new['revision']=int(prior.get('revision',0))+1
                if lang=='zh':changed_sources.add(new.get('pairId',ident))
            else:
                accepted=cue.get('review',{}).get('accepted') is True
                new['review']={'accepted':accepted,'reviewer':'user','signature':signature(new),'recordedAt':time.time()} if accepted else {'accepted':False}
                if lang=='en' and accepted:new.pop('translationSourceChanged',None)
            rows.append(new)
        if ids!=set(previous):raise ValueError('Use explicit split/merge workflow; do not drop source cues')
        result[lang]=rows
    for cue in result['en']:
        if cue.get('pairId',cue['id']) in changed_sources:
            cue['review']={'accepted':False,'invalidated':True};cue['translationSourceChanged']=True
    result['status']='REVIEW_DRAFT';result['updatedAt']=time.time()
    record(Path(project),'bilingual_subtitle_saved',old,result,reason='Chinese/English independent edits; changed Chinese invalidates paired translation review.',actor='workbench')
    p=Path(project)/'bilingual_state.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2));tmp.replace(p)
    # Generated review exports follow the saved revision; no platform/final approval is inferred.
    for lang in ('zh','en'):(Path(project)/f'{lang}_REVIEW_DRAFT.srt').write_text(srt(result[lang]))
    fresh=read(project);report=metrics(fresh)
    (Path(project)/'QA_REVIEW_DRAFT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (Path(project)/'Bilingual_REVIEW_DRAFT.zip').write_bytes(export_bundle(fresh))
    write_itt_exports(project,fresh)
    for name,body in srt_files(fresh).items():(Path(project)/name).write_bytes(body)
    return {'state':fresh,'metrics':report}

def srt(rows):
    def stamp(t):
        n=round(t*1000);h,n=divmod(n,3600000);m,n=divmod(n,60000);s,ms=divmod(n,1000);return f'{h:02}:{m:02}:{s:02},{ms:03}'
    return '\n\n'.join(f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}" for i,c in enumerate(sorted(rows,key=lambda c:(c['start'],c['end'])),1))+'\n'

def export_bundle(state):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for lang in ('zh','en'):z.writestr(f'{lang}_REVIEW_DRAFT.srt',srt(state[lang]))
        clean={k:v for k,v in state.items() if k!='_saveToken'}
        z.writestr('bilingual_REVIEW_DRAFT.json',json.dumps(clean,ensure_ascii=False,indent=2))
        z.writestr('QA_REVIEW_DRAFT.json',json.dumps(metrics(state),ensure_ascii=False,indent=2))
        z.writestr('READ_ME.txt','中文配音，中英文独立字幕轨。审阅稿，尚未完成逐条人工核听及翻译批准。17 CPS目标、21 CPS项目上限；亚马逊专属交付要求待核。\n')
    return out.getvalue()


def subtitle_basename(state):
    """Retain the exact media stem, adding only the player language suffix."""
    stem=Path(state.get('source',{}).get('path') or 'episode.mp4').stem
    if not stem or any(ord(c)<32 for c in stem):raise ValueError('Invalid media basename')
    return stem


def itt_files(state,track='both'):
    from timed_text import write_itt
    if track not in ('both','zh','en'):raise ValueError('Unsupported bilingual track')
    rate=str(state['editFrameRate']);stem=subtitle_basename(state);result={}
    # This writer verifies text roundtrip; technical/editorial review stays separate.
    with tempfile.TemporaryDirectory(prefix='bilingual-itt-') as folder:
        for lang in (('zh','en') if track=='both' else (track,)):
            path=Path(folder)/f'{stem}.{lang}.itt'
            write_itt(state[lang],path,rate,'zh-CN' if lang=='zh' else state.get('targetLanguage','en-US'))
            result[path.name]=path.read_bytes()
    return result


def itt_bundle(state):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in itt_files(state).items():z.writestr(name,data)
    return out.getvalue()


def write_itt_exports(project,state):
    """Keep each saved revision's local iTT exports and review status together."""
    files=itt_files(state)
    for name,data in files.items():
        dest=Path(project)/name;tmp=dest.with_suffix('.itt.tmp');tmp.write_bytes(data);tmp.replace(dest)
    (Path(project)/'Bilingual_ITT_REVIEW_DRAFT.zip').write_bytes(itt_bundle(state))
    receipt={'status':'REVIEW_DRAFT','frameRate':state['editFrameRate'],
             'sourceVideoFrameRate':state.get('videoFrameRate'),'offsetSeconds':0,
             'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
             'editorialApproval':False,'platformAcceptance':False}
    (Path(project)/'ITT_EXPORT_REVIEW_STATUS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    return receipt


def srt_files(state,track='both'):
    if track not in ('both','zh','en'):raise ValueError('Unsupported bilingual track')
    stem=subtitle_basename(state)
    return {f'{stem}.{lang}.srt':srt(state[lang]).encode('utf-8')
            for lang in (('zh','en') if track=='both' else (track,))}


def srt_bundle(state):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,body in srt_files(state).items():z.writestr(name,body)
    return out.getvalue()
