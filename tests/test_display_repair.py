import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from layout_policy import display_word_anchors,fit_sound_dialogue
from display_repair import repair,metrics
from fidelity import words
class DisplayRepairTest(unittest.TestCase):
 def test_bounded_display_edit_reuses_only_valid_sound_evidence(self):
  from evidence_gate import evidence_flags,signature
  sound={'id':'s','kind':'sound','start':0.,'end':4.,'text':'[wind]',
         'semanticReview':{'status':'machine_reviewed','caption':'[wind]','start':0.,'end':4.,
         'audioEvidence':'Wind heard','narrativeValue':'Storm threatens characters',
         'evidence':['first.json','second.json'],'clip':[0.,5.],'uncertain':False}}
  sound['reviewBinding']=signature(sound)
  dialogue={'id':'d','kind':'speech','start':1.2,'end':3.,'text':'This long sentence needs two lines in the finished subtitle.'}
  out,changes=repair([sound,dialogue],[],24)
  self.assertTrue(changes);self.assertFalse(evidence_flags(out[0]))
  self.assertEqual(out[0]['semanticReview'],sound['semanticReview'])
  self.assertFalse(out[0].get('checked'));self.assertIn('displayEvidenceCheck',out[0])
  sound['semanticReview']['uncertain']=True
  out,changes=repair([sound,dialogue],[],24)
  self.assertTrue(changes);self.assertIn('semantic_evidence_conflict',evidence_flags(out[0]))
  self.assertNotIn('displayEvidenceCheck',out[0])
 def test_hyphenated_exact_anchors(self):
  a=[{'word':w,'start':i,'end':i+1,'probability':.9}for i,w in enumerate(['Tick','Tick','bite','sized'])]
  mapped=display_word_anchors('Tick-Tick bite-sized',a)
  self.assertEqual([(x['word'],x['start'],x['end'])for x in mapped],[('Tick-Tick',0,2),('bite-sized',2,4)])
  self.assertEqual(display_word_anchors('Tick-Tick rice',a),[])
 def test_machine_lock_and_manual_lock(self):
  base=[{'id':'s','kind':'sound','start':0.,'end':2.8,'audioStart':0.,'audioEnd':3.,'text':'[wind]','displayTimingLock':True,'displayPolicy':{'rule':'sustained_sound_onset_label'}},{'id':'d','kind':'speech','start':1.,'end':3.,'text':'Hello.'}]
  out,changes=repair(base,[],24)
  self.assertTrue(changes);self.assertEqual(out[1],base[1]);self.assertTrue(all(a<=b for a,b in zip(metrics(out,24),metrics(base,24))))
  again,_=repair(out,[],24);self.assertEqual(again,out)
  for lock in [{'human':True},True]:
   manual=copy.deepcopy(base);manual[0]['displayTimingLock']=lock;manual[0].pop('displayPolicy')
   self.assertEqual(repair(manual,[],24)[0],manual)
 def test_missing_cuts_and_checked(self):
  rows=[{'id':'s','kind':'sound','start':0.,'end':2.8,'text':'[wind]','checked':True},{'id':'d','kind':'speech','start':1.,'end':3.,'text':'Hello.'}]
  self.assertEqual(repair(rows,None)[0],rows);self.assertEqual(repair(rows,[])[0],rows)
 def test_readable_onset_label_can_exit_before_later_dialogue(self):
  rows=[{'id':'s','kind':'sound','start':0.,'end':4.,'soundAudioStart':0.,'soundAudioEnd':4.,'text':'[wind]'},
        {'id':'d','kind':'speech','start':1.2,'end':3.,'text':'This long sentence needs two lines in the finished subtitle.'}]
  out,changes=repair(rows,[],24)
  self.assertTrue(changes)
  self.assertEqual(out[1],rows[1]);self.assertEqual(out[0]['soundAudioEnd'],4.)
  self.assertGreaterEqual(out[0]['end']-out[0]['start'],20/24)
  self.assertTrue(all(a<=b for a,b in zip(metrics(out,24),metrics(rows,24))))
  self.assertEqual(repair(out,[],24)[0],out)
 def test_real_anchor_split_keeps_all_words(self):
  text='Could you cut the vegetables into bite-sized pieces, please?'
  tokens=['Could','you','cut','the','vegetables','into','bite','sized','pieces','please']
  cue={'id':'d','kind':'speech','start':0.,'end':5.,'text':text,'wordAnchors':[{'word':w,'start':i*.45,'end':(i+1)*.45,'probability':.99}for i,w in enumerate(tokens)]}
  rows,changes=fit_sound_dialogue([cue],[(0,5)])
  self.assertTrue(changes);self.assertEqual(words(' '.join(c['text']for c in rows)),words(text))
  self.assertTrue(all(len(c['text'])<=42 and c['end']-c['start']>=20/24 for c in rows))
if __name__=='__main__':unittest.main()
