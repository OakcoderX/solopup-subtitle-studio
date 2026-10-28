"""Per-episode, append-only audit records and recoverable JSON snapshots."""
import copy,datetime,hashlib,json,os,uuid
from pathlib import Path

def clean(value):
    value=copy.deepcopy(value)
    if isinstance(value,dict):value.pop('_saveToken',None)
    return value

def differences(before,after,path=''):
    if before==after:return []
    if isinstance(before,dict) and isinstance(after,dict):
        result=[]
        for k in sorted(set(before)|set(after)):
            result+=differences(before.get(k),after.get(k),path+'/'+str(k))
        return result
    if isinstance(before,list) and isinstance(after,list) and all(isinstance(x,dict) and 'id' in x for x in before+after):
        return differences({str(x['id']):x for x in before},{str(x['id']):x for x in after},path)
    return [{'path':path,'before':before,'after':after}]

def record(folder,event,before=None,after=None,reason='',actor='system',details=None):
    folder=Path(folder);hist=folder/'history';hist.mkdir(parents=True,exist_ok=True)
    before,after=clean(before),clean(after)
    ident=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-'+uuid.uuid4().hex[:8]
    entry={'id':ident,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'event':event,'actor':actor,'reason':reason or 'No separate reason supplied.','changes':differences(before,after),'details':details or {}}
    for label,value in [('before',before),('after',after)]:
        if value is not None:
            body=json.dumps(value,ensure_ascii=False,indent=2).encode();name=ident+'-'+label+'.json';(hist/name).write_bytes(body)
            entry[label+'_snapshot']=name;entry[label+'_sha256']=hashlib.sha256(body).hexdigest()
    # Single O_APPEND write keeps concurrent worker and review events as complete lines.
    fd=os.open(hist/'events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    try:os.write(fd,(json.dumps(entry,ensure_ascii=False)+'\n').encode());os.fsync(fd)
    finally:os.close(fd)
    return entry
