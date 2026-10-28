import copy,io,json,sys,tempfile,unittest,zipfile
from pathlib import Path
import xml.etree.ElementTree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from export_bundle import bundle, shifted,select_latest

class ExportBundleTests(unittest.TestCase):
 def test_offset_and_zip_preserve_source_and_cue_duration(self):
  rows=[{'id':'one','start':1.,'end':3.,'text':'Hello!','italic':True}];before=copy.deepcopy(rows)
  self.assertEqual(shifted(rows,'2','24')[0]['start'],3);self.assertEqual(rows,before)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);state={'standard':rows,'sdh':rows,'frameRate':'24','subtitleSpec':'prime'};(p/'workbench_state.json').write_text(json.dumps(state));raw=(p/'workbench_state.json').read_bytes()
   data=bundle([{'id':'abcdefgh','title':'EP01 synthetic','status':'ready','folder':str(p)}],offset='2')
   with zipfile.ZipFile(io.BytesIO(data)) as z:
    manifest=json.loads(z.read('manifest.json'));self.assertEqual(len(manifest['files']),2)
    for f in manifest['files']:
     self.assertIn('REVIEW_DRAFT',f['file']);root=E.fromstring(z.read(f['file']));cue=root.find('.//{http://www.w3.org/ns/ttml}p');self.assertEqual((cue.get('begin'),cue.get('end')),('00:00:03:00','00:00:05:00'));self.assertEqual(''.join(cue.itertext()),'Hello!')
   self.assertEqual(raw,(p/'workbench_state.json').read_bytes())
 def test_non_frame_aligned_and_invalid_offsets_rejected(self):
  for val in ['-1','nan','Infinity','0.01','3601']:
   with self.assertRaises((ValueError,OverflowError)):shifted([],val,'24')
 def test_saved_sound_choices_cannot_export_stale_sdh(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'sound_composition_pending').touch()
   with self.assertRaisesRegex(ValueError,'composition'):bundle([{'id':'x','title':'ep','status':'ready','folder':str(p)}])
 def test_project_latest_groups_versions_and_keeps_failed_in_manifest(self):
  rows=[{'id':'old','title':'EP02 failed old','status':'failed','created':1},{'id':'new','title':'EP02 final','status':'ready','created':2},{'id':'test','title':'EP02 smoke','status':'ready','created':3},{'id':'first','title':'EP01 final','status':'ready','created':2}]
  self.assertEqual([r['id'] for r in select_latest(rows)],['first','new'])
if __name__=='__main__':unittest.main()
