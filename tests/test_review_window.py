import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from review_window import complete_window
class WindowTests(unittest.TestCase):
 def test_keep_complete_sentence_crossing_end(self):
  c=dict(id='a',start=118.458,end=125.4);a,b,rows=complete_window([c],60,120,660)
  self.assertEqual(rows,[c]);self.assertGreaterEqual(b,c['end']+2)
 def test_previous_owned_tail_is_present_as_context(self):
  c=dict(id='a',start=114,end=121);a,b,rows=complete_window([c],120,180,660)
  self.assertEqual(rows,[c]);self.assertLessEqual(a,c['start'])
 def test_next_owned_cue_does_not_expand_window_recursively(self):
  a,b,rows=complete_window([dict(id='future',start=120,end=200)],60,120,660)
  self.assertEqual(rows,[]);self.assertEqual((a,b),(56,124))
 def test_movie_bounds(self):
  a,b,rows=complete_window([dict(start=0,end=7)],0,60,60)
  self.assertEqual((a,b),(0,60))
if __name__=='__main__':unittest.main()
