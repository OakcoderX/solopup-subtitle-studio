"""Summarize measured batch time and provider usage; no inferred quality approval."""
import argparse,datetime,json,time
from pathlib import Path

def report(batch,library):
 data=json.loads(Path(batch).read_text());now=time.time();episodes=[]
 for source,eid in zip(data['entries'],data['ids']):
  folder=Path(library)/'episodes'/eid
  events=[json.loads(x) for x in (folder/'history/events.jsonl').read_text().splitlines()]
  stages=[(datetime.datetime.fromisoformat(x['at']).timestamp(),x['details']['stage']) for x in events if x.get('event')=='stage_started']
  spans=[{'stage':s,'seconds':round((stages[i+1][0] if i+1<len(stages) else now)-t,2)}for i,(t,s)in enumerate(stages)]
  totals={};calls=0
  for pattern in ['evidence/qwen_*.json','review/review_????.json','repair_review/repair_*.json']:
   for f in folder.glob(pattern):
    d=json.loads(f.read_text());u=d.get('usage') or {};calls+=1
    for key in ['prompt_tokens','completion_tokens','total_tokens']:totals[key]=totals.get(key,0)+u.get(key,0)
    totals['reasoning_tokens']=totals.get('reasoning_tokens',0)+u.get('completion_tokens_details',{}).get('reasoning_tokens',0)
  summary=json.loads((folder/'run_summary.json').read_text()) if (folder/'run_summary.json').exists() else None
  completed=[datetime.datetime.fromisoformat(x['at']).timestamp() for x in events if x.get('event')=='review_draft_published']
  completed_at=min(completed) if completed else None
  if spans and stages[-1][1]=='review':spans[-1]['seconds']=0
  episodes.append({'id':eid,'title':source['title'],'progress':json.loads((folder/'progress.json').read_text()) if (folder/'progress.json').exists() else {},'stage_spans':spans,'successful_cached_responses':calls,'usage':totals,'draft_completed_wall_seconds':round(completed_at-data['started_unix'],2) if completed_at else None,'run_summary':summary,'error':json.loads((folder/'error.json').read_text()) if (folder/'error.json').exists() else None})
 return {'elapsed_wall_seconds':round(now-data['started_unix'],2),'complete_drafts':sum(x['run_summary'] is not None for x in episodes),'episodes':episodes,'note':'Successful saved responses only; incomplete/retried calls may incur additional usage. Draft completion does not mean delivery accepted. No measured serial baseline yet.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--library',required=True);p.add_argument('--output',required=True);a=p.parse_args();Path(a.output).write_text(json.dumps(report(a.batch,a.library),ensure_ascii=False,indent=2)+'\n')
