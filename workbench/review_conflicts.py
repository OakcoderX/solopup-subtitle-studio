"""Keep conflicting speech-versus-sound evidence visible; never majority-vote it away."""
import copy

def mark(rows,conflicts):
    out=copy.deepcopy(rows)
    for c in out:
        evidence=[x for x in conflicts if str(x.get('id'))==str(c.get('id'))]
        if not evidence:continue
        c['crossModalConflicts']=list({(x.get('evidence',''),x.get('reason','')):x for x in c.get('crossModalConflicts',[])+evidence}.values())
        notice='对白与声音复核不一致，需核对原声：'+'；'.join(dict.fromkeys(x.get('reason','') for x in evidence))
        if notice not in c.get('unresolved',''):c['unresolved']=(c.get('unresolved','')+' '+notice).strip()
        c['checked']=False
    return out
