import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from timed_text import check,blocking_issues,speed_accepted
class SpeedReviewTests(unittest.TestCase):
 def cue(self,n):return dict(id='D1',start=0,end=1,text='x'*n,sourceText='x'*n,sourceGroup='D1')
 def accept(self,c):return {**c,'speedReview':dict(accepted=True,reviewer='user',policy='amazon_itt_children_17_120',text=c['text'],start=c['start'],end=c['end'],fps=24,at='test')}
 def test_thresholds(self):
  self.assertEqual(check([self.cue(17)]),[])
  for n,band in [(18,'over_17')]:self.assertEqual(check([self.cue(n)])[0]['speed_band'],band)
 def test_word_rate_is_independent_of_character_rate(self):
  c=dict(self.cue(5),text='a b c',sourceText='a b c')
  issue=check([c])[0];self.assertIn('wpm_over_120',issue['flags']);self.assertNotIn('cps_over_17',issue['flags']);self.assertEqual(issue['wpm'],180)
  c.update(text='a b',sourceText='a b');self.assertEqual(check([c]),[])
 def test_old_policy_acceptance_is_invalid(self):
  c=self.accept(self.cue(18));c['speedReview'].pop('policy');self.assertFalse(speed_accepted(c))
 def test_acceptance_keeps_warning_but_resolves_rate_block(self):
  for n in [18,20]:
   c=self.accept(self.cue(n));issues=check([c]);self.assertTrue(issues[0]['speed_accepted']);self.assertTrue(issues[0]['flags']);self.assertFalse(blocking_issues(issues))
 def test_content_time_and_rate_changes_invalidate(self):
  c=self.accept(self.cue(18))
  for change in [{'text':'other'},{'start':.01},{'end':1.1}]:self.assertFalse(speed_accepted({**c,**change}))
  self.assertFalse(speed_accepted(c,'25'))
 def test_non_rate_findings_remain_blocking(self):
  c=self.accept({**self.cue(18),'unresolved':'listen again'});self.assertTrue(blocking_issues(check([c])))
  c=self.accept({**self.cue(18),'sourceText':'Original words'});self.assertTrue(any('lexical_change' in x['flags'] for x in blocking_issues(check([c]))))
 def test_general_checkmark_is_not_speed_acceptance(self):
  self.assertTrue(blocking_issues(check([{**self.cue(18),'checked':True}])))
if __name__=='__main__':unittest.main()
