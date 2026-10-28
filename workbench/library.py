"""Persistent episode library and one resumable background producer per service."""
import csv
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from scope import validate as validate_scope
from history import record

HERE = Path(__file__).resolve().parent

def fingerprint(path):
    p = Path(path)
    s = p.stat()
    return [str(p.resolve()), s.st_size, s.st_mtime_ns]

class Library:
    def __init__(self, root, start_worker=True, key_zip=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.key_zip=Path(key_zip).resolve() if key_zip else None
        runtime=self.root/'runtime.json'
        if os.environ.get('SDH_ALIGN_PYTHON'):
            settings=json.loads(runtime.read_text()) if runtime.exists() else {}
            settings['timing_python']=os.environ['SDH_ALIGN_PYTHON'];runtime.write_text(json.dumps(settings))
        self.runtime=json.loads(runtime.read_text()) if runtime.exists() else {}
        self.instance_lock=(self.root/'service.lock').open('a+')
        if os.name=='posix':
            import fcntl
            try:fcntl.flock(self.instance_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                self.instance_lock.close()
                raise RuntimeError('This project library is already open in another service.')
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.processes = {}
        self.db = sqlite3.connect(self.root/'library.sqlite3', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS episodes(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,title TEXT NOT NULL,
        video TEXT NOT NULL,script TEXT,folder TEXT NOT NULL,sounds TEXT,status TEXT NOT NULL,
        stage TEXT NOT NULL DEFAULT '',error TEXT NOT NULL DEFAULT '',created REAL NOT NULL,fingerprint TEXT);
        ''')
        self.db.execute("UPDATE episodes SET status='queued',stage='resume' WHERE status='running'")
        self.db.commit()
        self.threads = []
        workers=max(1,min(3,int(self.runtime.get('episode_workers',1))))
        if start_worker:
            for i in range(workers):
                thread=threading.Thread(target=self.worker,daemon=True,name=f'subtitle-producer-{i}')
                self.threads.append(thread);thread.start()

    def query(self, sql, values=()):
        with self.lock:
            result = self.db.execute(sql, values)
            rows = [dict(x) for x in result.fetchall()]
            self.db.commit()
            return rows

    def project(self, name, settings=None):
        from project_policy import validate
        policy = validate(settings) if settings is not None else None
        name = str(name).strip()[:100]
        if not name:
            raise ValueError('Project name required')
        found = self.query('SELECT * FROM projects WHERE name=?', (name,))
        if found:
            if policy is not None:
                raise ValueError('A project with that name already exists; choose a new name to preserve its policy.')
            return found[0]['id']
        key = uuid.uuid4().hex
        if policy and policy.get('workflow')=='bilingual':policy['seriesTitle']=name
        if policy is not None:
            folder = self.root/'projects'/key
            folder.mkdir(parents=True)
            (folder/'project.json').write_text(json.dumps(policy, ensure_ascii=False, indent=2))
        self.query('INSERT INTO projects VALUES (?,?)', (key,name))
        return key

    def register(self, video, folder, title, sounds=None):
        folder = str(Path(folder).resolve())
        found = self.query('SELECT * FROM episodes WHERE folder=?',(folder,))
        if found: return found[0]['id']
        pid = self.project(Path(video).stem + ' / Project')
        eid = uuid.uuid4().hex
        self.query('INSERT INTO episodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (eid,pid,title,str(Path(video).resolve()),'',folder,str(sounds or ''),'ready','review','',time.time(),None))
        return eid

    def get(self, eid):
        rows = self.query('SELECT * FROM episodes WHERE id=?',(eid,))
        if not rows: raise ValueError('Episode not found')
        return rows[0]

    def series_directory(self,project_id):
        local=self.root/'projects'/project_id
        linked=local/'linked_project.json'
        return Path(json.loads(linked.read_text())['seriesDirectory']) if linked.exists() else local

    def effective_settings(self, project_id):
        path=self.series_directory(project_id)/'project.json'
        if path.exists():return json.loads(path.read_text())
        # Existing bilingual episodes supply their mode without rewriting their library or review data.
        for episode in self.query('SELECT folder FROM episodes WHERE project_id=? ORDER BY created',(project_id,)):
            saved=Path(episode['folder'])/'bilingual_state.json'
            if saved.exists():
                from project_policy import validate
                state=json.loads(saved.read_text())
                policy=validate({'workflow':'bilingual','sourceLanguage':'zh-CN','targetLanguage':state.get('targetLanguage','en-US'),
                                 'platform':'amazon','audience':'children','editFrameRate':str(state.get('editFrameRate','source'))})
                policy['seriesTitle']=state.get('project','');policy['syllableLexicon']=state.get('syllableLexicon',{})
                return policy
        return {}

    def enqueue(self, project_id, entries):
        if not self.query('SELECT id FROM projects WHERE id=?',(project_id,)):
            raise ValueError('Project not found')
        if not isinstance(entries,list) or not 1 <= len(entries) <= 5:
            raise ValueError('Choose one to five episodes')
        prepared = []
        # Validate every entry before inserting any of the batch.
        for entry in entries:
            video = Path(str(entry.get('video',''))).expanduser().resolve()
            script = Path(str(entry['script'])).expanduser().resolve() if entry.get('script') else None
            if not video.is_file() or video.suffix.lower() not in {'.mp4','.mov','.mkv','.m4v'}:
                raise ValueError('Video not found or unsupported: '+video.name)
            if script and (not script.is_file() or script.suffix.lower() not in {'.docx','.txt','.md'}):
                raise ValueError('Script not found or unsupported')
            entry=dict(entry);entry['scope']=validate_scope(entry.get('scope'))
            policy=self.effective_settings(project_id)
            for field in ('source_subtitles','target_subtitles'):
                if entry.get(field):
                    sub=Path(str(entry[field])).expanduser().resolve()
                    if not sub.is_file() or sub.suffix.lower()!='.srt':raise ValueError('Subtitle file must be an existing SRT')
                    if policy.get('workflow')!='bilingual':raise ValueError('Source/translation imports require a bilingual project')
                    entry[field]=str(sub)
            if entry.get('target_subtitles') and not entry.get('source_subtitles'):raise ValueError('Import Chinese SRT together with English SRT to bind screens')
            prepared.append((entry,video,script))
        ids=[]
        with self.lock:
            for entry,video,script in prepared:
                eid=uuid.uuid4().hex; folder=self.root/'episodes'/eid; folder.mkdir(parents=True)
                stamp={'video':fingerprint(video),'script':fingerprint(script) if script else None}
                inputs={key:entry[key] for key in ('source_subtitles','target_subtitles') if entry.get(key)}
                if inputs:stamp['subtitles']={key:fingerprint(value) for key,value in inputs.items()}
                policy_path = self.root/'projects'/project_id/'project.json'
                policy = self.effective_settings(project_id)
                (folder/'production_config.json').write_text(json.dumps({'scope':entry['scope'],'pipeline':'bilingual_review' if policy.get('workflow')=='bilingual' else 'full_review','projectSettings':policy,'inputs':inputs},ensure_ascii=False,indent=2))
                record(folder,'episode_created',after={'title':entry.get('title') or video.stem,'sources':stamp,'scope':entry['scope']},reason='New isolated episode requested; source files and production scope recorded.')
                self.db.execute('INSERT INTO episodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    (eid,project_id,str(entry.get('title') or video.stem)[:100],str(video),str(script or ''),
                     str(folder),str(folder/'SDH_Sound_Candidates.csv'),'queued','queued','',time.time(),json.dumps(stamp)))
                ids.append(eid)
            self.db.commit()
        return ids

    def action(self, eid, action):
        with self.lock:
            e=self.get(eid)
            if action=='pause' and e['status'] in {'queued','running'}:
                self.query("UPDATE episodes SET status='paused' WHERE id=?",(eid,))
            elif action in {'resume','retry'} and e['status'] in {'paused','failed'}:
                self.query("UPDATE episodes SET status='queued',error='' WHERE id=?",(eid,))
            elif action=='rerun' and e['status']=='ready':
                return self.enqueue(e['project_id'],[{'video':e['video'],'script':e['script'],
                                                    'title':e['title']+' · new draft',**(json.loads((Path(e['folder'])/'production_config.json').read_text()).get('inputs',{}) if (Path(e['folder'])/'production_config.json').exists() else {}),'scope':json.loads((Path(e['folder'])/'production_config.json').read_text()).get('scope') if (Path(e['folder'])/'production_config.json').exists() else {'mode':'full'}}])
            else: raise ValueError('Action unavailable for current state')
        return [eid]

    def snapshot(self):
        episodes=self.query('SELECT * FROM episodes ORDER BY created')
        for e in episodes:
            folder=Path(e['folder']); count=reviewed=sounds=decided=0
            if (folder/'workbench_state.json').exists():
                state=json.loads((folder/'workbench_state.json').read_text())
                rows=state.get('sdh',[]); count=len(rows);reviewed=sum(bool(c.get('checked')) for c in rows)
            if e['sounds'] and Path(e['sounds']).exists():
                with Path(e['sounds']).open(encoding='utf-8-sig') as f:sounds=sum(1 for _ in csv.DictReader(f))
            if (folder/'sound_review_state.json').exists():
                decisions=json.loads((folder/'sound_review_state.json').read_text())
                decided=sum(d.get('status') in {'KEEP','REVISE','REMOVE'} for d in decisions.values())
            workflow='sdh';track_counts=None
            if (folder/'bilingual_state.json').exists():
                from bilingual import metrics
                state=json.loads((folder/'bilingual_state.json').read_text());m=metrics(state)
                count=len(state['zh'])+len(state['en']);reviewed=sum(x['reviewed'] for x in m['summary'].values())
                sounds=decided=0;workflow='bilingual';track_counts=m['summary']
            else:
                cfg=folder/'production_config.json'
                if cfg.exists():workflow=json.loads(cfg.read_text()).get('projectSettings',{}).get('workflow','sdh')
            progress={}
            if (folder/'progress.json').exists():
                try: progress=json.loads((folder/'progress.json').read_text())
                except (ValueError,OSError):pass
            e.update(cues=count,reviewed=reviewed,sounds=sounds,decided=decided,progress=progress,phase='sound_review' if decided<sounds else 'film_review' if reviewed<count else 'delivery_check')
            e.update(workflow=workflow,trackCounts=track_counts,mediaAvailable=Path(e['video']).is_file())
            e.pop('fingerprint',None)
        projects=self.query('SELECT * FROM projects')
        for p in projects:
            settings=self.root/'projects'/p['id']/'project.json'
            p['settings']=self.effective_settings(p['id']) or None
        return {'projects':projects,'episodes':episodes,'concurrency':max(1,len(self.threads))}

    def worker(self):
        while not self.stop.wait(.5):
            with self.lock:
                rows=self.query("SELECT * FROM episodes WHERE status='queued' ORDER BY created LIMIT 1")
                if not rows:continue
                e=rows[0];self.query("UPDATE episodes SET status='running',stage='prepare',error='' WHERE id=?",(e['id'],))
            try:
                expected=json.loads(e['fingerprint'])
                actual={'video':fingerprint(e['video']),'script':fingerprint(e['script']) if e['script'] else None}
                inputs_path=Path(e['folder'])/'production_config.json'
                inputs=json.loads(inputs_path.read_text()).get('inputs',{}) if inputs_path.exists() else {}
                if inputs:actual['subtitles']={key:fingerprint(value) for key,value in inputs.items()}
                if actual!=expected:raise ValueError('Source file changed. Import as a new draft to avoid mixed evidence.')
                command=[sys.executable,str(HERE/'produce.py'),'--video',e['video'],'--output',e['folder'],
                         '--series',str(self.series_directory(e['project_id']))]
                record(e['folder'],'production_started',reason='Background worker executing mandatory production stages.')
                if e['script']:command+=['--script',e['script']]
                if self.key_zip:command+=['--key-zip',str(self.key_zip)]
                with (Path(e['folder'])/'worker.log').open('a') as log:
                    env=os.environ.copy()
                    if self.runtime.get('timing_python') and Path(self.runtime['timing_python']).is_file():env['SDH_ALIGN_PYTHON']=self.runtime['timing_python']
                    process=subprocess.Popen(command,stdout=log,stderr=log,start_new_session=True,env=env)
                    with self.lock:self.processes[e['id']]=process
                    while process.poll() is None:
                        if self.stop.wait(.25) or self.get(e['id'])['status']=='paused':
                            self.terminate(e['id']); break
                        progress=Path(e['folder'])/'progress.json'
                        if progress.exists():
                            try:self.query('UPDATE episodes SET stage=? WHERE id=?',(json.loads(progress.read_text()).get('stage','working'),e['id']))
                            except (ValueError,OSError):pass
                    rc=process.wait()
                if self.stop.is_set():
                    self.query("UPDATE episodes SET status='queued' WHERE id=? AND status='running'",(e['id'],))
                elif self.get(e['id'])['status']=='paused':pass
                elif rc==0:self.query("UPDATE episodes SET status='ready',stage='review' WHERE id=?",(e['id'],))
                else:
                    error_path=Path(e['folder'])/'error.json'
                    error=json.loads(error_path.read_text()).get('error','') if error_path.exists() else 'Generation failed; retry to resume saved chunks.'
                    self.query("UPDATE episodes SET status='failed',error=? WHERE id=?",(error,e['id']))
            except Exception as exc:
                if self.stop.is_set():
                    self.query("UPDATE episodes SET status='queued' WHERE id=? AND status='running'",(e['id'],))
                elif self.get(e['id'])['status']!='paused':
                    self.query("UPDATE episodes SET status='failed',error=? WHERE id=?",(str(exc)[:300],e['id']))
            finally:
                with self.lock:self.processes.pop(e['id'],None)

    def terminate(self, eid=None):
        with self.lock: processes=[p for key,p in self.processes.items() if eid is None or key==eid]
        for process in processes:
            if process.poll() is not None:continue
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL)

    def close(self):
        self.stop.set();self.terminate()
        for thread in self.threads:thread.join(timeout=8)
        self.db.close()
        self.instance_lock.close()
