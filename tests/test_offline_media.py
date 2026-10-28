import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from server import stored_media_metadata
class OfflineMediaTests(unittest.TestCase):
 def test_saved_scope_and_rate_available_without_media(self):
  s={'scope':[0,661.631],'frameRate':'24/1','standard':[{'end':650}],'sdh':[]}
  self.assertEqual(stored_media_metadata(s),(661.631,'24/1'));self.assertEqual(s['standard'][0]['end'],650)
 def test_empty_saved_state_is_editable_without_inventing_duration(self):
  self.assertEqual(stored_media_metadata({}),(0,'24'))
if __name__=='__main__':unittest.main()
