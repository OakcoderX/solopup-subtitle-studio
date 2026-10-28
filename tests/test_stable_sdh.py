import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from presentation import stabilize
class Stable(unittest.TestCase):
 def test_tail_and_fidelity(self):
  rows=[dict(id='d',start=1,end=3,text='Hello',checked=True),dict(id='s',kind='sound',start=2,end=2.8,text='[wind]',checked=True,speedReview={'accepted':True})]
  out=stabilize(rows,[])
  self.assertEqual([c['text'] for c in out],[c['text'] for c in rows]);self.assertEqual([c['start'] for c in out],[1,2]);self.assertEqual(out[1]['end'],3);self.assertFalse(out[1]['checked']);self.assertFalse(out[1]['speedReview']['accepted']);self.assertEqual(stabilize(out,[]),out);self.assertEqual(rows[1]['end'],2.8)
 def test_large_gap_and_no_chain(self):
  a=dict(id='d',start=1,end=3,text='Hello');b=dict(id='s',kind='sound',start=2,end=2.2,text='[wind]')
  self.assertEqual(stabilize([a,b]),[a,b]);b.update(end=2.8,presentationOriginalEnd=2.2);self.assertEqual(stabilize([a,b]),[a,b])
 def test_line_limit(self):
  a=dict(start=1,end=3,text='Hello\nthere');b=dict(kind='sound',start=2,end=2.8,text='[wind]');self.assertEqual(stabilize([a,b]),[a,b])
if __name__=='__main__':unittest.main()
