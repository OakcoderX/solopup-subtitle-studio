"""Link existing ready episode indexes; original databases and review folders stay in place."""
import hashlib,json,sqlite3
from pathlib import Path

def link(library,root):
    root=Path(root).expanduser().resolve();database=root/'library.sqlite3'
    if root==library.root:raise ValueError('This library is already open')
    if not database.is_file():raise ValueError('No subtitle project library at that folder')
    origin=sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True);origin.row_factory=sqlite3.Row
    try:
        projects=[dict(r) for r in origin.execute('SELECT * FROM projects')]
        episodes=[dict(r) for r in origin.execute("SELECT * FROM episodes WHERE status='ready'")]
    except sqlite3.Error as exc:raise ValueError('The selected folder is not a supported subtitle project library') from exc
    finally:origin.close()
    count=0;mapping={}
    with library.lock:
        for p in projects:
            pid=hashlib.sha256((str(root)+':project:'+p['id']).encode()).hexdigest()[:32];mapping[p['id']]=pid
            library.db.execute('INSERT OR IGNORE INTO projects VALUES (?,?)',(pid,p['name']))
            local=library.root/'projects'/pid;local.mkdir(parents=True,exist_ok=True)
            source_series=root/'projects'/p['id']
            meta=local/'linked_project.json'
            if not meta.exists():meta.write_text(json.dumps({'sourceLibrary':str(root),'sourceProjectId':p['id'],'seriesDirectory':str(source_series)},indent=2))
        for e in episodes:
            folder=Path(e['folder'])
            if not ((folder/'workbench_state.json').is_file() or (folder/'bilingual_state.json').is_file()):continue
            eid=hashlib.sha256((str(root)+':episode:'+e['id']).encode()).hexdigest()[:32]
            before=library.db.total_changes
            library.db.execute('INSERT OR IGNORE INTO episodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
              (eid,mapping[e['project_id']],e['title'],e['video'],e.get('script',''),e['folder'],e.get('sounds',''),'ready','review','',e['created'],e.get('fingerprint')))
            count+=library.db.total_changes-before
        library.db.commit()
    return {'linkedProjects':len(projects),'addedReadyEpisodes':count,'originalDatabaseModified':False,'originalReviewFoldersCopied':False}
