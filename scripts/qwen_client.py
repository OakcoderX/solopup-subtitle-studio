"""Bounded streamed requests. Never log request headers or credentials."""
import json,re,time,urllib.request

def call_json(url,key,payload):
    started=time.monotonic()
    payload=dict(payload,stream=True)
    payload.setdefault("stream_options",{"include_usage":True})
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            pieces=[];usage=None;complete=False
            with urllib.request.urlopen(req,timeout=300) as response:
                for line in response:
                    if not line.startswith(b'data:'):continue
                    data=line[5:].strip()
                    if data==b'[DONE]':complete=True;break
                    item=json.loads(data);usage=item.get('usage') or usage
                    for choice in item.get('choices',[]):
                        content=choice.get('delta',{}).get('content')
                        if content:pieces.append(content)
                        if choice.get('finish_reason')=='stop':complete=True
            if not complete:raise ValueError('Incomplete provider response')
            raw=''.join(pieces);value=re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip())
            value=re.sub(r'("confidence"\s*:\s*)(high|medium|low)(\s*[,}])',r'\1"\2"\3',value)
            usage=dict(usage or {})
            usage["client_elapsed_seconds"]=round(time.monotonic()-started,3)
            usage["client_attempts"]=attempt+1
            from provider_json import parse_object
            return parse_object(raw),usage,raw
        except (OSError,ValueError):
            if attempt==2:raise
            time.sleep(2)
