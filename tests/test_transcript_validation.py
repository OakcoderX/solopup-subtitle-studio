import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from qwen_transcribe import validate_response
class TranscriptValidationTest(unittest.TestCase):
 def test_valid(self):validate_response({'speech_segments':[{'start':0,'end':2,'text':'Hello'}],'sound_events':[]},2)
 def test_missing_arrays(self):
  with self.assertRaises(ValueError):validate_response({},30)
 def test_invalid(self):
  for c in ({'end':1,'text':'Hello'},{'start':1,'end':1,'text':'Hello'},{'start':29,'end':30.5,'text':'Hello'},{'start':0,'end':float('nan'),'text':'Hello'}):
   with self.assertRaises(ValueError):validate_response({'speech_segments':[c],'sound_events':[]},30)
