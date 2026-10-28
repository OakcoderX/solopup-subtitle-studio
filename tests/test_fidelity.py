import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from fidelity import audit
from timed_text import check

class FidelityTests(unittest.TestCase):
 def cue(self,text,source=None,**extra):
  return dict(id='D1',sourceGroup='G1',start=1,end=6,text=text,sourceText=source or text,**extra)
 def test_reported_eight_paraphrases_are_not_accepted(self):
  examples=[('Please bring all three blue folders to the front desk.', 'Bring blue folders to the desk.'), ('Iris and Noah have already checked every window.', 'Iris and Noah checked the windows.'), ('The small green box is still under the table.', 'The box is under the table.'), ('First open the door, then switch on the lamp.', 'Open the door and switch on the lamp.'), ('Wait here until I call you again.', 'Wait until I call.'), ('We need five empty jars for the morning workshop.', 'We need empty jars for the workshop.'), ('She moved the red notebook beside the silver clock.', 'She moved the notebook by the clock.'), ('Before you leave, please return both spare keys.', 'Return the keys before leaving.')]
  for source,caption in examples:
   with self.subTest(source=source):
    self.assertIn('lexical_change',audit([self.cue(caption,source)])[0]['flags'])
    self.assertEqual(audit([self.cue(source)]),[])
 def test_split_and_formatting_are_allowed(self):
  a=self.cue('[narrator] First, crack an egg.','First, crack an egg. Then mix together.')
  b={**a,'id':'D1b','start':6.1,'end':8,'text':'Then mix\ntogether.'}
  self.assertEqual(audit([a,b]),[])
  self.assertEqual(audit([self.cue('♪ Here we go! ♪','Here we go!')]),[])
 def test_swapped_words_are_flagged(self):
  self.assertTrue(audit([self.cue('Noah called Iris.','Iris called Noah.')]))
 def test_low_cps_does_not_erase_word_loss(self):
  c=self.cue('Mix.', 'First, mix everything together.')
  self.assertIn('lexical_change',check([c])[0]['flags'])
 def test_whole_cue_deletion_is_flagged(self):
  self.assertEqual(audit([],{'G1':'First, mix.'})[0]['flags'],['source_group_missing'])
 def test_baseline_change_does_not_hide_edit(self):
  self.assertIn('source_baseline_changed',audit([self.cue('Mix.')],{'G1':'First, mix.'})[0]['flags'])
 def test_missing_evidence_blocks_dialogue_not_sound(self):
  self.assertTrue(audit([dict(id='D1',start=1,end=2,text='Hello!')]))
  self.assertFalse(audit([dict(id='S1',start=1,end=2,text='[wind gusts]')]))

if __name__=='__main__':unittest.main()
