import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from evidence_gate import evidence_flags,refresh,reconcile_edit
from timed_text import check
from quality_gate import report
from produce import assemble

class EvidenceGateTests(unittest.TestCase):
 def sound(self):
  return dict(id='s',kind='sound',text='[wind]',start=1,end=3,semanticReview=dict(status='machine_reviewed',caption='[wind]',start=1,end=3,audioEvidence='audible gust',evidence=['audio-a','audio-b'],narrativeValue='Warns of exposure on the frozen lake',clip=[0,4]))
 def test_valid_machine_evidence_never_implies_human_release(self):
  c=self.sound();self.assertEqual(evidence_flags(c),[])
  self.assertEqual(report({'sdh':[c]})['status'],'REVIEW_REQUIRED')
 def test_necessity_missing_cannot_pass_with_model_confidence(self):
  c=self.sound();c['semanticReview'].pop('narrativeValue');c['confidence']=1
  self.assertIn('sound_necessity_unverified',evidence_flags(c))
 def test_clip_conflict_visual_and_stale_checks(self):
  for key,value,flag in [('clip',[2,4],'evidence_outside_clip'),('conflict',True,'semantic_evidence_conflict'),('visualOnly',True,'sound_inferred_from_picture'),('caption','[rain]','semantic_evidence_stale')]:
   c=self.sound();c['semanticReview'][key]=value
   self.assertIn(flag,evidence_flags(c))
   self.assertTrue(any(flag in i['blocking_flags'] for i in check([c])))
 def test_display_tail_uses_retained_acoustic_evidence(self):
  c=self.sound();c.update(end=3.3,soundAudioEnd=3)
  self.assertNotIn('semantic_evidence_stale',evidence_flags(c))
 def test_only_changed_review_is_invalidated_and_can_be_reviewed_again(self):
  a=dict(id='a',text='Hello',start=1,end=3,checked=True)
  old=refresh({'standard':[a,dict(a,id='b',start=4,end=6)],'release':{'content_verified':True}})
  new=copy.deepcopy(old);new['standard'][0]['text']='Hi';new['standard'][0].pop('reviewBinding')
  new=refresh(reconcile_edit(old,new))
  self.assertFalse(new['standard'][0]['checked']);self.assertTrue(new['standard'][1]['checked'])
  self.assertFalse(new['release']['content_verified']);self.assertIn('review_evidence_stale',evidence_flags(new['standard'][0]))
  new['standard'][0]['checked']=True;new=refresh(new)
  self.assertEqual(evidence_flags(new['standard'][0]),[])
 def test_invalid_recognition_time_is_not_clamped_or_dropped(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'chunk.json'
   for start,end in [(-1,1),(0,11),(0,float('nan'))]:
    p.write_text(json.dumps({'offset_seconds':20,'end_seconds':30,'parsed':{'speech_segments':[{'start':start,'end':end,'text':'Hello'}]}}))
    with self.assertRaisesRegex(ValueError,'outside supplied audio'):assemble([p],24,100)
 def test_unresolved_full_review_finding_blocks_even_empty_technical_report(self):
  state={'standard':[],'sdh':[],'release':{'content_verified':True},'latestReviewFindings':[{'id':'a','reason':'uncertain source'}]}
  self.assertEqual(report(state)['status'],'REVIEW_REQUIRED')
 def test_master_issues_still_block_under_lyric_speed_advisory(self):
  state={'standard':[],'sdh':[],'reviewPolicy':{'songSpeedAdvisory':True},'release':{'content_verified':True},'songLibrary':{'matches':[{'master_id':'theme','issues':[{'reason':'word uncertain'}]}]}}
  self.assertEqual(report(state)['status'],'REVIEW_REQUIRED')
if __name__=='__main__':unittest.main()
