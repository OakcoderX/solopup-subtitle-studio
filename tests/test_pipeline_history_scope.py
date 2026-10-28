import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from history import record
from scope import validate
from timing_review import align
from fidelity import audit
class PipelineTests(unittest.TestCase):
 def test_history_preserves_before_after_words_and_reason(self):
  with tempfile.TemporaryDirectory() as d:
   before={'standard':[{'id':'D1','text':'First, mix together.','start':1,'end':2}]};after={'standard':[{'id':'D1','text':'First, mix together.','start':1,'end':3}]}
   e=record(d,'timing',before,after,'Use measured tail room')
   self.assertEqual(len(e['changes']),1);self.assertEqual(e['changes'][0]['path'],'/standard/D1/end')
   self.assertEqual(json.loads((Path(d)/'history'/e['before_snapshot']).read_text()),before)
   record(d,'second',after,after,'No lexical edits')
   lines=(Path(d)/'history/events.jsonl').read_text().splitlines();self.assertEqual(len(lines),2);self.assertEqual(json.loads(lines[0])['reason'],'Use measured tail room')
 def test_scope_explicit_full_vs_program_and_invalid_bounds(self):
  self.assertEqual(validate({'mode':'full'},660)['end'],660)
  self.assertEqual(validate({'mode':'custom','start':'00:58','end':'10:00'},660)['start'],58)
  for x in [{'mode':'custom','start':600,'end':58},{'mode':'custom','start':0,'end':661},{'mode':'custom','start':'nan','end':600}]:
   with self.assertRaises(ValueError):validate(x,660)
 def test_timing_witness_cannot_rewrite_transcript(self):
  row={'id':'a','text':'Mix everything together.','sourceText':'Mix everything together.','sourceGroup':'a','start':10,'end':13}
  w={'segments':[{'words':[{'word':'Mix','start':10,'end':10.3,'probability':.9},{'word':'together.','start':11,'end':12,'probability':.9}]}]}
  result,events=align([row],w,24);self.assertEqual(result[0]['text'],row['text']);self.assertEqual(events,[]);self.assertTrue(result[0]['timingReview'].startswith('pending'));self.assertFalse(audit(result))
 def test_same_words_elsewhere_cannot_supply_timing(self):
  row={'id':'a','text':'Hello there.','sourceText':'Hello there.','sourceGroup':'a','start':50,'end':51}
  w={'segments':[{'words':[{'word':'Hello','start':1,'end':2,'probability':.9},{'word':'there','start':2,'end':3,'probability':.9}]}]}
  result,events=align([row],w,24);self.assertFalse(events);self.assertEqual(result[0]['start'],50)
 def test_exact_match_changes_time_without_changing_words(self):
  row={'id':'a','text':'First, mix together.','sourceText':'First, mix together.','sourceGroup':'a','start':10,'end':11}
  w={'segments':[{'words':[{'word':t,'start':9.5+i*.5,'end':10+i*.5,'probability':.95} for i,t in enumerate(['First,','mix','together.'])]}]}
  result,events=align([row],w,24);self.assertEqual(result[0]['start'],9.5);self.assertFalse(audit(result));self.assertEqual(len(events),1)
 def test_repeated_cues_cannot_reuse_the_same_audio_words(self):
  row={'id':'a','text':'Hello there.','sourceText':'Hello there.','sourceGroup':'a','start':10,'end':11}
  w={'segments':[{'words':[{'word':'Hello','start':10,'end':10.4,'probability':.9},{'word':'there','start':10.4,'end':11,'probability':.9}]}]}
  result,events=align([row,dict(row,id='b',start=11,end=12)],w,24)
  self.assertEqual(len(events),1);self.assertTrue(result[1]['timingReview'].startswith('pending'))
if __name__=='__main__':unittest.main()
