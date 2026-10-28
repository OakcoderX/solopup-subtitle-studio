import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from issue_triage import build

class TriageTests(unittest.TestCase):
 def test_multiple_flags_and_rendered_event_do_not_disguise_wpm_as_only_problem(self):
  cues=[dict(id=x,start=i,end=i+1,text=x) for i,x in enumerate(['words','layout','other','wpm'])]
  s={'standard':cues,'sdh':[]}
  issues=[dict(id='words',flags=['unresolved_content','wpm_over_120']),dict(id='layout',flags=['wpm_over_120']),dict(id='layout+other',cue_ids=['layout','other'],flags=['export_event_short']),dict(id='other',flags=['sound_brackets']),dict(id='wpm',flags=['wpm_over_120'])]
  q={'tracks':{'standard':{'issues':issues},'sdh':{'issues':[]}}}
  r=build(s,q)['tracks']['standard'];self.assertEqual(r['affected_cues'],4);self.assertEqual(r['by_priority'],{'1':1,'2':2,'3':0,'4':1});self.assertEqual(r['joint_event_count'],1)
 def test_song_advisory_is_not_a_blocker_and_pending_content_outranks_speed(self):
  s={'standard':[dict(id='a',start=1,end=3,text='Song'),dict(id='b',start=4,end=5,text='Maybe')],'sdh':[]}
  q={'tracks':{'standard':{'issues':[dict(id='a',flags=['wpm_over_120'],blocking_flags=[]),dict(id='b',flags=['wpm_over_120'])]},'sdh':{'issues':[]}},'review_findings':[dict(id='b',reason='Heard wording unclear')]}
  r=build(s,q)['tracks']['standard'];self.assertEqual(r['affected_cues'],1);self.assertEqual(r['items'][0]['priority'],1);self.assertEqual(r['items'][0]['assessment'],'content_question_not_confirmed_error')
 def test_missing_source_group_is_reported_even_without_an_existing_cue(self):
  q={'tracks':{'standard':{'issues':[dict(id='missing',flags=['source_group_missing'])]},'sdh':{'issues':[]}}}
  r=build({'standard':[],'sdh':[]},q)['tracks']['standard'];self.assertEqual(r['unmapped_finding_count'],1);self.assertEqual(r['unmapped_findings'][0]['priority'],1)

if __name__=='__main__':unittest.main()
