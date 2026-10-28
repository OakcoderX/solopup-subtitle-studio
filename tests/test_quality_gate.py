import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from layout_policy import prepare
from fidelity import audit
from number_policy import normalize,issues
from quality_gate import report
from timed_text import unresolved_flags
class GateTests(unittest.TestCase):
 def c(self,id,text,start=0):return dict(id=id,text=text,sourceText=text,sourceGroup=id,start=start,end=start+3,kind='speech',checked=True)
 def test_list_numbers_and_idempotence(self):
  rows=[self.c('a',"We'll need:"),self.c('b','one egg,',3),self.c('c','one hundred seventy-five grams of flour,',6)]
  fixed=normalize(rows)
  self.assertEqual(fixed[2]['text'],'175 grams of flour,')
  self.assertEqual(fixed[1]['text'],'one egg,')
  self.assertEqual(normalize(fixed),fixed)
  self.assertFalse(fixed[2]['checked'])
  self.assertEqual(audit(fixed),[])
  self.assertTrue(issues(rows));self.assertFalse(issues(fixed))
 def test_sentence_begin_and_values(self):
  rows=[self.c('a','One hundred grams is enough.')]
  self.assertEqual(normalize(rows),rows)
  fixed=normalize([self.c('a','Add sixty grams of sugar.')]);self.assertEqual(fixed[0]['text'],'Add 60 grams of sugar.')
  fixed[0]['text']='Add 600 grams of sugar.'
  self.assertTrue(audit(fixed))
 def test_gate_never_invents_approval(self):
  rows=[self.c('a','Hello there.')]
  s=prepare({'standard':rows,'sdh':copy.deepcopy(rows),'release':{'content_verified':False}})
  self.assertEqual(report(s)['status'],'REVIEW_REQUIRED')
  s['release']['content_verified']=True
  self.assertEqual(report(s)['status'],'READY_FOR_DELIVERY')
  s['sdh'][0]['unresolved']='Listen again'
  self.assertEqual(report(s)['status'],'REVIEW_REQUIRED')
 def test_save_normalizes_before_checks(self):
  s=prepare({'standard':[self.c('a','Add sixty grams of sugar.')],'sdh':[]})
  self.assertEqual(s['standard'][0]['text'],'Add 60 grams of sugar.')
 def test_profile_source_hierarchy_is_visible(self):
  s=prepare({'standard':[self.c('a','Hello there.')],'sdh':[self.c('b','Hello there.')],
             'subtitleSpec':'amazon_itt_children_17_120'})
  p=report(s)['policy_basis']
  self.assertEqual(p['project_policy']['children_cps'],17)
  self.assertEqual(p['project_policy']['wpm'],120)
  self.assertIn('13 CPS',p['note'])
  self.assertEqual(p['authority_order'][0],'title-specific Slate / Kids+ delivery instructions when supplied')
 def test_legacy_unresolved_notes_keep_their_real_blocker_type(self):
  timing=unresolved_flags({'kind':'speech','unresolved':'时间边界尚无逐词证据，需复核。'})
  sound=unresolved_flags({'kind':'sound','unresolved':'SDH 系统建议，待视听确认。'})
  doubt=unresolved_flags({'kind':'speech','unresolved':'本轮听辨疑点：词语可能是 dumpling 或 dumplings。'})
  unknown=unresolved_flags({'kind':'speech','unresolved':'Unmapped open note.'})
  self.assertEqual(timing,['timing_evidence_unresolved'])
  self.assertEqual(sound,['sound_review_required'])
  self.assertEqual(doubt,['unresolved_content'])
  self.assertEqual(unknown,['unresolved_content'])
 def test_amazon_ep14_visual_only_sdh_description_is_blocked(self):
  from sdh_validation import style_issues
  cue=self.c('s','[A guest pretends to enjoy the soup]');cue['kind']='sound'
  self.assertIn('sound_visual_action',style_issues(cue))
  cue['text']='[cat meowing]'
  self.assertNotIn('sound_visual_action',style_issues(cue))
 def test_song_case_after_comma_is_blocked_without_rewriting_lyrics(self):
  from sdh_validation import style_issues
  cue=self.c('song','♪ Splish, Splash, Splosh! ♪');cue.update(kind='song',italic=True,presentation='song')
  self.assertIn('song_case_after_comma',style_issues(cue))
  self.assertEqual(cue['text'],'♪ Splish, Splash, Splosh! ♪')
 def test_final_script_comparison_is_exposed_as_reference_only(self):
  s=prepare({'standard':[self.c('a','Hello there.')],'sdh':[self.c('b','Hello there.')],
             'scriptComparison':[{'classification':'difference_to_review'}]})
  comparison=report(s)['script_comparison']
  self.assertEqual(comparison['cue_count'],1)
  self.assertEqual(comparison['by_classification'],{'difference_to_review':1})
  self.assertIn('reference only',comparison['authority'])
 def test_project_preferred_spelling_is_a_blocking_check(self):
  from timed_text import check
  row=self.c('a','A rainbow colored flower.')
  issues=check([row],preferred_spellings={'rainbow colored':'rainbow-colored'})
  self.assertTrue(any('preferred_spelling' in x['flags'] and x['correction']=='rainbow-colored' for x in issues))
  self.assertFalse(any('preferred_spelling' in x['flags'] for x in check([self.c('b','A rainbow-colored flower.')],preferred_spellings={'rainbow colored':'rainbow-colored'})))
  self.assertFalse(any('preferred_spelling' in x['flags'] for x in check([self.c('c',"The Big Workshop.")],preferred_spellings={"the big workshop":"The Big Workshop"})))
  self.assertTrue(any(x.get('correction')=='The Big Workshop' for x in check([self.c('d',"The big workshop.")],preferred_spellings={"the big workshop":"The Big Workshop"})))
 def test_amazon_qc_punctuation_findings_are_caught_without_auto_rewrite(self):
  from sdh_validation import style_issues
  row=self.c('p','Sounds tasty');row['kind']='speech'
  self.assertIn('terminal_punctuation_review',style_issues(row))
  row['text']='Now take some yeast -';row['sourceText']=row['text']
  self.assertIn('continuation_punctuation_review',style_issues(row))
  self.assertEqual(row['text'],'Now take some yeast -')
  row.update(kind='speech',text='Now we wait for the dough to rise',sourceText='Now we wait for the dough to rise and become nice and fluffy.')
  self.assertNotIn('terminal_punctuation_review',style_issues(row))
if __name__=='__main__':unittest.main()
