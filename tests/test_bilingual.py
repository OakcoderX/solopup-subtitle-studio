import sys,json,tempfile,unittest,zipfile,io,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from bilingual import read,save,metrics,signature,Conflict,export_bundle,itt_files,itt_bundle,write_itt_exports,srt_files,srt_bundle
class BilingualReview(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)
  s={'policy':{'targetCps':17,'maxCps':21},'editFrameRate':25,'syllableLexicon':{'hello':[2]},'zh':[{'id':'z1','pairId':'p1','text':'你好','start':1,'end':3,'sourceEvidence':{'ocr':'immutable'}}],'en':[{'id':'e1','pairId':'p1','text':'Hello!','start':1,'end':3}]}
  for lang in ['zh','en']:
   for c in s[lang]:c['review']={'accepted':True,'reviewer':'user','signature':signature(c)}
  (self.p/'bilingual_state.json').write_text(json.dumps(s))
 def tearDown(self):self.tmp.cleanup()
 def test_source_edit_invalidates_both_and_keeps_evidence(self):
  s=read(self.p);s['zh'][0]['text']='您好';s['zh'][0]['sourceEvidence']={'ocr':'forged'};s['policy']['maxCps']=99
  r=save(self.p,s,10)['state']
  self.assertFalse(r['zh'][0]['review']['accepted']);self.assertFalse(r['en'][0]['review']['accepted'])
  self.assertEqual(r['zh'][0]['sourceEvidence'],{'ocr':'immutable'});self.assertEqual(r['policy']['maxCps'],21)
 def test_target_edit_preserves_source_review(self):
  s=read(self.p);s['en'][0]['text']='Hi!';r=save(self.p,s,10)['state'];self.assertFalse(r['en'][0]['review']['accepted']);self.assertTrue(r['zh'][0]['review']['accepted'])
 def test_browser_numeric_serialization_is_not_a_source_edit(self):
  s=read(self.p)
  for lang in ['zh','en']:
   for c in s[lang]:c['start']=float(c['start']);c['end']=float(c['end'])
  r=save(self.p,s,10)['state']
  self.assertTrue(r['zh'][0]['review']['accepted']);self.assertTrue(r['en'][0]['review']['accepted'])
  self.assertFalse(r['en'][0].get('translationSourceChanged',False))
 def test_stale_save_rejected(self):
  s=read(self.p);save(self.p,copy.deepcopy(s),10)
  with self.assertRaises(Conflict):save(self.p,s,10)
 def test_nonfinite_time_and_dropped_cue_rejected(self):
  s=read(self.p);s['zh'][0]['start']=float('nan')
  with self.assertRaises(ValueError):save(self.p,s,10)
  s=read(self.p);s['zh']=[]
  with self.assertRaises(ValueError):save(self.p,s,10)
 def test_no_wpm_gate_and_speed_bands(self):
  s=read(self.p);s['en'][0]['text']='x'*38
  self.assertFalse(any('21 CPS' in f for f in metrics(s)['en']['e1']['flags']))
  self.assertTrue(any('17–21' in f for f in metrics(s)['en']['e1']['warnings']))
  s['en'][0]['text']='x'*44;self.assertIn('超过21 CPS',metrics(s)['en']['e1']['flags'])
 def test_export_has_two_separate_languages_and_no_fake_final(self):
  z=zipfile.ZipFile(io.BytesIO(export_bundle(read(self.p))))
  self.assertIn('你好',z.read('zh_REVIEW_DRAFT.srt').decode());self.assertIn('Hello',z.read('en_REVIEW_DRAFT.srt').decode())
  self.assertEqual(json.loads(z.read('QA_REVIEW_DRAFT.json'))['status'],'REVIEW_DRAFT')
 def test_two_itt_languages_keep_exact_unicode_video_prefix(self):
  from xml.etree import ElementTree as E
  s=read(self.p);s['source']={'path':'/test/sample 示例片段（上）-v1.mp4'}
  files=itt_files(s)
  self.assertEqual(set(files),{'sample 示例片段（上）-v1.zh.itt','sample 示例片段（上）-v1.en.itt'})
  for lang,label,text in [('zh','zh-CN','你好'),('en','en-US','Hello!')]:
   root=E.fromstring(files['sample 示例片段（上）-v1.'+lang+'.itt'])
   self.assertEqual(root.attrib['{http://www.w3.org/XML/1998/namespace}lang'],label)
   self.assertEqual(root.attrib['{http://www.w3.org/ns/ttml#parameter}frameRate'],'25')
   p=root.find('.//{http://www.w3.org/ns/ttml}p');self.assertEqual(''.join(p.itertext()),text)
   self.assertEqual(p.attrib['begin'],'00:00:01:00')
  z=zipfile.ZipFile(io.BytesIO(itt_bundle(s)));self.assertEqual(set(z.namelist()),set(files))
 def test_itt_single_track_and_saved_revision_refresh(self):
  s=read(self.p);self.assertEqual(list(itt_files(s,'en')),['episode.en.itt'])
  with self.assertRaises(ValueError):itt_files(s,'sdh')
  s['en'][0]['text']='Revised';save(self.p,s,10)
  self.assertIn(b'Revised',(self.p/'episode.en.itt').read_bytes())
  self.assertEqual(json.loads((self.p/'ITT_EXPORT_REVIEW_STATUS.json').read_text())['status'],'REVIEW_DRAFT')
 def test_srt_separate_languages_exact_name_and_timing(self):
  s=read(self.p);s['source']={'path':'/test/sample 示例片段（上）-v1.mp4'}
  s['zh'][0]['start']=1.04;s['en'][0]['start']=1.08
  files=srt_files(s);self.assertEqual(len(files),2)
  self.assertEqual(files['sample 示例片段（上）-v1.zh.srt'].decode(),'1\n00:00:01,040 --> 00:00:03,000\n你好\n')
  self.assertIn(b'00:00:01,080',files['sample 示例片段（上）-v1.en.srt'])
  self.assertEqual(len(srt_files(s,'en')),1)
  with self.assertRaises(ValueError):srt_files(s,'sdh')
  z=zipfile.ZipFile(io.BytesIO(srt_bundle(s)));self.assertEqual(set(z.namelist()),set(files))
  for name,data in files.items():self.assertEqual(z.read(name),data)
 def test_check_signature_invalidates_changed_cue(self):
  s=read(self.p);s['zh'][0]['text']='再见';self.assertFalse(metrics(s)['zh']['z1']['checked'])
if __name__=='__main__':unittest.main()
