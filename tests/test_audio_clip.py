import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audio_clip import validate_duration
class AudioCompletenessTests(unittest.TestCase):
 def test_native_success_with_truncated_audio_is_not_complete_evidence(self):
  for duration in (6.698,7.69,0,float('nan')):
   with self.assertRaises(ValueError):validate_duration(duration,30)
 def test_small_encoder_padding_accepted_but_missing_duration_not(self):
  validate_duration(30.048,30);validate_duration(29.98,30)
  with self.assertRaises(ValueError):validate_duration(29.5,30)
if __name__=='__main__':unittest.main()
