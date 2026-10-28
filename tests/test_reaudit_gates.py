import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from sound_readability import repair_minimum_frames
from sdh_validation import screen_issues
from timed_text import frame
class ReauditGates(unittest.TestCase):
 def test_minimum_is_frames_not_decimal_seconds(self):
  c={'id':'S','kind':'sound','start':110.4,'end':111.2,'text':'[squeaking]'}
  result=repair_minimum_frames([c],[],24)
  self.assertEqual(frame(result[0]['end'],24)-frame(result[0]['start'],24),20)
  self.assertEqual(result,repair_minimum_frames(result,[],24))
  self.assertEqual([c],repair_minimum_frames([c],None,24))
  self.assertEqual([c],repair_minimum_frames([c],[111.21],24))
 def test_human_lock_and_new_overlap_untouched(self):
  c={'id':'S','kind':'sound','start':0,'end':.8,'text':'[thud]','checked':True}
  self.assertEqual([c],repair_minimum_frames([c],[],24));c['checked']=False
  d={'id':'D','kind':'speech','start':.81,'end':2,'text':'Hi'}
  self.assertEqual([c,d],repair_minimum_frames([c,d],[],24))
 def test_connected_chain_not_a_seven_second_display(self):
  rows=[{'id':'A','kind':'speech','start':0,'end':6,'text':'Hello'}, {'id':'B','kind':'sound','start':5,'end':10,'text':'[wind]'}]
  self.assertFalse(any('composite_duration_long' in x['flags'] for x in screen_issues(rows,frame,24)))
  rows=[{'id':'S','kind':'sound','start':0,'end':8,'text':'[wind]'}]
  self.assertTrue(any('composite_duration_long' in x['flags'] for x in screen_issues(rows,frame,24)))
if __name__=='__main__':unittest.main()

class ScriptLayout(unittest.TestCase):
 def test_tabbed_cue_numbers_are_not_quantities(self):
  import tempfile,zipfile
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
  from character_lookup import script_text
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'script.docx'
   with zipfile.ZipFile(p,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>We need 2</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>75</w:t></w:r></w:p><w:p><w:r><w:t>275 grams</w:t></w:r></w:p></w:body></w:document>')
   self.assertEqual(script_text(p),'We need 2\n275 grams')
