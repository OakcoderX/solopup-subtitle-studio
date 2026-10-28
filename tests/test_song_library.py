import unittest,sys,copy
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from song_library import locate,apply,audit
class SongLibraryTest(unittest.TestCase):
 def test_identical_recording_gain_and_offset(self):
  r=np.random.default_rng(1);t=r.normal(size=6000);y=np.r_[r.normal(size=1000),t*.8,r.normal(size=1000)]
  m=locate(t,y,1000);self.assertTrue(m['verified_same_recording']);self.assertEqual(m['start'],1)
 def test_one_changed_block_rejects_remix(self):
  r=np.random.default_rng(2);t=r.normal(size=20000);y=t.copy();y[5000:6500]=r.normal(size=1500)
  self.assertFalse(locate(t,y,1000)['verified_same_recording'])
 def test_multiple_recordings_are_found(self):
  import tempfile,json,hashlib
  from song_library import identify
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);rng=np.random.default_rng(3);t=rng.normal(size=6000).astype('float32')
   np.savez_compressed(root/'a.npz',pcm=t)
   master={'id':'A','status':'audio_verified','fingerprint':'a.npz','fingerprint_sha256':hashlib.sha256((root/'a.npz').read_bytes()).hexdigest(),'lines':[]}
   (root/'registry.json').write_text(json.dumps({'masters':[master]}))
   result=identify('unused',root,np.r_[np.zeros(1000),t,np.zeros(1000),t,np.zeros(1000)])
   self.assertEqual(len(result['matches']),2)
 def test_missing_and_repeated_lyrics_gate(self):
  m={'matches':[{'master_id':'A','master_digest':'d','start':10,'end':14,'lyric_status':'audio_verified','correlation':1,'weakest_block':1,'lines':[{'start':0,'end':1,'text':'Go go','kind':'song'},{'start':2,'end':3,'text':'Go go','kind':'song'}]}]}
  out,manifest,events=apply([],{},m);self.assertEqual(events[0]['status'],'reused');self.assertFalse(audit(out,m))
  self.assertTrue(audit(out[:-1],m));self.assertTrue(audit([],m))
  out[0]['text']='Go';self.assertTrue(audit(out,m))
 def test_checked_and_boundary_words_preserved(self):
  m={'matches':[{'master_id':'A','master_digest':'d','start':10,'end':14,'lyric_status':'audio_verified','correlation':1,'weakest_block':1,'lines':[{'start':0,'end':1,'text':'Go'}]}]}
  for row in [{'id':'x','start':9,'end':11,'text':'outside'},{'id':'x','start':10,'end':11,'text':'approved','checked':True}]:
   result,_,events=apply([row],{'x':row['text']},m);self.assertEqual(result,[row]);self.assertNotEqual(events[0]['status'],'reused')
 def test_stale_dialogue_time_cannot_be_erased_by_song_reuse(self):
  m={'matches':[{'master_id':'A','master_digest':'d','start':10,'end':14,'lyric_status':'audio_verified','correlation':1,'weakest_block':1,'lines':[{'start':0,'end':4,'text':'What dish shall we make today?','kind':'song'}]}]}
  cue={'id':'answer','start':12,'end':14,'text':'Mashed potatoes with gravy.','kind':'speech'}
  rows,manifest,events=apply([cue],{'answer':cue['text']},m)
  self.assertEqual(rows,[cue]);self.assertEqual(manifest,{'answer':cue['text']})
  self.assertEqual(events[0]['status'],'unmatched_dialogue_preserved')
 def test_pending_master_never_ready(self):
  from quality_gate import report
  state={'standard':[],'sdh':[],'release':{'content_verified':True},'songLibrary':{'matches':[{'master_id':'A','start':0,'end':3,'lines':[],'issues':[{'id':'ambiguous','text':'make or bake'}]}]}}
  self.assertEqual(report(state)['status'],'REVIEW_REQUIRED')
if __name__=='__main__':unittest.main()
