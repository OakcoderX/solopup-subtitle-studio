import unittest,sys,tempfile,json,subprocess,re
from pathlib import Path
from xml.etree import ElementTree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from layout_policy import prepare,wrap,split_verified,repair_legacy_split_anchors
from presentation import layout_parts,visible_events
from timed_text import write_itt,check,frame,blocking_issues
class LayoutTests(unittest.TestCase):
 def cue(self,text,**kw):return dict(id='D',start=0,end=4,text=text,**kw)
 def test_long_sentence_is_actionable_and_blocks_delivery(self):
  text="Please arrange the wooden chairs beside the tall windows before our evening workshop starts."
  state=prepare({'standard':[self.cue(text)],'sdh':[]})
  self.assertEqual(state['standard'][0]['text'],text)
  self.assertEqual(state['layoutTasks'][0]['action'],'split_at_verified_audio_boundary')
  self.assertTrue(any('line_limit' in i['flags'] for i in blocking_issues(check(state['standard']))))
 def test_reflow_preserves_words_and_invalidates_acceptance(self):
  c=self.cue('One short\nline.',checked=True,speedReview={'accepted':True})
  state=prepare({'standard':[c],'sdh':[]})
  self.assertEqual(state['standard'][0]['text'],'One short line.')
  self.assertFalse(state['standard'][0]['checked'])
  self.assertFalse(state['standard'][0]['speedReview']['accepted'])
  self.assertEqual(prepare(state),state)
 def test_combined_budget_queues_audio_review(self):
  rows=[self.cue('This is a sufficiently long sentence to require two lines.'),self.cue('[wind]',kind='sound')]
  state=prepare({'standard':[],'sdh':rows})
  self.assertTrue(any(t['action']=='resolve_simultaneous_layout' for t in state['layoutTasks']))
 def test_batch_preparation_preserves_checked_text_and_acceptance(self):
  c=self.cue('One short\nline.',checked=True,speedReview={'accepted':True})
  state=prepare({'standard':[c],'sdh':[]},preserve_checked=True)
  self.assertTrue(state['standard'][0].pop('reviewBinding'))
  self.assertEqual(state['standard'][0],c)
 def test_internal_anchor_survives_uncertain_opening_but_not_wrong_words(self):
  cue=self.cue('Oh, hello. Please come in.',end_unused=True)
  cue['end']=5
  ws=[{'word':w,'start':t,'end':t+.4,'probability':p}for w,t,p in [('Oh,',0,.1),('hello.',.5,.99),('Please',2,.99),('come',2.5,.99),('in.',3,.99)]]
  witness={'segments':[{'start':0,'end':4,'words':ws}]}
  result=split_verified(cue,'Oh, hello.',witness)
  self.assertEqual([x['text']for x in result],['Oh, hello.','Please come in.'])
  self.assertGreaterEqual(result[1]['start']-result[0]['end'],2/24)
  self.assertAlmostEqual(result[0]['audioEnd'],.9)
  self.assertLess(result[0]['end'],1)
  ws[2]['word']='Maybe'
  with self.assertRaises(ValueError):split_verified(cue,'Oh, hello.',witness)
 def test_preview_export_contract_all_intervals(self):
  root=Path(__file__).resolve().parents[1];html=(root/'workbench/index.html').read_text()
  js=html[html.index('function wrapCaption'):html.index('function layoutDetail')]
  cases=[[],[self.cue('Hello\nthere.')],[self.cue('[wind]',kind='sound'),self.cue('Hello there.',italic=True)],
   [self.cue('[water splash]',kind='sound'),self.cue('[laughter]',kind='sound'),self.cue('The fish pastry mold.')],
   [self.cue('A fairly long line with some words and another phrase for wrapping.')]]
  script=js+'\nconsole.log(JSON.stringify('+json.dumps(cases)+'.map(g=>captionLines(g).map(l=>l.map(p=>p.text).join("")))))'
  actual=json.loads(subprocess.check_output(['node','-e',script],text=True))
  expected=[[''.join(t for c,t in line) for line in layout_parts(g)]for g in cases]
  self.assertEqual(actual,expected)
  for g,want in zip(cases[1:],expected[1:]):
   with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'test.itt';write_itt(g,p)
    para=E.parse(p).find('.//{http://www.w3.org/ns/ttml}p');lines=['']
    def read(el):
     if el.text:lines[-1]+=el.text
     for child in el:
      if child.tag.endswith('}br'):lines.append('')
      else:read(child)
      if child.tail:lines[-1]+=child.tail
    read(para);self.assertEqual(lines,want)
 def test_exact_split_crosses_asr_segment_without_fabricating_words(self):
  cue=self.cue('Oh, hello. Please come in.');cue['end']=5
  ws=[{'word':w,'start':t,'end':t+.4,'probability':.99}
      for w,t in [('Oh,',0),('hello.',.5),('Please',2),('come',2.5),('in.',3)]]
  witness={'segments':[{'start':0,'end':1,'words':ws[:2]},
                       {'start':2,'end':4,'words':ws[2:]}]}
  children=split_verified(cue,'Oh, hello.',witness)
  self.assertEqual(children[1]['start'],2)
  witness['segments'][1]['words'][0]['word']='Maybe'
  with self.assertRaises(ValueError):split_verified(cue,'Oh, hello.',witness)
 def test_cross_segment_match_rejects_long_silence_and_duplicate_witness(self):
  cue=self.cue('Hello there. Come in.');cue['end']=10
  ws=[{'word':w,'start':t,'end':t+.4,'probability':.99}
      for w,t in [('Hello',0),('there.',.5),('Come',6),('in.',7)]]
  witness={'segments':[{'start':0,'end':8,'words':ws}]}
  with self.assertRaises(ValueError):split_verified(cue,'Hello there.',witness)
  ws[2]['start']=2;ws[2]['end']=2.4;ws[3]['start']=3;ws[3]['end']=3.4
  witness['segments']*=2
  with self.assertRaises(ValueError):split_verified(cue,'Hello there.',witness)
 def test_numeric_format_matches_exact_value_without_inventing_tail(self):
  cue=self.cue('175 grams, then stir.');cue['end']=5
  ws=[{'word':w,'start':t,'end':t+.3,'probability':.99} for w,t in
      [('one',0),('hundred',.4),('seventy',.8),('five',1.2),('grams,',1.6),('then',3),('stir.',3.4)]]
  witness={'segments':[{'start':0,'end':2,'words':ws[:5]},{'start':3,'end':4,'words':ws[5:]}]}
  children=split_verified(cue,'175 grams,',witness)
  self.assertEqual(children[0]['text'],'175 grams,');self.assertAlmostEqual(children[0]['audioEnd'],1.9)
  self.assertEqual(children[1]['start'],3)
  ws[3]['word']='six'
  with self.assertRaises(ValueError):split_verified(cue,'175 grams,',witness)
 def test_old_split_cannot_use_next_onset_as_audio_end(self):
  rows=[self.cue('Hello there.'),self.cue('Come in.')]
  rows[0].update(id='D-L1',end=2.9166666667,audioEnd=3)
  rows[1].update(id='D-L2',start=3,end=5)
  for c in rows:c['layoutSplit']={'parent':'D','prefix':'Hello there.','next_word':{'word':'Come','start':3}}
  witness={'segments':[{'start':0,'end':5,'words':[{'word':w,'start':t,'end':t+.4,'probability':.99} for w,t in [('Hello',0),('there.',1),('Come',3),('in.',4)]]}]}
  repaired,ledger=repair_legacy_split_anchors(rows,witness,24,[])
  self.assertTrue(ledger);self.assertAlmostEqual(repaired[0]['audioEnd'],1.4)
  self.assertLessEqual(repaired[0]['end'],1.9)
  self.assertEqual(repaired[1]['start'],3)
  self.assertEqual(repair_legacy_split_anchors(repaired,witness,24,[])[1],[])
if __name__=='__main__':unittest.main()
