"""Persist human sound decisions by exact media bytes, independently of candidate IDs."""
import copy,hashlib,json,os,tempfile
from pathlib import Path

def media_key(video):
    p=Path(video);cache=p.stat()
    # Full content digest: copies on another path inherit; changed media does not.
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

def inherit(candidates,decisions,confirmed):
    out=copy.deepcopy(decisions);events=[]
    for item in confirmed:
        matches=[]
        for i,c in enumerate(candidates,1):
            overlap=min(float(c['end']),item['end'])-max(float(c['start']),item['start'])
            if overlap>0 and overlap/min(float(c['end'])-float(c['start']),item['end']-item['start'])>=.5:matches.append(str(i))
        if len(matches)!=1:
            events.append({'confirmed':item,'status':'missing_or_ambiguous_match','candidate_ids':matches});continue
        key=matches[0];prior=item['decision'];new=out.get(key,{})
        same=new.get('caption','').strip()==prior.get('caption','').strip() and new.get('status')==prior.get('status')
        # Even same labels require timing adjudication if candidate boundaries changed.
        row=candidates[int(key)-1];exact=float(row['start'])==item['start'] and float(row['end'])==item['end']
        if same and exact:out[key]=copy.deepcopy(prior)
        else:
            out[key]={**new,'status':'','recommendation':prior.get('status'),'confirmedPrior':copy.deepcopy(item),'uncertain':True,'humanApproved':False,'note':'与同一成片的用户裁定或时间边界冲突；需复核，不能覆盖用户裁定。'}
            events.append({'candidate_id':key,'confirmed':item,'status':'conflict'})
    return out,events

def save_human(path,candidates,decisions):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    old=json.loads(path.read_text()) if path.exists() else []
    for i,row in enumerate(candidates,1):
        d=decisions.get(str(i),{})
        if d.get('reviewer')!='human' or d.get('humanApproved') is not True:continue
        item={'start':float(row['start']),'end':float(row['end']),'decision':copy.deepcopy(d)}
        old=[x for x in old if (x['start'],x['end'])!=(item['start'],item['end'])];old.append(item)
    fd,name=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    with os.fdopen(fd,'w') as f:json.dump(old,f,ensure_ascii=False,indent=2)
    os.replace(name,path)
