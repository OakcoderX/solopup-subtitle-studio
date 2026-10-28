import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from timing_review import display_anchors,equivalence,align
from boundary_policy import repair_gaps
from fidelity import audit,words
from layout_policy import split_internal_evidence
class EvidenceBoundaryTests(unittest.TestCase):
 def test_fraction_maps_multiple_tokens_without_inventing_times(self):
  spans=[{'word':w,'start':i,'end':i+.8,'probability':.9}for i,w in enumerate(['one','third','teaspoon'])]
  mapped=display_anchors('one-third teaspoon',equivalence(spans))
  self.assertEqual(mapped[0]['start'],0);self.assertEqual(mapped[0]['end'],1.8)
  self.assertEqual(mapped[0]['word'],'one-third')
  self.assertIsNone(display_anchors('two-thirds teaspoon',equivalence(spans)))
 def test_long_numeric_recipe_splits_and_retains_fidelity(self):
  text='Add 150 grams of flour, one-third teaspoon of salt, one tablespoon of oil, and then stir everything together.'
  spans=[];i=0
  for token in words(text):spans.append({'word':token,'start':i*.5,'end':i*.5+.3,'probability':.9});i+=1
  c={'id':'x','start':0,'end':spans[-1]['end'],'text':text,'sourceText':text,'sourceGroup':'x'}
  rows,events=align([c],{'segments':[{'words':spans}]},24)
  self.assertGreater(len(rows),1);self.assertFalse(audit(rows,{'x':text}));self.assertTrue(all(x['end']-x['start']<=7 for x in rows))
 def rows(self):
  return [dict(id='a',start=0,end=2,audioStart=0,audioEnd=2,text='Hello there',timingReview='machine_word_matched',timingEvidence='independent'),dict(id='b',start=2,end=4,audioStart=2,audioEnd=4,text='Good morning',timingReview='machine_word_matched',timingEvidence='independent')]
 def test_small_gap_fixed_once_preserving_words(self):
  rows=self.rows();out,events=repair_gaps(rows,24,[])
  self.assertEqual(len(events),1);self.assertAlmostEqual(out[1]['start']-out[0]['end'],2/24)
  self.assertEqual([c['text']for c in rows],[c['text']for c in out]);self.assertEqual(repair_gaps(out,24,[])[0],out)
 def test_no_gap_guess_without_evidence_or_across_cut(self):
  rows=self.rows();rows[0].pop('timingEvidence');self.assertFalse(repair_gaps(rows,24,[])[1])
  self.assertFalse(repair_gaps(self.rows(),24,[1.95])[1]);self.assertFalse(repair_gaps(self.rows(),24,None)[1])
 def test_real_overlap_not_suppressed(self):
  rows=self.rows();rows[0]['end']=rows[0]['audioEnd']=2.5;self.assertFalse(repair_gaps(rows,24,[])[1])
 def test_internal_split_does_not_copy_parent_end_or_approve_outer_timing(self):
  text='Please mix all these ingredients carefully, and then cook the mixture gently until ready.'
  tokens=text.split();ws=[{'word':w,'start':i*.5,'end':i*.5+.3,'probability':.95}for i,w in enumerate(tokens)]
  c=dict(id='x',text=text,sourceText=text,sourceGroup='x',start=0,end=len(tokens)*.5,audioStart=0,audioEnd=len(tokens)*.5,timingReview='machine_word_matched',timingEvidence='parent')
  forced={'x':{'text':text,'words':ws}};witness={'segments':[{'words':ws}]}
  out,events=split_internal_evidence([c],forced,witness,24)
  self.assertTrue(events);self.assertLess(out[0]['audioEnd'],c['audioEnd']);self.assertTrue(all(x['timingReview'].startswith('pending') for x in out));self.assertFalse(audit(out,{'x':text}))
  bad=copy.deepcopy(witness);bad['segments'][0]['words'][7]['end']=bad['segments'][0]['words'][7]['start'];self.assertFalse(split_internal_evidence([c],forced,bad,24)[1])
 def test_sustained_sound_exposure_does_not_delete_event(self):
  from sound_readability import sustained_onsets
  row={'id':'s','kind':'sound','start':5,'end':30,'text':'[straining]'}
  out=sustained_onsets([row]);self.assertEqual(out[0]['audioEnd'],30);self.assertEqual(out[0]['end'],8)
  self.assertEqual(out[0]['text'],row['text']);self.assertEqual(sustained_onsets(out),out)
  row['checked']=True;self.assertEqual(sustained_onsets([row]),[row])
 def test_missing_sounds_registered_once_without_approval(self):
  from missing_sounds import register
  m={'start':10,'end':12,'caption':'[meowing]','evidence':'review.json'}
  rows,decisions,ledger=register([],{},[m],20)
  self.assertEqual(len(rows),1);self.assertEqual(decisions['1']['status'],'');self.assertFalse(decisions['1']['humanApproved'])
  again=register(rows,decisions,[m],20);self.assertEqual(len(again[0]),1)
  covered=register([{'start':9,'end':13,'caption':'[meowing]'}],{},[m],20)
  self.assertEqual(covered[2][0]['status'],'already_covered')
 def test_audio_disagreement_survives_a_confident_later_keep(self):
  from review_conflicts import mark
  from repair_apply import reviewed_candidate
  import tempfile,json
  conflict={'id':'a','reason':'Could be a party blower','evidence':'sound.json'}
  row={'id':'a','start':1,'end':2,'text':'Riley!','sourceText':'Riley!','sourceGroup':'a'}
  row=mark([row],[conflict])[0]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'review.json';p.write_text(json.dumps({'parsed':{'verdicts':[{'id':'a','action':'KEEP','text':'Riley!','uncertain':False,'reason':'sounds lexical'}]}}))
   state,_=reviewed_candidate({'standard':[row],'release':{}},[p])
   self.assertIn('对白与声音复核不一致',state['standard'][0]['unresolved'])
 def test_machine_semantic_review_is_bound_and_not_final_approval(self):
  from sdh_track import compose
  from quality_gate import report
  row={'start':1,'end':3,'caption':'[meowing]'}
  d={'status':'KEEP','caption':'[meowing]','uncertain':False,'reviewer':'assistant','humanApproved':False,
     'semanticReview':{'status':'machine_reviewed','caption':'[meowing]','decision':'KEEP','start':1.0,'end':3.0,'narrativeValue':'Offscreen call draws attention to a stranded character','audioEvidence':'heard cat','pictureEvidence':'sampled cat frame','evidence':['first.json','second.json']}}
  result=compose({'standard':[],'sdh':[],'frameRate':24},[row],{'1':d},[])
  self.assertFalse(result['sdh'][0].get('unresolved'));self.assertFalse(result['sdh'][0]['checked']);self.assertEqual(report(result)['status'],'REVIEW_REQUIRED')
  d['caption']='[squeaking]';result=compose({'standard':[],'sdh':[]},[row],{'1':d},[])
  self.assertTrue(result['sdh'][0].get('unresolved'))
 def test_composition_never_extends_dialogue_or_crosses_cut(self):
  from presentation import stabilize
  rows=[{'id':'d','start':1,'end':3,'text':'Hello'},{'id':'s','kind':'sound','start':2,'end':3.3,'text':'[wind]'}]
  self.assertEqual(stabilize(rows,[])[0],rows[0])
  rows[1]['end']=2.8
  self.assertEqual(stabilize(rows,None),rows);self.assertEqual(stabilize(rows,[2.9]),rows)
  self.assertEqual(stabilize(rows,[])[1]['end'],3)
 def test_legacy_sdh_split_recovered_only_with_complete_source(self):
  from layout_policy import recover_standard_layout
  text='Please let us know what kind of food we should make.'
  rows=[]
  for i,t in enumerate(['Please let us know what','kind of food we should make.']):
   rows.append({'id':'r-S'+str(i),'sourceGroup':'r','sourceText':text,'text':t,'start':i*2,'end':i*2+1.9,'layoutSplit':{'parent':'r','reason':'One dialogue line plus one sound line; measured word boundary; no word edits'}})
  merged,changes=recover_standard_layout(rows);self.assertTrue(changes);self.assertEqual(len(merged),1);self.assertFalse(audit(merged,{'r':text}))
  rows[0]['checked']=True;self.assertFalse(recover_standard_layout(rows)[1]);rows[0]['checked']=False
  rows[1]['text']='food we should make.';self.assertFalse(recover_standard_layout(rows)[1])
if __name__=='__main__':unittest.main()
