import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from review_schema import normalize_adjudications
class LayeredSchemaTest(unittest.TestCase):
 def test_explicit_verdict_moved_without_changing_words(self):
  row={'id':'R1','verdict':'correct','corrected_text':'Exact words!','uncertain':False}
  source={'speech':[row,{'start':10,'text':'New speech'}],'cue_reviews':[]}
  result=normalize_adjudications(source,{'R1'})
  self.assertEqual(result['cue_reviews'],[row]);self.assertEqual(result['speech'],[{'start':10,'text':'New speech'}]);self.assertEqual(len(source['speech']),2)
 def test_unrequested_or_untyped_rows_are_not_answers(self):
  rows=[{'id':'R2','verdict':'agree'},{'id':'R1','text':'Words'}]
  result=normalize_adjudications({'speech':rows,'cue_reviews':[]},{'R1'})
  self.assertEqual(result['cue_reviews'],[]);self.assertEqual(result['speech'],rows)
