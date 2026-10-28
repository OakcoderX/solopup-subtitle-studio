import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from timed_text import check
class SongPolicyTests(unittest.TestCase):
 def test_project_exception_is_scoped(self):
  c=dict(id='a',kind='song',text='♪ Sing this very fast song with many words ♪',start=0,end=1)
  strict=check([c])[0]; advisory=check([c],song_speed_advisory=True)[0]
  self.assertIn('cps_over_17',strict['blocking_flags'])
  self.assertIn('cps_over_17',advisory['flags'])
  self.assertNotIn('cps_over_17',advisory['blocking_flags'])
  c['unresolved']='word uncertainty'
  self.assertIn('unresolved_content',check([c],song_speed_advisory=True)[0]['blocking_flags'])
  c['kind']='speech'
  self.assertIn('cps_over_17',check([c],song_speed_advisory=True)[0]['blocking_flags'])
