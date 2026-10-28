import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from song_library import repair_short_exposures
class SongExposureTests(unittest.TestCase):
 def cue(self):
  return dict(id='theme',start=154/24,end=173/24,text='We are cats',kind='song',songMaster='theme',audioEnd=173/24,timingEvidence='PCM matched master',checked=False)
 def test_real_theme_short_event_gets_one_frame_without_moving_audio(self):
  c=self.cue();out,edits=repair_short_exposures([c],[179/24],24,660)
  self.assertEqual(out[0]['end'],174/24);self.assertEqual(out[0]['audioEnd'],c['audioEnd']);self.assertEqual(out[0]['text'],c['text']);self.assertEqual(len(edits),1)
  again,_=repair_short_exposures(out,[179/24],24,660);self.assertEqual(again,out)
 def test_no_guessing_missing_cuts_or_evidence_and_preserve_manual(self):
  for changes,cuts in [({},None),({'timingEvidence':''},[]),({'checked':True},[])]:
   c=self.cue();c.update(changes);out,edits=repair_short_exposures([c],cuts,24,660)
   self.assertEqual(out,[c]);self.assertEqual(edits,[])
 def test_no_new_flash_against_other_sound(self):
  c=self.cue();sound=dict(id='s',start=c['end'],end=9,text='[bell]',kind='sound')
  out,edits=repair_short_exposures([c,sound],[],24,660)
  self.assertEqual(out,[c,sound]);self.assertEqual(edits,[])
 def test_project_short_sound_policy_uses_exported_frames(self):
  from sdh_track import compose
  state={'standard':[],'sdh':[dict(id='s',start=.2,end=1,text='[chirp]',kind='sound')],'frameRate':24,'reviewPolicy':{'removeSoundBelowSeconds':.8}}
  result=compose(state,[],{},None)
  self.assertEqual(result['sdh'],[])
  self.assertEqual(result['soundDisplayOmissions'][0]['id'],'s')
 def test_rate_advisory_does_not_stretch_normal_song(self):
  c=self.cue();c.update(end=180/24,text='We are cats and we love to cook')
  out,edits=repair_short_exposures([c],[],24,660);self.assertEqual(out,[c]);self.assertEqual(edits,[])
if __name__=='__main__':unittest.main()
