"""Read-only project export dispatch; workflow types retain distinct track meanings."""
import io,json,zipfile
from pathlib import Path
from export_bundle import bundle,select_latest
from bilingual import itt_files,srt_files,metrics

def project_bundle(episodes,fmt='itt'):
    if fmt not in ('itt','srt'):raise ValueError('Select ITT or SRT')
    out=io.BytesIO();manifest=[]
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for e in select_latest(episodes):
            if e['status']!='ready':continue
            folder=Path(e['folder']);bilingual=folder/'bilingual_state.json';prefix=e['id'][:12]+'/'
            if bilingual.exists():
                state=json.loads(bilingual.read_text());files=(itt_files if fmt=='itt' else srt_files)(state)
                for name,data in files.items():z.writestr(prefix+name,data)
                manifest.append({'episode':e['title'],'workflow':'bilingual','tracks':['zh','en'],'status':'REVIEW_DRAFT','files':[prefix+n for n in files]})
            else:
                data=bundle([e],fmt=fmt)
                with zipfile.ZipFile(io.BytesIO(data)) as old:
                    for name in old.namelist():z.writestr(prefix+name,old.read(name))
                manifest.append({'episode':e['title'],'workflow':'sdh','tracks':['standard','sdh'],'filesPrefix':prefix})
        if not manifest:raise ValueError('No ready episodes in this project')
        z.writestr('workflows.json',json.dumps({'sourceStatesModified':False,'episodes':manifest},ensure_ascii=False,indent=2))
    return out.getvalue()
