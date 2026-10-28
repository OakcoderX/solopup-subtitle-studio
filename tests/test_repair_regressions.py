import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from timing_review import align,equivalence
from sound_readability import music_onsets
from layout_policy import prepare
from number_policy import normalize
from fidelity import audit
class RepairTests(unittest.TestCase):
 def test_equal_numeric_timing_not_word_substitution(self):
  row={'id':'a','text':'fifty grams','sourceText':'fifty grams','start':1,'end':3}
  witness={'segments':[{'words':[{'word':'50','start':1,'end':1.5,'probability':.9},{'word':'grams','start':1.5,'end':2,'probability':.9}]}]}
  fixed,events=align([row],witness,24)
  self.assertEqual(fixed[0]['text'],'fifty grams');self.assertEqual(len(events),1)
  row['text']='fifteen grams';self.assertFalse(align([row],witness,24)[1])
 def test_music_exposure_preserves_acoustic_duration(self):
  rows=[{'id':'m','kind':'sound','start':0,'end':30,'text':'[upbeat music]'}, {'id':'d','kind':'speech','start':5,'end':7,'text':'Hello there'}]
  fixed=music_onsets(rows)
  self.assertEqual(fixed[0]['end'],3);self.assertEqual(fixed[0]['audioEnd'],30)
  self.assertEqual(fixed[1],rows[1]);self.assertEqual(music_onsets(fixed),fixed)
 def test_lyrics_punctuation_preserves_words(self):
  row={'id':'a','kind':'song','text':'♪ We are cats. ♪','sourceText':'We are cats.','start':0,'end':3}
  fixed=prepare({'standard':[row],'sdh':[]})['standard'];self.assertEqual(fixed[0]['text'],'♪ We are cats ♪');self.assertFalse(audit(fixed))
 def test_conjunction_quantity(self):
  row={'id':'a','text':'Add salt and thirty milliliters of vinegar.','sourceText':'Add salt and thirty milliliters of vinegar.','start':0,'end':5}
  fixed=normalize([row]);self.assertIn('and 30',' '.join(fixed[0]['text'].split()));self.assertFalse(audit(fixed))
 def test_sound_sync_never_moves_dialogue(self):
  from display_timing import optimize,score
  rows=[{'id':'s','kind':'sound','start':1,'end':3,'text':'[meowing]'}, {'id':'d','kind':'speech','start':1.25,'end':3.25,'text':'Hello there.'}]
  fixed=optimize(rows,[],24)
  self.assertEqual(fixed[1],rows[1]);self.assertLess(score(fixed,24),score(rows,24));self.assertEqual(optimize(fixed,[],24),fixed)
 def test_sound_sync_respects_manual_lock(self):
  from display_timing import optimize
  rows=[{'id':'s','kind':'sound','start':1,'end':9,'text':'[whirring]','displayTimingLock':True}]
  self.assertEqual(optimize(rows,[],24),rows)
 def test_repair_incomplete_coverage_rejected(self):
  from repair_apply import reviewed_candidate
  with self.assertRaises(ValueError):reviewed_candidate({'standard':[{'id':'a'}]},[])
 def test_forced_clip_zero_needs_independent_boundary(self):
  from timing_review import apply_forced
  c={'id':'a','text':'Hello there','start':2,'end':4}
  forced={'a':{'text':'Hello there','words':[{'word':'Hello','start':1,'end':3,'probability':.99},{'word':'there','start':3,'end':4,'probability':.99}]}}
  fixed,events=apply_forced([c],forced,{},24)
  self.assertEqual(fixed,[c]);self.assertEqual(events,[])
 def test_clause_split_preserves_source_group(self):
  from layout_policy import split_anchored
  text='Please arrange these bright paper lanterns beside the windows, and bring every empty folder to the front desk.'
  tokens=text.split();anchors=[{'word':w,'start':i*.4,'end':(i+1)*.4,'probability':.9}for i,w in enumerate(tokens)]
  cue={'id':'x','sourceGroup':'x','sourceText':text,'text':text,'start':0,'end':len(tokens)*.4,'wordAnchors':anchors}
  fixed,changes=split_anchored([cue],24)
  self.assertTrue(changes);self.assertFalse(audit(fixed,{'x':text}));self.assertTrue(all(len(line)<=42 for c in fixed for line in c['text'].splitlines()))
if __name__=='__main__':unittest.main()
