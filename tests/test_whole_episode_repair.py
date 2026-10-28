import copy, json, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from whole_episode_repair import drop_exact_duplicate_groups, merge_verified_fragments, corroborated_content_repairs, unique_verdicts, explicit_sound_adjudications,apply_review,explicitly_corroborated_words

class WholeEpisodeRepairTests(unittest.TestCase):
 def cue(self,ident='a',group='a',start=1,end=3,text='Hello there.'):
  tokens=text.split();step=(end-start)/len(tokens)
  return dict(id=ident,sourceGroup=group,sourceText=text,text=text,start=start,end=end,audioStart=start,audioEnd=end,kind='speech',presentation='voiceover',timingReview='machine_word_matched',timingEvidence='Independent word witness',wordAnchors=[dict(word=w,start=start+i*step,end=start+(i+1)*step,probability=.95) for i,w in enumerate(tokens)])
 def state(self,rows):
  return dict(frameRate='24',standard=copy.deepcopy(rows),sdh=copy.deepcopy(rows),sourceManifest={t:{c['sourceGroup']:c['sourceText'] for c in rows} for t in ('standard','sdh')})
 def test_duplicate_acoustic_group_can_have_different_legal_display_tail(self):
  a=self.cue();b=self.cue('b','b');b['end']=3.5
  s,e=drop_exact_duplicate_groups(self.state([a,b]));self.assertEqual(len(e),1);self.assertEqual(len(s['standard']),1);self.assertNotIn('b',s['sourceManifest']['standard'])
 def test_genuine_sequential_repetitions_and_locked_songs_survive(self):
  a=self.cue();b=self.cue('b','b',4,6)
  s,e=drop_exact_duplicate_groups(self.state([a,b]));self.assertEqual(len(s['standard']),2)
  b=self.cue('b','b');b['songMaster']='locked';s,e=drop_exact_duplicate_groups(self.state([a,b]));self.assertEqual(len(s['standard']),2)
 def test_measured_fragments_merge_without_removing_a_word(self):
  a=self.cue('a1','a',1,2,'Hello');b=self.cue('a2','a',2.1,3,'there.')
  for c in (a,b):c['sourceText']='Hello there.'
  rows,e=merge_verified_fragments([a,b],[],24);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['text'],'Hello there.')
  rows,e=merge_verified_fragments([a,b],[2.05],24);self.assertEqual(len(rows),2)
 def test_contradictory_same_id_verdicts_do_not_silently_pick_latest(self):
  v=unique_verdicts([{'id':'a','verdict':'agree'},{'id':'a','verdict':'correct','corrected_text':'changed'}]);self.assertTrue(v['a']['uncertain'])
 def test_new_model_words_without_independent_match_are_not_applied(self):
  a=self.cue();s,e=corroborated_content_repairs(self.state([a]),{'cue_reviews':[{'id':'a','verdict':'correct','corrected_text':'Goodbye there.','reason':'clear voice','uncertain':False}]},Path('review.json'),{})
  self.assertEqual(s['standard'][0]['text'],'Hello there.');self.assertEqual(e,[])
 def test_animal_source_needs_two_real_audio_evidence_paths(self):
  a=self.cue(text='Ow!');a['audioAdjudication']={'reason':'Oven vocalization','evidence':'missing.json'}
  parsed={'cue_reviews':[{'id':'a','verdict':'nonlexical','reason':'false lexical oven grumble','uncertain':False}]}
  s,e=corroborated_content_repairs(self.state([a]),parsed,Path('whole.json'),{});self.assertEqual(len(s['standard']),1)
  with tempfile.TemporaryDirectory() as tmp:
   prior=Path(tmp)/'prior.json';prior.write_text('{}');a['audioAdjudication']['evidence']=str(prior)
   s,e=corroborated_content_repairs(self.state([a]),parsed,Path('whole.json'),{});self.assertEqual(s['standard'],[]);self.assertEqual(s['sdh'],[])
 def test_explicit_sound_adjudication_requires_distinct_stored_audio_responses(self):
  with tempfile.TemporaryDirectory() as tmp:
   paths=[]
   for name,body in [('a','first audio review'),('copy','first audio review'),('b','second audio review'),('full','complete episode third review')]:
    p=Path(tmp)/(name+'.json');p.write_text(body);paths.append(p)
   sound=dict(id='S001',sourceSoundId='1',kind='sound',text='[chime]',start=1,end=3)
   decisions={'1':{'status':'KEEP','evidence':str(paths[3])}}
   state={'standard':[],'sdh':[sound],'soundEvidenceRecheckTasks':[]}
   verdict=dict(id='1',decision='REMOVE',caption='[chime]',uncertain=False,confidence='high',resolves_prior_disagreement=True,prior_reason_addressed='The earlier onset interpretation duplicates the sung theme accent and conveys no separate story information.',audio_evidence='The chime is mixed into the already captioned sung entrance.',narrative_value='none')
   r={'interval':[0,660],'parsed':{'sound_reviews':[verdict]}}
   out,d,e=explicit_sound_adjudications(state,decisions,r,paths[3]);self.assertEqual(len(out['sdh']),1)
   decisions['1']['evidence']=str(paths[0])
   out,d,e=explicit_sound_adjudications(state,decisions,r,paths[3]);self.assertEqual(out['sdh'],[]);self.assertEqual(d['1']['status'],'REMOVE')
   verdict['resolves_prior_disagreement']=False
   out,d,e=explicit_sound_adjudications(state,decisions,r,paths[3]);self.assertEqual(len(out['sdh']),1)
 def test_scoped_content_review_preserves_other_doubts_and_unverified_timing(self):
  with tempfile.TemporaryDirectory() as tmp:
   old=Path(tmp)/'old.json';old.write_text('old original-audio witness');new=Path(tmp)/'new.json';new.write_text('new complete audio review')
   a=self.cue();a.update(sourceEvidence=str(old),unresolved='Targeted audio review remains uncertain: disputed word; 时间边界尚无逐词证据，需复核。',timingReview='pending: no exact match',timingEvidence='');a.pop('wordAnchors')
   b=self.cue('b','b',4,6,'Other words.');s=self.state([a,b]);s['latestReviewFindings']=[{'id':'b','source':'whole_episode_recheck','reason':'Another unresolved utterance'}]
   r={'interval':[0,660],'parsed':{'speech':[],'cue_reviews':[dict(id='a',verdict='agree',uncertain=False,resolves_prior_disagreement=True,prior_reason_addressed='The complete mix clearly contains the exact two narrator words.')],'sound_reviews':[]}}
   out,_,_=apply_review(s,r,new,{},[],{},reviewed_ids={'a'})
   self.assertEqual(out['standard'][0]['unresolved'],'时间边界尚无逐词证据，需复核。');self.assertTrue(any(x.get('id')=='b' for x in out['latestReviewFindings']));self.assertNotIn('wholeEpisodeReview',out)
 def test_two_explicit_audio_corrections_preserve_words_and_leave_timing_open(self):
  with tempfile.TemporaryDirectory() as tmp:
   prior=Path(tmp)/'old.json';prior.write_text('first complete mix');new=Path(tmp)/'new.json';new.write_text('second complete mix')
   c=self.cue(text='Wrong there.');s=self.state([c]);v=dict(id='a',verdict='correct',corrected_text='Hello there.',uncertain=False,resolves_prior_disagreement=True,audio_evidence='The narrator clearly says Hello there.',prior_reason_addressed='The first word is hello, with an audible initial h, not wrong.')
   r={'parsed':{'cue_reviews':[v]}};out,e=explicitly_corroborated_words(s,r,new,r,prior)
   self.assertEqual(out['standard'][0]['text'],'Hello there.');self.assertEqual(out['sdh'][0]['text'],'Hello there.');self.assertEqual(out['standard'][0]['timingEvidence'],'');self.assertIn('时间边界',out['standard'][0]['unresolved']);self.assertEqual(out['sourceManifest']['standard']['a'],'Hello there.')

if __name__=='__main__':unittest.main()
