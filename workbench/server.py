#!/usr/bin/env python3
"""Portable local review server for timed-text and SDH projects."""
from __future__ import annotations

import argparse
import hashlib
import threading
import signal
import uuid
from concurrent.futures import ThreadPoolExecutor
import csv
import html
import json
import mimetypes
import re
import shutil
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
from library import Library
from http_security import trusted_request
from project_policy import profile as selected_profile
import secrets
from provider_settings import status as provider_status, save as save_provider
from history import record
from confirmed_sounds import media_key,save_human
from sdh_track import compose as compose_sdh
from sound_readability import scene_times
from layout_policy import prepare as prepare_layout
from timed_text import PROFILE, check, write_itt, blocking_issues

HERE = Path(__file__).resolve().parent
PAGE = HERE / "index.html"


def read_state(path: Path) -> dict:
    if path.exists():
        raw=path.read_bytes();data=json.loads(raw);data["_saveToken"]=hashlib.sha256(raw).hexdigest();return data
    return {"standard": [], "sdh": [], "subtitleSpec": "prime"}


def sound_token(project):
    p=project/'sound_review_state.json'
    return hashlib.sha256(p.read_bytes() if p.exists() else b'').hexdigest()


def write_srt(rows: list[dict], path: Path) -> None:
    def ts(value: float) -> str:
        ms = max(0, round(float(value) * 1000))
        h, ms = divmod(ms, 3_600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    lines = []
    for i, cue in enumerate(sorted(rows, key=lambda x: (x["start"], x["end"])), 1):
        lines.extend((str(i), f"{ts(cue['start'])} --> {ts(cue['end'])}", str(cue["text"]), ""))
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(path)


def get_duration(video: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 24 * 60 * 60.0
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(video)],
            check=True, capture_output=True, text=True, timeout=20,
        )
        return float(result.stdout.strip())
    except Exception:
        return 24 * 60 * 60.0


def stored_media_metadata(state):
    """Offline editing fallback only; never claim that cached metadata probes a new master."""
    scope=state.get('scope') or [0,0]
    ends=[float(c.get('end',0)) for track in ('standard','sdh') for c in state.get(track,[])]
    duration=max([float(scope[1]) if len(scope)>1 else 0]+ends+[0])
    return duration,str(state.get('frameRate','24'))


def make_handler(args: argparse.Namespace):
    project = args.project.resolve()
    project.mkdir(parents=True, exist_ok=True)
    video = args.video.resolve()
    state_path = project / "workbench_state.json"
    sounds_path = args.sounds_csv.resolve() if args.sounds_csv else None
    try:
        duration = get_duration(video)
        frame_rate = subprocess.check_output([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(video)], text=True).strip()
        initial_media_available=True
    except (OSError,subprocess.SubprocessError):
        duration,frame_rate=stored_media_metadata(read_state(state_path));initial_media_available=False

    library=getattr(args,'library_instance',None) or Library(getattr(args,'library',None) or project.parent/'Subtitle_Library',key_zip=getattr(args,'key_zip',None))
    default_episode=library.register(video,project,args.title,sounds_path)
    write_lock=threading.RLock()
    identity_worker=ThreadPoolExecutor(max_workers=1, thread_name_prefix="sound-history")
    def persist_confirmed(video, rows, decisions):
        try:
            stamp=(str(video),video.stat().st_size,video.stat().st_mtime_ns)
            if stamp not in media_keys:media_keys[stamp]=media_key(video)
            save_human(library.root/"confirmed_sounds"/(media_keys[stamp]+".json"),rows,decisions)
        except Exception as exc:
            print("Sound history indexing deferred; episode decisions remain saved:",type(exc).__name__,flush=True)
    media_keys={}
    meta_cache={str(video):(duration,frame_rate)} if initial_media_available else {}
    def metadata(path):
        key=str(path)
        if key not in meta_cache:
            meta_cache[key]=(get_duration(path),subprocess.check_output([shutil.which('ffprobe') or 'ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=r_frame_rate','-of','csv=p=0',key],text=True).strip())
        return meta_cache[key]
    config_token=secrets.token_urlsafe(32)
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(project), **kw)

        def select_episode(self):
            path=urlparse(self.path).path
            eid=default_episode
            if path.startswith('/episode/'):
                parts=self.path.split('/',3)
                if len(parts)!=4:raise ValueError('Invalid episode URL')
                eid=parts[2];self.path='/'+parts[3]
            self.episode=library.get(eid)
            self.project=Path(self.episode['folder']);self.video=Path(self.episode['video'])
            self.state_path=self.project/'workbench_state.json'
            self.sounds_path=Path(self.episode['sounds']) if self.episode['sounds'] else None
            self.media_available=False
            if self.video.is_file():
                try:
                    self.duration,self.frame_rate=metadata(self.video);self.media_available=True
                except (OSError,subprocess.SubprocessError):
                    self.duration,self.frame_rate=stored_media_metadata(read_state(self.state_path))
            else:self.duration,self.frame_rate=stored_media_metadata(read_state(self.state_path))
            self.directory=str(self.project)
            self.base='/episode/'+eid

        def local_request(self):
            if not trusted_request(self.headers,self.server.server_port):
                self.send_error(403,"Untrusted local service origin");return False
            return True

        def do_GET(self):
            if not self.local_request():return
            if urlparse(self.path).path == "/api/provider":
                self.json_response({**provider_status(library.key_zip),"config_token":config_token});return
            if urlparse(self.path).path=="/api/health":
                self.json_response({"ok":True,"service":"sdh-workbench"});return
            if urlparse(self.path).path in ('/projects','/projects/'):
                body=(HERE/'project_hub.html').read_bytes();self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body);return
            if urlparse(self.path).path=='/api/library/export':
                from unified_export import project_bundle
                query=parse_qs(urlparse(self.path).query);project_id=query.get('project',[''])[0]
                try:
                    if not library.query('SELECT id FROM projects WHERE id=?',(project_id,)):raise ValueError('Unknown project')
                    payload=project_bundle([e for e in library.snapshot()['episodes'] if e['project_id']==project_id],query.get('format',['itt'])[0])
                    self.send_response(200);self.send_header('Content-Type','application/zip')
                    self.send_header('Content-Disposition','attachment; filename="Project_Subtitles.zip"')
                    self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
                except (ValueError,OSError) as exc:self.json_response({'error':str(exc)},400)
                return
            if urlparse(self.path).path=='/api/library':
                self.json_response(library.snapshot());return
            if urlparse(self.path).path in {'/assets/studio.css','/assets/studio.js','/assets/shell.js','/assets/shell_policy.js','/assets/settings.js','/assets/bilingual.js','/assets/bilingual.css','/assets/project_hub.js','/assets/project_hub.css','/assets/hub_link.js','/assets/provider_onboarding.js'}:
                file=HERE/urlparse(self.path).path.split('/')[-1]
                data=file.read_bytes();self.send_response(200)
                self.send_header('Content-Type','text/css' if file.suffix=='.css' else 'text/javascript')
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            try:self.select_episode()
            except (ValueError,OSError,subprocess.SubprocessError):self.send_error(404,'Episode or video unavailable');return
            route = urlparse(self.path).path
            if route == "/api/bilingual":
                from bilingual import read, metrics
                value=read(self.project)
                self.json_response({"state":value,"metrics":metrics(value),"videoFrameRate":self.frame_rate,"duration":self.duration});return
            if route == "/api/bilingual/export":
                from bilingual import read, export_bundle, itt_files, itt_bundle, srt_files, srt_bundle, subtitle_basename
                from urllib.parse import quote
                state=read(self.project);query=parse_qs(urlparse(self.path).query)
                fmt=query.get('format',['itt'])[0];track=query.get('track',['both'])[0]
                try:
                    if fmt=='review' and track=='both':
                        payload=export_bundle(state);name='Bilingual_REVIEW_DRAFT.zip';mime='application/zip'
                    elif fmt=='srt' and track=='both':
                        payload=srt_bundle(state);name=subtitle_basename(state)+'.srt.zip';mime='application/zip'
                    elif fmt=='srt' and track in ('zh','en'):
                        files=srt_files(state,track);name,payload=next(iter(files.items()));mime='application/x-subrip; charset=utf-8'
                    elif fmt=='itt' and track=='both':
                        payload=itt_bundle(state);name=subtitle_basename(state)+'.subtitles.zip';mime='application/zip'
                    elif fmt=='itt' and track in ('zh','en'):
                        files=itt_files(state,track);name,payload=next(iter(files.items()));mime='application/ttml+xml'
                    else:raise ValueError('Unsupported export')
                except (ValueError,KeyError):self.json_response({'error':'Unsupported bilingual export'},400);return
                fallback='subtitles.'+('zip' if mime=='application/zip' else 'srt' if fmt=='srt' else 'itt')
                self.send_response(200);self.send_header('Content-Type',mime)
                self.send_header('Content-Disposition',f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name,safe='')}")
                self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload);return
            if route == "/api/media-status":
                self.json_response({'available':self.media_available,'duration':self.duration,'frameRate':self.frame_rate,'metadata_source':'video_probe' if self.media_available else 'saved_state_only'});return
            if route in ("/", "/index.html"):
                state = read_state(self.state_path)
                page = (HERE / "bilingual.html" if (self.project / "bilingual_state.json").is_file() else PAGE).read_text(encoding="utf-8")
                page = page.replace("__INITIAL__", json.dumps(state, ensure_ascii=False).replace("</", "<\\/"))
                page = page.replace("__PROJECT_TITLE__", html.escape(self.episode["title"]))
                page = page.replace("__VIDEO_NAME__", html.escape(self.video.name))
                page = page.replace("__VIDEO_DURATION__", f"{self.duration:.3f}")
                slug = re.sub(r"[^A-Za-z0-9_-]+", "_", self.episode["title"]).strip("_") or "episode"
                page = page.replace("__PROJECT_SLUG__", slug)
                page=page.replace('__EPISODE_ID__',self.episode['id'])
                page=page.replace('src="/video"','src="'+self.base+'/video"')
                page=page.replace('href="/prime-style-guides"','href="'+self.base+'/prime-style-guides"')
                page=page.replace("fetch('/api", "fetch('"+self.base+"/api")
                page=page.replace('src="/${esc(r.clip_file)}"','src="'+self.base+'/${esc(r.clip_file)}"')
                body = page.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if route == "/api/waveform":
                import array, math
                try:
                    q=parse_qs(urlparse(self.path).query)
                    start=float(q.get('start',['0'])[0]);end=float(q.get('end',['10'])[0])
                    if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= self.duration+.1 or end-start>30:
                        self.send_error(400,'Invalid waveform range');return
                    pcm=subprocess.check_output([shutil.which('ffmpeg') or 'ffmpeg','-v','error','-ss',str(start),'-i',str(self.video),'-t',str(end-start),'-vn','-ac','1','-ar','8000','-f','s16le','-'],timeout=20)
                    samples=array.array('h');samples.frombytes(pcm)
                    if __import__('sys').byteorder!='little':samples.byteswap()
                    size=max(1,len(samples)//600)
                    peaks=[round(max(abs(x) for x in samples[i:i+size])/32768,4) for i in range(0,len(samples),size)]
                    self.json_response({'start':start,'end':end,'peaks':peaks});return
                except (ValueError,OSError,subprocess.SubprocessError):
                    self.send_error(400,'Waveform unavailable');return
            if route == "/video":
                self.serve_video()
                return
            if route == '/qwen-setup-guide':
                path=HERE.parent/'docs/QWEN_SETUP.md'
                if not path.is_file():self.send_error(404);return
                body=('<!doctype html><meta charset="utf-8"><title>Qwen setup</title><pre style="white-space:pre-wrap;max-width:1000px;margin:30px auto;font:16px/1.6 system-ui">'+html.escape(path.read_text())+'</pre>').encode()
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
            if route == "/prime-style-guides" or route.startswith('/subtitle-wiki/'):
                from subtitle_wiki import page as wiki_page
                wiki=HERE.parent/'references/subtitle_wiki'
                if not (wiki/'README.md').is_file():
                    self.send_response(303)
                    self.send_header("Location", "https://videocentral.amazon.com/support/delivery-specifications/prime-video-subtitling-guidelines?language=en_US")
                    self.end_headers()
                    return
                try:body=wiki_page(wiki,route)
                except (ValueError,OSError):self.send_error(404);return
                self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body)
                return
            if route == "/api/scope":
                saved=read_state(self.state_path)
                suggestion=self.project/'scope_suggestion.json'
                self.json_response({'scope':saved.get('scope',[0,self.duration]),'duration':self.duration,'suggestion':json.loads(suggestion.read_text()) if suggestion.exists() else None})
                return
            if route == "/api/profile":
                self.json_response({**selected_profile(read_state(self.state_path)), "frameRate": self.frame_rate, "duration": self.duration})
                return
            if route == "/api/quality-gate":
                from quality_gate import report
                self.json_response(report(read_state(self.state_path),self.duration))
                return
            if route == "/api/preflight":
                state = read_state(self.state_path)
                self.json_response({"profile": selected_profile(state), "frameRate": self.frame_rate, "tracks": {k: check(state[k], self.frame_rate, self.duration, state.get("sourceManifest", {}).get(k),state.get("reviewPolicy",{}).get("songSpeedAdvisory",False),state.get("preferredSpellings"),selected_profile(state)) for k in ("standard", "sdh")}, "release": state.get("release", {})})
                return
            if route == "/api/export/bundle":
                from export_bundle import bundle, select_latest
                query=parse_qs(urlparse(self.path).query)
                try:
                    scope=query.get('scope',['episode'])[0]
                    if scope not in {'episode','project'}:raise ValueError('Unsupported scope')
                    choice=query.get('tracks',['both'])[0]
                    if choice not in {'both','standard','sdh'}:raise ValueError('Unsupported tracks')
                    episodes=[self.episode]
                    if scope=='project':
                        project=query.get('project',[self.episode['project_id']])[0]
                        episodes=select_latest([e for e in library.snapshot()['episodes'] if e['project_id']==project])
                    payload=bundle(episodes,('standard','sdh') if choice=='both' else (choice,),query.get('format',['itt'])[0],query.get('offset',['0'])[0])
                    self.send_response(200);self.send_header('Content-Type','application/zip')
                    self.send_header('Content-Disposition','attachment; filename="subtitles_'+scope+'.zip"')
                    self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
                except (ValueError,OSError,KeyError,ZeroDivisionError) as exc:self.json_response({'error':str(exc)},400)
                return
            if route == "/api/export/itt":
                query = parse_qs(urlparse(self.path).query)
                track = query.get("track", ["sdh"])[0]
                if track not in {"standard", "sdh"}:
                    self.send_error(400); return
                state = read_state(self.state_path)
                issues = check(state[track], self.frame_rate, self.duration, state.get("sourceManifest", {}).get(track),state.get("reviewPolicy",{}).get("songSpeedAdvisory",False),state.get("preferredSpellings"),selected_profile(state))
                draft = query.get("draft", ["0"])[0] == "1"
                blockers = state.get("release", {}).get("blockers", [])
                from quality_gate import report
                gate=report(state,self.duration)
                song_issues=gate.get("song_issues",[])
                blockers=gate.get("release_blockers",blockers)
                if not draft and (blocking_issues(issues) or blockers or song_issues or not state.get("release", {}).get("content_verified")):
                    self.json_response({"error": "Preflight incomplete; review draft available", "issues": issues, "blockers": blockers, "song_issues": song_issues}, 409); return
                name = ("REVIEW_DRAFT_" if draft else "") + track + ".itt"
                dest = self.project / name
                write_itt(state[track], dest, self.frame_rate, state.get("targetLanguage", "en-US"))
                record(self.project,"itt_exported",reason="Review draft export" if draft else "Delivery preflight passed",actor="workbench",details={"track":track,"file":name,"draft":draft})
                body = dest.read_bytes()
                self.send_response(200); self.send_header("Content-Type", "application/ttml+xml; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="'+name+'"')
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            if route == "/api/state":
                self.json_response(read_state(self.state_path))
                return
            if route == "/api/sounds":
                rows = []
                if self.sounds_path and self.sounds_path.exists():
                    with self.sounds_path.open(encoding="utf-8-sig", newline="") as f:
                        rows = list(csv.DictReader(f))
                decisions_path = self.project / "sound_review_state.json"
                decisions = json.loads(decisions_path.read_text(encoding="utf-8")) if decisions_path.exists() else {}
                for i, row in enumerate(rows, 1):
                    row["id"] = str(i)
                    clip = Path(row.get("clip_file", ""))
                    if clip.is_absolute():
                        row["clip_file"] = ""
                    elif clip.parts and clip.parts[0] != "clips":
                        row["clip_file"] = (Path("clips") / clip).as_posix()
                self.json_response({"candidates": rows, "decisions": decisions, "soundToken": sound_token(self.project), "needsCompose":(self.project/"sound_composition_pending").exists()})
                return
            # Only review media and subtitle exports are public; state has explicit APIs.
            resource=(self.project/unquote(route).lstrip('/')).resolve()
            if not resource.is_relative_to(self.project.resolve()) or not resource.is_file() or resource.suffix.lower() not in {'.mp3','.srt','.itt','.vtt'}:
                self.send_error(404);return
            return super().do_GET()

        def json_response(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_HEAD(self):
            if not self.local_request():return
            try:self.select_episode()
            except (ValueError,OSError):self.send_error(404);return
            if urlparse(self.path).path == "/video":
                self.serve_video(head=True)
                return
            super().do_HEAD()

        def serve_video(self, head: bool = False):
            size = self.video.stat().st_size
            start, end, status = 0, size - 1, 200
            rng = self.headers.get("Range")
            if rng:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
                if not match:
                    self.send_error(416)
                    return
                a, b = match.groups()
                if a:
                    start = int(a)
                    end = int(b) if b else end
                elif b:
                    start = max(0, size - int(b))
                if start >= size or end < start:
                    self.send_error(416)
                    return
                end, status = min(end, size - 1), 206
            length = end - start + 1
            self.send_response(status)
            self.send_header("Content-Type", mimetypes.guess_type(self.video.name)[0] or "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if head:
                return
            with self.video.open("rb") as f:
                f.seek(start)
                left = length
                while left:
                    chunk = f.read(min(1024 * 1024, left))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        break
                    left -= len(chunk)

        def do_POST(self):
            if not self.local_request():return
            if urlparse(self.path).path == '/api/provider':
                self.connection.settimeout(10)
                if not secrets.compare_digest(self.headers.get('X-Config-Token',''),config_token):
                    self.send_error(403);return
                if library.processes or library.query("SELECT id FROM episodes WHERE status IN ('running','queued')"):
                    self.json_response({'error':'Pause production jobs before changing provider configuration.'},409);return
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<16384 or self.headers.get_content_type()!='application/json':raise ValueError('Invalid request')
                    data=json.loads(self.rfile.read(length))
                    with write_lock: result=save_provider(data)
                    self.json_response(result)
                except (ValueError,KeyError,OSError):
                    self.json_response({'error':'Configuration could not be saved. Check HTTPS endpoint, model names and local permissions.'},400)
                return
            if urlparse(self.path).path.startswith('/api/library'):
                self.library_post();return
            try:self.select_episode()
            except (ValueError,OSError):self.send_error(404);return
            if self.episode['status']!='ready':
                self.json_response({'error':'Episode is still being prepared'},409);return
            self.connection.settimeout(20)
            with write_lock:self.save_post()

        def library_post(self):
            route=urlparse(self.path).path
            try:
                length=int(self.headers.get('Content-Length','0'))
                if route=='/api/library/upload':
                    name=Path(parse_qs(urlparse(self.path).query).get('name',[''])[0]).name
                    if Path(name).suffix.lower() not in {'.mp4','.mov','.mkv','.m4v','.docx','.txt','.md','.srt'} or not 0<length<=20*1024**3:
                        raise ValueError('Unsupported file or file exceeds 20 GB')
                    folder=library.root/'imports'/uuid.uuid4().hex;folder.mkdir(parents=True)
                    dest=folder/name;tmp=folder/'upload.partial'
                    try:
                        with tmp.open('wb') as f:
                            remaining=length
                            while remaining:
                                chunk=self.rfile.read(min(1024*1024,remaining))
                                if not chunk:raise ValueError('Upload interrupted')
                                f.write(chunk);remaining-=len(chunk)
                        tmp.replace(dest)
                    finally:
                        if tmp.exists():tmp.unlink()
                    self.json_response({'path':str(dest)});return
                if not 0<length<100000:raise ValueError('Invalid request size')
                data=json.loads(self.rfile.read(length))
                if route=='/api/library/projects':result={'id':library.project(data['name'],data['settings'])}
                elif route=='/api/library/link':
                    from library_links import link
                    result=link(library,data['root'])
                elif route=='/api/library/enqueue':
                    from provider_settings import require_production_provider
                    require_production_provider(library.effective_settings(data['project_id']),data['entries'],provider_status(library.key_zip))
                    result={'ids':library.enqueue(data['project_id'],data['entries'])}
                elif route=='/api/library/action':result={'ids':library.action(data['id'],data['action'])}
                else:self.send_error(404);return
                self.json_response(result)
            except (ValueError,KeyError,OSError) as exc:self.json_response({'error':str(exc)},400)

        def save_post(self):
            route = urlparse(self.path).path
            if route == "/api/bilingual":
                from bilingual import save, Conflict
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<5000000 or self.headers.get_content_type()!='application/json':raise ValueError('Invalid request')
                    data=json.loads(self.rfile.read(length))
                    result=save(self.project,data,self.duration)
                    self.json_response(result)
                except Conflict:
                    self.json_response({'error':'本集已在其他窗口修改，请刷新后核对；未覆盖新版。'},409)
                except (ValueError,TypeError,KeyError):
                    self.json_response({'error':'字幕格式或时间无效，未保存。'},400)
                return
            if route not in ("/api/state", "/api/review", "/api/sounds/apply", "/api/sounds/preview"):
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 5_000_000:
                    self.send_error(413)
                    return
                data = json.loads(self.rfile.read(length))
                if route == "/api/state":
                    if not isinstance(data, dict) or any(not isinstance(data.get(k), list) for k in ("standard", "sdh")):
                        self.send_error(400)
                        return
                    if data.get("subtitleSpec") not in {"prime", "amazon_itt_children_13", "amazon_itt_children_17_120", "amazon_itt_adult_20_220", "custom"}:
                        data["subtitleSpec"] = "prime"
                    for track in ("standard", "sdh"):
                        for cue in data[track]:
                            if not isinstance(cue.get("text"), str) or not isinstance(cue.get("start"), (int, float)) or not isinstance(cue.get("end"), (int, float)) or cue["start"] < 0 or cue["end"] <= cue["start"] or cue["end"] > self.duration + 1:
                                self.send_error(400, "Invalid subtitle cue")
                                return
                elif not isinstance(data, dict) or any(not isinstance(v, dict) or v.get("status") not in ({"", "KEEP", "REVISE", "REMOVE"} if route in {"/api/review", "/api/sounds/preview"} else {"KEEP", "REVISE", "REMOVE"}) for v in data.values()):
                    self.send_error(400)
                    return
            except Exception:
                self.send_error(400)
                return

            if route != "/api/state":
                if not self.headers.get('X-State-Token') or not self.headers.get('X-Sound-Token'):
                    self.json_response({'error':'Reload this older workbench page before saving sound decisions.'},428);return
                if self.headers['X-State-Token'] != read_state(self.state_path).get('_saveToken') or self.headers['X-Sound-Token'] != sound_token(self.project):
                    self.json_response({'error':'Episode changed; reload before saving sound decisions.'},409);return
            if route == "/api/state":
                old = read_state(self.state_path)
                if data.get('_saveToken') != old.get('_saveToken'):
                    self.json_response({'error':'This episode changed in another window. Reload before saving.'},409);return
                data.pop('_saveToken',None)
                for track in ("standard", "sdh"):
                    previous = {c.get("id"): c for c in old.get(track, [])}
                    for cue in data[track]:
                        prior = previous.get(cue.get("id"), {})
                        for key in ("sourceText", "sourceGroup", "sourceEvidence", "songMaster", "songMasterDigest", "songMasterStatus", "songRecordingMatch"):
                            if key in prior:
                                cue[key] = prior[key]
                if "sourceManifest" in old:
                    data["sourceManifest"] = old["sourceManifest"]
                if "songLibrary" in old:
                    data["songLibrary"] = old["songLibrary"]
                release = old.get("release", {})
                if any(old.get(k) != data.get(k) for k in ("standard", "sdh", "subtitleSpec", "targetLanguage")):
                    release = {**release, "content_verified": False}
                data["release"] = release
                from evidence_gate import reconcile_edit
                data=reconcile_edit(old,data)
                data=prepare_layout(data)
                record(self.project,"subtitle_saved",old,data,reason="Saved through workbench; no separate reason supplied. Per-cue records retain review ownership.",actor="workbench")
                tmp = self.state_path.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                tmp.replace(self.state_path)
                language = re.sub(r"[^A-Za-z0-9_-]", "", str(data.get("targetLanguage", "en-US"))) or "en-US"
                write_srt(data["standard"], self.project / f"{language}_Standard.srt")
                write_srt(data["sdh"], self.project / f"{language}_SDH.srt")
                self.json_response({"saved": True, "saveToken":read_state(self.state_path).get("_saveToken"), "state":read_state(self.state_path)})
                return
            if route == "/api/review":
                dest = self.project / "sound_review_state.json"
                previous=json.loads(dest.read_text()) if dest.exists() else {}
                record(self.project,"sound_decisions_saved",previous,data,reason="Saved sound judgments; per-item reasons are in note fields.",actor="workbench")
                if previous != data:(self.project/"sound_composition_pending").touch()
                tmp = dest.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                tmp.replace(dest)
                if previous != data and any(d.get('reviewer')=='human' and d.get('humanApproved') is True for d in data.values()) and self.sounds_path and self.sounds_path.exists():
                    with self.sounds_path.open(encoding='utf-8-sig') as source:rows=list(csv.DictReader(source))
                    identity_worker.submit(persist_confirmed,self.video,rows,data)
                self.json_response({"saved": True, "saveToken":read_state(self.state_path).get("_saveToken"), "soundToken":sound_token(self.project)})
                return
            rows = []
            if self.sounds_path and self.sounds_path.exists():
                with self.sounds_path.open(encoding="utf-8-sig", newline="") as f:
                    rows = list(csv.DictReader(f))
            if route == "/api/sounds/apply" and (len(data) != len(rows) or any(str(i) not in data or data[str(i)].get("status") not in {"KEEP", "REVISE", "REMOVE"} for i in range(1, len(rows) + 1))):
                self.send_error(409, "Review every candidate before applying")
                return
            state = read_state(self.state_path)
            previous_state=json.loads(json.dumps(state))
            try:
                state = compose_sdh(state, rows, data, scene_times(self.project / "scene_changes.txt"))
            except ValueError as exc:
                self.send_error(400, str(exc));return
            record(self.project,"sound_decisions_applied",previous_state,state,reason="Compose review SDH from KEEP/REVISE only; pending candidates excluded, model ownership retained.",actor="workbench")
            tmp=self.state_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.state_path)
            language = re.sub(r"[^A-Za-z0-9_-]", "", str(state.get("targetLanguage", "en-US"))) or "en-US"
            write_srt(state["sdh"], self.project / f"{language}_SDH.srt")
            (self.project / "sound_review_state.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            (self.project/"sound_composition_pending").unlink(missing_ok=True)
            self.json_response({"saved": True, "saveToken":read_state(self.state_path).get("_saveToken"), "soundToken":sound_token(self.project)})

        def log_message(self, fmt, *args):
            print(fmt % args)

    Handler.library=library
    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path, help="Path to the final episode video")
    parser.add_argument("--project", required=True, type=Path, help="Folder for editable state and exported SRT files")
    parser.add_argument("--sounds-csv", type=Path, help="Optional candidate CSV; clip files should be in PROJECT/clips/")
    parser.add_argument("--title", default="Subtitle Review Workbench")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--key-zip",type=Path,help="Optional authorized credential bundle")
    parser.add_argument("--library",type=Path,help="Persistent projects and background jobs")
    parser.add_argument("--port", type=int, default=8877)
    args = parser.parse_args()
    if not args.video.is_file() and not (args.project/'workbench_state.json').is_file():
        parser.error(f"Video not found: {args.video}")
    if args.sounds_csv and not args.sounds_csv.is_file():
        parser.error(f"Sound candidate CSV not found: {args.sounds_csv}")
    handler = make_handler(args)
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    print(f"Open http://{args.host}:{args.port}  |  project: {args.project.resolve()}")
    try:
        ThreadingHTTPServer((args.host, args.port), handler).serve_forever()
    except KeyboardInterrupt:
        print("Workbench stopped.")
    finally:
        handler.library.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
