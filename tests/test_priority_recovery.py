import unittest,sys,tempfile,json
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'workbench')]
from priority_recovery import resolve_superseded_findings,unique_word_alignment
from tail_room import extend_tails
from boundary_policy import repair_gaps
class PriorityRecoveryTest(unittest.TestCase):
 def test_only_explicit_matching_adjudication_closes_old_finding(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'actual.json';p.write_text('{}')
   c={'id':'a','text':'Hello, friend.','start':1,'end':3,'kind':'speech','wholeEpisodeAudioReview':{'input_text':'Hello, friend.','evidence':str(p),'verdict':{'verdict':'agree','uncertain':False,'resolves_prior_disagreement':True,'prior_reason_addressed':'Final consonants and greeting are clearly audible in the complete mix.','audio_evidence':'Hello, friend heard'}}}
   s={'standard':[c],'sdh':[],'latestReviewFindings':[{'id':'a','reason':'Old model doubt'},{'action':'missing_speech_review','start':5,'text':'Possible missing sentence'}]}
   out,events=resolve_superseded_findings(s,{})
   self.assertEqual(len(events),1);self.assertEqual(len(out['latestReviewFindings']),1);self.assertEqual(len(s['latestReviewFindings']),2)
   c['wholeEpisodeAudioReview']['verdict']['uncertain']=True
   self.assertEqual(len(resolve_superseded_findings(s,{})[1]),0)
 def test_exact_timing_rejects_duplicate_and_low_confidence(self):
  c={'text':'Good morning','start':1,'end':2};span=[{'word':'Good','start':1,'end':1.3,'probability':.9},{'word':'morning','start':1.4,'end':2,'probability':.9}];w={'segments':[{'words':span}]}
  self.assertTrue(unique_word_alignment(c,w));w['segments'].append({'words':span});self.assertIsNone(unique_word_alignment(c,w));w['segments'].pop();span[0]['probability']=.1;self.assertIsNone(unique_word_alignment(c,w));span[0]['probability']=float('nan');self.assertIsNone(unique_word_alignment(c,w))
 def test_sound_does_not_block_dialogue_tail(self):
  rows=[{'id':'a','start':0,'end':1,'text':'Hello there, friend.','audioEnd':1,'timingEvidence':'measured'}, {'id':'s','kind':'sound','start':.8,'end':1.2,'text':'[meow]'}, {'id':'b','start':2,'end':3,'text':'Hi.'}]
  out,_=extend_tails(rows,[],24,4);self.assertGreater(out[0]['end'],1);self.assertEqual(out[1],rows[1]);self.assertLessEqual(out[0]['end'],1.5)
 def test_sound_between_rows_does_not_hide_dialogue_gap(self):
  a={'id':'a','start':0,'end':1,'text':'A.','audioEnd':1,'timingReview':'machine_word_matched','timingEvidence':'measured'};b={'id':'b','start':1,'end':2,'text':'B.','audioStart':1,'timingReview':'machine_word_matched','timingEvidence':'measured'};sound={'id':'s','start':.9,'end':1.4,'text':'[meow]','kind':'sound'}
  out,events=repair_gaps([a,sound,b],24,[]);self.assertEqual(len(events),1);self.assertEqual(next(c for c in out if c['id']=='s'),sound)

 def test_nonlexical_requires_two_actual_passes_and_preserves_names(self):
  from priority_recovery import remove_corroborated_false_interjections
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'old.json';q=Path(root)/'new.json'
   p.write_text(json.dumps({'parsed':{'cue_reviews':[{'id':'a','verdict':'remove','reason':'false lexical cat squeak'}]}}))
   q.write_text(json.dumps({'parsed':{'cue_reviews':[{'id':'a','verdict':'nonlexical','uncertain':False,'confidence':'high','presentation':'onscreen','resolves_prior_disagreement':True,'prior_reason_addressed':'No English phonemes; it is the same animal squeak in the original audio.','audio_evidence':'A short high-pitched cat squeak without the English consonant-vowel structure.'}]}}))
   c={'id':'a','sourceGroup':'a','sourceText':'Yeah!','text':'Yeah!','start':1,'end':1.3,'kind':'speech'}
   state={'standard':[c],'sdh':[dict(c)],'sourceManifest':{'standard':{'a':'Yeah!'},'sdh':{'a':'Yeah!'}}}
   out,events=remove_corroborated_false_interjections(state,p,q);self.assertEqual(len(events),1);self.assertEqual(out['standard'],[]);self.assertEqual(state['standard'],[c])
   c['text']='Riley.';c['sourceText']='Riley.';state['sourceManifest']={'standard':{'a':'Riley.'},'sdh':{'a':'Riley.'}};state['standard']=[c];state['sdh']=[dict(c)]
   self.assertEqual(remove_corroborated_false_interjections(state,p,q)[1],[])

 def test_aggregate_gains_cannot_move_a_defect_to_another_cue(self):
  from priority_recovery import technical_nonregression
  a={'id':'a','start':0,'end':.4,'text':'Hello.','kind':'speech'}
  b={'id':'b','start':2,'end':3.5,'text':'Bye.','kind':'speech'}
  old={'standard':[a,b],'sdh':[]};new={'standard':[dict(a,end=1.5),dict(b,end=2.4)],'sdh':[]}
  self.assertFalse(technical_nonregression(old,new))

 def test_manual_lock_survives_technical_improvement(self):
  from priority_recovery import technical_nonregression
  c={'id':'a','start':0,'end':.4,'text':'Hello.','kind':'speech','checked':True}
  self.assertFalse(technical_nonregression({'standard':[c],'sdh':[]},{'standard':[dict(c,end=1.5)],'sdh':[]}))

 def test_tail_rebinding_needs_exact_words_and_measured_edges(self):
  from priority_recovery import rebind_measured_machine_evidence
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'actual_review.json';p.write_text('{}')
   c={'id':'a','text':'Hi.','start':1,'end':2.4,'audioStart':1,'audioEnd':2,'timingReview':'machine_word_matched','timingEvidence':'actual measured words','wordAnchors':[{'word':'Hi','start':1,'end':2,'probability':.9}], 'reviewInvalidated':True,'wholeEpisodeAudioReview':{'evidence':str(p),'input_text':'Hi.','verdict':{'verdict':'agree','uncertain':False}}}
   state={'standard':[c],'sdh':[]};out,events=rebind_measured_machine_evidence(state);self.assertEqual(len(events),1);self.assertNotIn('reviewInvalidated',out['standard'][0]);self.assertFalse(out['standard'][0]['measuredMachineReviewBinding']['humanApproved'])
   c['end']=2.6;self.assertEqual(rebind_measured_machine_evidence(state)[1],[])
   c['end']=2.4;c['wholeEpisodeAudioReview']['input_text']='Bye.';self.assertEqual(rebind_measured_machine_evidence(state)[1],[])
