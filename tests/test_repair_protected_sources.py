import sys,tempfile,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from repair_apply import reviewed_candidate
class ProtectedSourcesTests(unittest.TestCase):
 def run_proposal(self,text,new,**extra):
  c=dict(id='a',start=1,end=3,text=text,sourceText=text,sourceGroup='a',**extra)
  s=dict(standard=[c],sdh=[c],release={},projectSettings={'protectedNames':['Iris','Noah']})
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'review.json';p.write_text(json.dumps({'parsed':{'verdicts':[dict(id='a',action='CORRECT',text=new,uncertain=False,reason='Sounds plausible')]}}))
   return reviewed_candidate(s,[p])[0]['standard'][0]
 def test_explicitly_protected_names_are_not_merged(self):
  c=self.run_proposal('Iris, Noah, can you help?','IrisNoah, can you help?')
  self.assertEqual(c['text'],'Iris, Noah, can you help?');self.assertTrue(c['audioAdjudication']['uncertain'])
 def test_verified_song_changes_require_master_adjudication(self):
  c=self.run_proposal('Bring every empty folder','Bring all empty folders',songMaster='sample_song_v1')
  self.assertEqual(c['text'],'Bring every empty folder');self.assertTrue(c['audioAdjudication']['uncertain'])
 def test_other_supported_correction_is_not_blanket_blocked(self):
  c=self.run_proposal('Riley is ready',"Riley's ready")
  self.assertEqual(c['text'],"Riley's ready")
if __name__=='__main__':unittest.main()
