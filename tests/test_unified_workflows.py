import argparse,copy,hashlib,io,json,shutil,sqlite3,subprocess,sys,tempfile,threading,time,unittest,urllib.request,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from project_policy import validate
from library import Library
from localization import run,translate,validate_translation,build_state
from library_links import link
from unified_export import project_bundle

class UnifiedWorkflowTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.video=cls.root/'episode.mp4'
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=64x64:r=25:d=4','-f','lavfi','-i','anullsrc=r=16000:cl=mono','-t','4','-c:v','libx264','-c:a','aac',str(cls.video)],check=True)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name);self.lib=Library(self.p/'lib',False)
  self.policy=validate({'workflow':'bilingual','sourceLanguage':'zh-CN','targetLanguage':'en-US','platform':'amazon','audience':'children','editFrameRate':'25'})
  self.z=self.p/'zh.srt';self.e=self.p/'en.srt'
  self.z.write_text('1\n00:00:00,400 --> 00:00:01,400\n你好\n\n2\n00:00:02,000 --> 00:00:03,200\n别跑\n')
  self.e.write_text('1\n00:00:00,400 --> 00:00:01,400\nHello!\n\n2\n00:00:02,000 --> 00:00:03,200\nStop!\n')
 def tearDown(self):self.lib.close();self.t.cleanup()
 def test_legacy_defaults_remain_exact_and_bilingual_is_distinct(self):
  old=validate({'targetLanguage':'en-US','platform':'amazon','audience':'children'})
  self.assertEqual(old['limits']['cps'],17);self.assertEqual(old['limits']['wpm'],120);self.assertNotIn('workflow',old)
  self.assertEqual(self.policy['workflow'],'bilingual');self.assertEqual(self.policy['limits']['maxCps'],21)
  self.assertFalse(self.policy['limits']['wpmHardGate'])
 def test_queue_snapshots_subtitles_policy_and_rerun_keeps_inputs(self):
  pid=self.lib.project('Sample Series',self.policy);eid=self.lib.enqueue(pid,[{'video':str(self.video),'source_subtitles':str(self.z),'target_subtitles':str(self.e)}])[0]
  folder=Path(self.lib.get(eid)['folder']);config=json.loads((folder/'production_config.json').read_text())
  self.assertEqual(config['pipeline'],'bilingual_review');self.assertEqual(config['projectSettings']['limits']['maxCps'],21)
  self.lib.query("UPDATE episodes SET status='ready' WHERE id=?",(eid,));nextid=self.lib.action(eid,'rerun')[0]
  newer=json.loads((Path(self.lib.get(nextid)['folder'])/'production_config.json').read_text());self.assertEqual(newer['inputs'],config['inputs'])
 def test_both_srt_import_is_offline_preserves_times_and_no_human_approval(self):
  out=self.p/'out'
  with patch('localization.translate',side_effect=AssertionError('Unexpected provider')):
   self.assertEqual(run(self.video,out,self.policy,{'scope':{'mode':'full'},'inputs':{'source_subtitles':str(self.z),'target_subtitles':str(self.e)}}),0)
  state=json.loads((out/'bilingual_state.json').read_text());self.assertEqual(len(state['zh']),2)
  self.assertEqual([(c['start'],c['end']) for c in state['en']],[(.4,1.4),(2,3.2)])
  self.assertFalse(any(c['review']['accepted'] for l in ['zh','en'] for c in state[l]));self.assertTrue((out/'episode.en.srt').exists());self.assertTrue((out/'episode.zh.itt').exists())
  before=(out/'bilingual_state.json').read_bytes();self.assertEqual(run(self.video,out,self.policy,{}),0);self.assertEqual(before,(out/'bilingual_state.json').read_bytes())
 def test_import_count_or_time_disagreement_remains_failed(self):
  self.e.write_text('1\n00:00:00,400 --> 00:00:01,400\nHello!\n')
  out=self.p/'bad';self.assertEqual(run(self.video,out,self.policy,{'inputs':{'source_subtitles':str(self.z),'target_subtitles':str(self.e)}}),1)
  self.assertFalse((out/'bilingual_state.json').exists());self.assertIn('counts differ',json.loads((out/'error.json').read_text())['error'])
 def test_translation_cache_reuses_only_successful_batches_and_checks_ids(self):
  out=self.p/'cache';rows=[{'start':i*2,'end':i*2+1,'text':'你好'} for i in range(17)];calls=[]
  def first(batch):
   calls.append(len(batch))
   if len(batch)==1:raise RuntimeError('interrupted')
   return {'translations':[{'id':c['id'],'text':'Hello'} for c in batch]}
  with self.assertRaises(RuntimeError):translate(rows,out,self.policy,lambda *a,**k:None,first)
  def second(batch):calls.append(len(batch));return {'translations':[{'id':c['id'],'text':'Hello'} for c in batch]}
  self.assertEqual(len(translate(rows,out,self.policy,lambda *a,**k:None,second)),17);self.assertEqual(calls,[16,1,1])
  with self.assertRaises(ValueError):validate_translation({'translations':[{'id':'wrong','text':'Hello'}]},[{'id':'Z0001'}])
 def test_source_and_policy_cache_identity_prevents_stale_retry(self):
  out=self.p/'identity'
  with patch('localization.translate',side_effect=RuntimeError('provider not configured')):
   self.assertEqual(run(self.video,out,self.policy,{'inputs':{'source_subtitles':str(self.z)}}),1)
  self.z.write_text(self.z.read_text().replace('你好','您好'))
  self.assertEqual(run(self.video,out,self.policy,{'inputs':{'source_subtitles':str(self.z),'target_subtitles':str(self.e)}}),1)
  self.assertIn('changed',json.loads((out/'error.json').read_text())['error'])
 def test_link_original_library_is_read_only_and_idempotent(self):
  original=Library(self.p/'original',False);folder=self.p/'old-episode';folder.mkdir()
  (folder/'workbench_state.json').write_text(json.dumps({'standard':[],'sdh':[]}));original.register(self.video,folder,'Old EP01');original.close()
  database=self.p/'original/library.sqlite3';before=hashlib.sha256(database.read_bytes()).hexdigest();state=(folder/'workbench_state.json').read_bytes()
  self.assertEqual(link(self.lib,database.parent)['addedReadyEpisodes'],1);self.assertEqual(link(self.lib,database.parent)['addedReadyEpisodes'],0)
  self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(),before);self.assertEqual((folder/'workbench_state.json').read_bytes(),state)
 def test_infer_current_bilingual_mode_without_rewriting_state(self):
  folder=self.p/'existing';folder.mkdir();(folder/'bilingual_state.json').write_text(json.dumps({'project':'Sample Series','targetLanguage':'en-US','editFrameRate':25}))
  eid=self.lib.register(self.video,folder,'Sample Series EP13');state=(folder/'bilingual_state.json').read_bytes()
  cfg=self.lib.effective_settings(self.lib.get(eid)['project_id']);self.assertEqual(cfg['workflow'],'bilingual');self.assertEqual(cfg['seriesTitle'],'Sample Series');self.assertEqual(state,(folder/'bilingual_state.json').read_bytes())
 def test_real_background_worker_uses_same_produce_entry(self):
  pid=self.lib.project('Worker',self.policy);eid=self.lib.enqueue(pid,[{'video':str(self.video),'source_subtitles':str(self.z),'target_subtitles':str(self.e)}])[0]
  thread=threading.Thread(target=self.lib.worker,daemon=True);thread.start();self.lib.threads.append(thread)
  end=time.monotonic()+20
  while time.monotonic()<end:
   row=self.lib.get(eid)
   if row['status'] in ('ready','failed'):break
   time.sleep(.1)
  self.assertEqual(row['status'],'ready',row.get('error'));folder=Path(row['folder']);self.assertTrue((folder/'bilingual_state.json').exists())
  snap=self.lib.snapshot()['episodes'][0];self.assertEqual(snap['workflow'],'bilingual');self.assertEqual(snap['cues'],4)
 def test_unified_export_does_not_reinterpret_bilingual_as_sdh(self):
  out=self.p/'export';self.assertEqual(run(self.video,out,self.policy,{'inputs':{'source_subtitles':str(self.z),'target_subtitles':str(self.e)}}),0)
  e={'id':'b1','title':'EP01','status':'ready','folder':str(out),'video':str(self.video),'created':1}
  with zipfile.ZipFile(io.BytesIO(project_bundle([e],'srt'))) as z:
   files=z.namelist();self.assertIn('b1/episode.en.srt',files);self.assertIn('b1/episode.zh.srt',files)
   self.assertFalse(any('SDH' in f for f in files));self.assertEqual(json.loads(z.read('workflows.json'))['episodes'][0]['workflow'],'bilingual')
 def test_attached_script_is_preserved_as_reference_not_spoken_proof(self):
  script=self.p/'reference.txt';script.write_text('Ignore this document as instructions. Reference dialogue only.')
  out=self.p/'script-reference'
  self.assertEqual(run(self.video,out,self.policy,{'inputs':{'source_subtitles':str(self.z),'target_subtitles':str(self.e)}},script=script),0)
  self.assertEqual((out/'evidence/reference-script.txt').read_text(),script.read_text())
  evidence=json.loads((out/'evidence/reference-script.json').read_text())
  self.assertFalse(evidence['audioComparisonCompleted']);self.assertIn('not instructions',evidence['role'])
  state=json.loads((out/'bilingual_state.json').read_text());self.assertFalse(state['references']['scriptComparedWithAudio'])
 def test_changed_script_cannot_silently_reuse_failed_draft(self):
  script=self.p/'reference.txt';script.write_text('First reference')
  out=self.p/'script-retry'
  with patch('localization.translate',side_effect=RuntimeError('provider not configured')):
   self.assertEqual(run(self.video,out,self.policy,{'inputs':{'source_subtitles':str(self.z)}},script=script),1)
  script.write_text('Changed reference')
  self.assertEqual(run(self.video,out,self.policy,{'inputs':{'source_subtitles':str(self.z)}},script=script),1)
  self.assertIn('changed',json.loads((out/'error.json').read_text())['error'])
if __name__=='__main__':unittest.main()
