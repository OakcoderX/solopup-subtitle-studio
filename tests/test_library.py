import argparse,copy,json,sys,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from library import Library
from produce import assemble
from server import make_handler

class LibraryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.video=self.root/'clip.mp4';self.video.write_bytes(b'test')
  self.lib=Library(self.root/'library',False);self.pid=self.lib.project('Series')
 def tearDown(self):self.lib.close();self.tmp.cleanup()
 def enqueue(self,n=1):return self.lib.enqueue(self.pid,[{'video':str(self.video),'title':str(i)}for i in range(n)])
 def test_batch_validation_is_atomic(self):
  with self.assertRaises(ValueError):self.lib.enqueue(self.pid,[{'video':str(self.video)},{'video':'/missing.mp4'}])
  self.assertFalse(self.lib.snapshot()['episodes'])
  with self.assertRaises(ValueError):self.enqueue(6)
 def test_five_isolated_folders_pause_resume_and_restart(self):
  ids=self.enqueue(5);self.assertEqual(len({self.lib.get(i)['folder']for i in ids}),5)
  self.lib.action(ids[0],'pause');self.lib.action(ids[0],'resume');self.lib.query("UPDATE episodes SET status='running' WHERE id=?",(ids[0],))
  self.lib.action(ids[1],'pause');self.lib.close();self.lib=Library(self.root/'library',False)
  self.assertEqual(self.lib.get(ids[0])['status'],'queued');self.assertEqual(self.lib.get(ids[1])['status'],'paused')
 def test_rerun_never_replaces_review(self):
  eid=self.enqueue()[0];self.lib.query("UPDATE episodes SET status='ready' WHERE id=?",(eid,))
  path=Path(self.lib.get(eid)['folder'])/'workbench_state.json';path.write_text('{"sdh": []}')
  newer=self.lib.action(eid,'rerun')[0];self.assertNotEqual(eid,newer);self.assertEqual(path.read_text(),'{"sdh": []}')
 def test_only_one_service_owns_library(self):
  with self.assertRaises(RuntimeError):Library(self.root/'library',False)
 def test_overlap_witnesses_keep_conflicts(self):
  files=[]
  for i,text in enumerate(['First, add milk.','First, add milk.','Then add milk.']):
   p=self.root/f'{i}.json';p.write_text(json.dumps({'offset_seconds':0,'parsed':{'speech_segments':[{'start':1,'end':2,'text':text}]}}));files.append(p)
  rows,_=assemble(files,24,10);self.assertEqual(len(rows),2);self.assertIn('unresolved',rows[1])

class EpisodeHttpTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.video=cls.root/'v.mp4';cls.video.write_bytes(b'0123456789')
  cls.lib=Library(cls.root/'library',False);cls.folders=[];cls.ids=[]
  for n in range(2):
   folder=cls.root/str(n);folder.mkdir();cls.folders.append(folder)
   (folder/'workbench_state.json').write_text(json.dumps({'standard':[],'sdh':[{'id':'D1','start':0,'end':1,'text':f'Hello {n}','sourceText':f'Hello {n}'}],'subtitleSpec':'prime'}))
   cls.ids.append(cls.lib.register(cls.video,folder,f'Episode {n}'))
  args=argparse.Namespace(project=cls.folders[0],video=cls.video,sounds_csv=None,title='Episode 0',library_instance=cls.lib)
  with patch('server.get_duration',return_value=10),patch('server.subprocess.check_output',return_value='24/1'):
   handler=make_handler(args)
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),handler);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.base='http://127.0.0.1:'+str(cls.server.server_port)
 def test_export_endpoints_remain_available_with_waveform_handler(self):
  base='/episode/'+self.ids[0]
  status,body=self.call(base+'/api/export/itt?track=sdh&draft=1')
  self.assertEqual(status,200);self.assertIn(b'<tt',body)
  status,body=self.call(base+'/api/export/itt?track=sdh')
  self.assertEqual(status,409);self.assertIn(b'Preflight incomplete',body)
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.lib.close();cls.tmp.cleanup()
 def call(self,path,data=None,headers=None):
  headers=dict(headers or {})
  if data is not None and any(path.endswith(x) for x in ['/api/review','/api/sounds/preview','/api/sounds/apply']):
   prefix=path.split('/api/')[0];st=json.loads(self.call(prefix+'/api/state')[1]);so=json.loads(self.call(prefix+'/api/sounds')[1]);headers.setdefault('X-State-Token',st['_saveToken']);headers.setdefault('X-Sound-Token',so['soundToken'])
  req=urllib.request.Request(self.base+path,data=json.dumps(data).encode()if data is not None else None,headers=headers or {})
  try:
   with urllib.request.urlopen(req)as r:return r.status,r.read()
  except urllib.error.HTTPError as e:return e.code,e.read()
 def test_stale_sound_save_rejected(self):
  prefix='/episode/'+self.ids[0]
  data={'1':{'status':'KEEP','caption':'[laughing]'}}
  self.assertEqual(self.call(prefix+'/api/review',data,{'X-State-Token':'old','X-Sound-Token':'old'})[0],409)
 def test_assistant_decisions_do_not_hash_video(self):
  prefix='/episode/'+self.ids[0]
  with patch('server.media_key',side_effect=AssertionError('interactive video hash')):
   self.assertEqual(self.call(prefix+'/api/review',{'1':{'status':'KEEP','reviewer':'assistant'}})[0],200)
 def test_episode_routing_range_and_static_boundary(self):
  for i,eid in enumerate(self.ids):
   code,body=self.call('/episode/'+eid+'/api/state');self.assertEqual(code,200);self.assertEqual(json.loads(body)['sdh'][0]['text'],f'Hello {i}')
   code,body=self.call('/episode/'+eid+'/video',headers={'Range':'bytes=2-4'});self.assertEqual((code,body),(206,b'234'))
  self.assertEqual(self.call('/episode/'+self.ids[0]+'/workbench_state.json')[0],404)
 def test_stale_save_rejected_and_other_episode_untouched(self):
  path='/episode/'+self.ids[0]+'/api/state';state=json.loads(self.call(path)[1]);stale=copy.deepcopy(state);state['sdh'][0]['text']='Edit'
  self.assertEqual(self.call(path,state)[0],200);self.assertEqual(self.call(path,stale)[0],409)
  other=json.loads(self.call('/episode/'+self.ids[1]+'/api/state')[1]);self.assertEqual(other['sdh'][0]['text'],'Hello 1')
  saved=json.loads(self.call(path)[1]);self.assertEqual(saved['sdh'][0]['sourceText'],'Hello 0')
 def test_pending_sound_recommendation_cannot_be_applied(self):
  folder=self.folders[0];sounds=folder/'SDH_Sound_Candidates.csv';sounds.write_text('start,end,caption\n1,2,[laughing]\n')
  self.lib.query('UPDATE episodes SET sounds=? WHERE id=?',(str(sounds),self.ids[0]))
  before=(folder/'workbench_state.json').read_bytes()
  try:
   self.assertEqual(self.call('/episode/'+self.ids[0]+'/api/review',{'1':{'status':'','recommendation':'KEEP','caption':'[laughing]','reviewer':'assistant'}})[0],200)
   code,_=self.call('/episode/'+self.ids[0]+'/api/sounds/apply',{'1':{'status':'','recommendation':'KEEP','caption':'[laughing]','reviewer':'assistant'}})
   self.assertIn(code,(400,409));self.assertEqual(before,(folder/'workbench_state.json').read_bytes())
  finally:self.lib.query('UPDATE episodes SET sounds=NULL WHERE id=?',(self.ids[0],))
 def test_preview_includes_decided_sounds_even_when_others_pending(self):
  folder=self.folders[0];sounds=folder/'SDH_Sound_Candidates.csv';sounds.write_text('start,end,caption\n2,3,[laughing]\n4,5,[wind]\n')
  self.lib.query('UPDATE episodes SET sounds=? WHERE id=?',(str(sounds),self.ids[0]))
  before=(folder/'workbench_state.json').read_bytes()
  try:
   data={'1':{'status':'KEEP','reviewer':'assistant'},'2':{'status':''}}
   route='/episode/'+self.ids[0]
   self.assertEqual(self.call(route+'/api/sounds/preview',data)[0],200)
   state=json.loads(self.call(route+'/api/state')[1]);sounds=[c for c in state['sdh'] if c.get('sourceSoundId')]
   self.assertEqual(len(sounds),1);self.assertFalse(sounds[0]['checked']);self.assertIn('unresolved',sounds[0])
   self.assertEqual(self.call(route+'/api/sounds/preview',data)[0],200)
   state=json.loads(self.call(route+'/api/state')[1]);self.assertEqual(sum('sourceSoundId' in c for c in state['sdh']),1)
  finally:
   (folder/'workbench_state.json').write_bytes(before);self.lib.query('UPDATE episodes SET sounds=NULL WHERE id=?',(self.ids[0],))
 def test_cross_origin_write_rejected(self):
  self.assertEqual(self.call('/api/library/projects',{'name':'bad'},headers={'Origin':'http://elsewhere.example'})[0],403)
 def test_scope_is_episode_specific(self):
  path=self.folders[1]/'workbench_state.json';saved=json.loads(path.read_text());saved['scope']=[2,8];path.write_text(json.dumps(saved))
  self.assertEqual(json.loads(self.call('/episode/'+self.ids[1]+'/api/scope')[1])['scope'],[2,8])
  self.assertEqual(json.loads(self.call('/episode/'+self.ids[0]+'/api/scope')[1])['scope'],[0,10])
if __name__=='__main__':unittest.main()
