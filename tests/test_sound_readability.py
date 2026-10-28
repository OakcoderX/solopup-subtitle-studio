import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from sound_readability import improve
class SoundReadability(unittest.TestCase):
 def test_extension_preserves_words_and_onset(self):
  a={'id':'s','kind':'sound','start':1,'end':1.3,'text':'[cat meows]','checked':True}
  b=improve([a],[])[0]
  self.assertEqual(b['start'],1);self.assertEqual(b['text'],a['text']);self.assertLessEqual(b['end'],1.8);self.assertFalse(b['checked']);self.assertEqual(improve([b],[]),[b])
 def test_missing_cuts_no_extension(self):
  a={'kind':'sound','start':1,'end':1.3,'text':'[cat meows]'};self.assertEqual(improve([a]),[a])
 def test_cut_and_original_anchor_caps(self):
  a={'kind':'sound','start':1,'end':1.5,'presentationOriginalEnd':1.3,'text':'[cat meows]'}
  b=improve([a],[1.7])[0];self.assertLessEqual(b['end'],1.7-2/24)
if __name__=='__main__':unittest.main()
