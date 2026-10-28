import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from fidelity import audit
class RepeatedQuantityTest(unittest.TestCase):
 def cue(self,text):return {'id':'A','sourceGroup':'A','sourceText':'fifty grams and fifty milliliters','text':text,'start':0,'end':4,'numberFormatting':[{'from':'fifty','to':'50'}]}
 def test_repeated(self):self.assertEqual(audit([self.cue('50 grams and 50 milliliters')]),[])
 def test_partial(self):self.assertEqual(audit([self.cue('50 grams and fifty milliliters')]),[])
 def test_nested_number_phrase(self):
  c=self.cue('50 grams and 250 milliliters');c['sourceText']='fifty grams and two hundred fifty milliliters';c['numberFormatting'].append({'from':'two hundred fifty','to':'250'});self.assertEqual(audit([c]),[])
 def test_wrong_quantity(self):self.assertTrue(audit([self.cue('50 grams and 60 milliliters')]))
 def test_missing_word(self):self.assertTrue(audit([self.cue('50 grams 50 milliliters')]))
 def test_forged_mapping(self):
  c=self.cue('60 grams and 60 milliliters');c['numberFormatting']=[{'from':'fifty','to':'60'}];self.assertTrue(audit([c]))
