"""Register review-discovered sounds as auditable candidates, never hidden notes."""
import copy,hashlib,json,re,csv,subprocess

def register(candidates,decisions,proposals,duration):
    rows=copy.deepcopy(candidates);out=copy.deepcopy(decisions);ledger=[]
    for m in proposals:
        start,end=float(m['start']),float(m['end']);caption=str(m['caption']).strip()
        if not 0<=start<end<=duration or not re.fullmatch(r'\[[^\[\]\n]+\]',caption):
            ledger.append({'proposal':m,'status':'invalid_pending'});continue
        token=hashlib.sha256(json.dumps([start,end,caption,m.get('evidence')],sort_keys=True).encode()).hexdigest()
        # Same reviewed proposal on resume must not become a second candidate.
        known=next((k for k,d in out.items() if d.get('missingProposalKey')==token),None)
        if known:ledger.append({'proposal':m,'candidate':known,'status':'already_registered'});continue
        equivalent=[]
        for i,c in enumerate(rows,1):
            same=' '.join(str(c.get('caption','')).lower().split())==' '.join(caption.lower().split())
            overlap=max(0,min(end,float(c['end']))-max(start,float(c['start'])))
            if same and overlap>=.8*(end-start):equivalent.append(str(i))
        if equivalent:ledger.append({'proposal':m,'candidates':equivalent,'status':'already_covered'});continue
        key=str(len(rows)+1);off=max(0,start-2);stop=min(duration,end+2)
        rows.append({'start':start,'end':end,'caption':caption,'clip_file':f'clips/missing_{token[:12]}.mp3','clip_start':off,'clip_end':stop,'selection_reason':m.get('narrative_value','Review-discovered sound'),'review_group':'review_discovered'})
        out[key]={'status':'','caption':caption,'recommendation':'KEEP','note':m.get('narrative_value',''),
                  'reviewer':'assistant','humanApproved':False,'uncertain':True,'reviewed':False,
                  'audioEvidence':m.get('audio_evidence'),'pictureEvidence':m.get('picture_evidence'),
                  'evidence':m.get('evidence'),'sourceUncertainty':m.get('uncertainty'),
                  'missingProposalKey':token,'missingProposal':m}
        ledger.append({'proposal':m,'candidate':key,'status':'registered_pending'})
    return rows,out,ledger

def persist(folder,video,rows):
    path=folder/'SDH_Sound_Candidates.csv';fields=['start','end','caption','clip_file','clip_start','clip_end','selection_reason','review_group']
    for row in rows:
        if row.get('review_group')!='review_discovered':continue
        dest=folder/row['clip_file'];dest.parent.mkdir(exist_ok=True)
        if not dest.exists():subprocess.run(['ffmpeg','-v','error','-ss',str(row['clip_start']),'-i',str(video),'-t',str(float(row['clip_end'])-float(row['clip_start'])),'-vn','-ac','1','-ar','24000','-b:a','64k','-y',str(dest)],check=True)
    tmp=path.with_suffix('.csv.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    tmp.replace(path)
