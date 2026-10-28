import sys
from pathlib import Path
import unittest
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from review_pass import archive_other_review_windows,episode_picture_times,review_starts

class EpisodeReviewGranularityTests(unittest.TestCase):
 def test_episode_mode_is_one_request_for_full_scope(self):
  self.assertEqual(review_starts(0,660,'episode'),[0])
  self.assertEqual(review_starts(15,660,'episode'),[15])
  self.assertEqual(review_starts(0,130,'60s'),[0,60,120])

 def test_candidate_centers_are_kept_and_frames_are_absolute(self):
  sounds=[{'start':'12','end':'13'},{'start':'301','end':'303'},{'start':'658','end':'659'}]
  frames=episode_picture_times(0,660,sounds)
  self.assertEqual(frames,sorted(set(frames)))
  self.assertLessEqual(len(frames),200)
  for t in (12.5,302,658.5):self.assertIn(t,frames)
  self.assertTrue(all(0<=t<660 for t in frames))

 def test_frame_limit_preserves_candidate_evidence_before_uniform_fill(self):
  sounds=[{'start':str(i*2),'end':str(i*2+1)} for i in range(40)]
  frames=episode_picture_times(0,100,sounds,limit=24)
  self.assertEqual(len(frames),24)
  self.assertTrue(all(0<=t<100 for t in frames))
  self.assertEqual(frames,sorted(set(frames)))

 def test_episode_mode_archives_other_chunk_results_without_mixing_them(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'review_0000.json').write_text('episode candidate');(root/'review_0060.json').write_text('old chunk')
   archive_other_review_windows(root,0)
   self.assertTrue((root/'review_0000.json').exists())
   self.assertFalse((root/'review_0060.json').exists())
   self.assertEqual((next((root/'incomplete').iterdir())).read_text(),'old chunk')

if __name__=='__main__':unittest.main()
