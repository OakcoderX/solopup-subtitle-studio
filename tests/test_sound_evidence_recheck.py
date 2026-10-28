import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from sound_evidence_recheck import apply_agreements,validate

class SoundRecheckTests(unittest.TestCase):
 def test_partial_recheck_preserves_unreviewed_and_failed_window_tasks(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'first.json';p.write_text('{}');s,d,c,r=self.fixture(p)
   prior=[{'id':'S001','action':'old doubt'},{'id':'S002','action':'other window doubt'}]
   s['soundEvidenceRecheckTasks']=prior
   out,_,_,tasks=apply_agreements(s,d,c,{})
   self.assertEqual(tasks,prior)
   out,_,ledger,tasks=apply_agreements(s,d,c,{'1':(r,Path(td)/'second.json',[0,4])})
   self.assertEqual(len(ledger),1)
   self.assertEqual(tasks,[prior[1]])
   self.assertEqual(out['soundEvidenceRecheckTasks'],tasks)
 def fixture(self,p):
  c={'id':'S001','sourceSoundId':'1','kind':'sound','start':1.,'end':3.,'text':'[wind]',
     'checked':False,'unresolved':'SDH 系统建议，待视听确认。 时间需复核。'}
  d={'status':'KEEP','caption':'[wind]','uncertain':False,'audioEvidence':'Wind heard','evidence':str(p)}
  r={'id':'1','decision':'KEEP','caption':'[wind]','uncertain':False,'audio_evidence':'Loud wind',
     'picture_evidence':'Trees sway','narrative_value':'Storm threatens characters','reason':'Narrative cue'}
  return {'standard':[],'sdh':[c],'release':{}},{'1':d},[{'start':'1','end':'3'}],r
 def test_agreement_clears_only_generic_notice_never_human_or_other_doubt(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'first.json';p.write_text('{}');s,d,c,r=self.fixture(p)
   out,dec,ledger,tasks=apply_agreements(s,d,c,{'1':(r,Path(td)/'second.json',[0,4])})
   self.assertEqual(len(ledger),1);self.assertEqual(out['sdh'][0]['unresolved'],'时间需复核。')
   self.assertFalse(out['sdh'][0]['checked']);self.assertFalse(out['release']['content_verified'])
 def test_disagreement_and_outside_clip_do_not_resolve(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'first.json';p.write_text('{}');s,d,c,r=self.fixture(p)
   r['decision']='REMOVE'
   out,_,ledger,tasks=apply_agreements(s,d,c,{'1':(r,Path(td)/'second.json',[0,4])})
   self.assertFalse(ledger);self.assertEqual(len(tasks),1);self.assertEqual(out['sdh'],s['sdh'])
   r['decision']='KEEP'
   self.assertFalse(apply_agreements(s,d,c,{'1':(r,Path(td)/'second.json',[0,2])})[2])
 def test_human_protected_and_incomplete_response_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'first.json';p.write_text('{}');s,d,c,r=self.fixture(p);d['1']['humanApproved']=True
   self.assertFalse(apply_agreements(s,d,c,{'1':(r,Path(td)/'second.json',[0,4])})[2])
  with self.assertRaises(ValueError):validate({'reviews':[]},['1'])
  with self.assertRaises(ValueError):validate({'reviews':[r,r]},['1'])
 def test_explicit_third_adjudication_can_remove_only_sound_preserving_dialogue(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'first.json';p.write_text('{}');s,d,c,r=self.fixture(p)
   speech={'id':'D','text':'Hello.','kind':'speech','start':1,'end':3}
   s['sdh'].append(speech);s['standard'].append(speech)
   r['decision']='REMOVE';r['adjudication']=dict(r)
   r['adjudication_evidence']=str(Path(td)/'third.json')
   out,dec,ledger,tasks=apply_agreements(s,d,c,{'1':(r,Path(td)/'second.json',[0,4])})
   self.assertEqual(out['sdh'],[speech]);self.assertEqual(out['standard'],[speech])
   self.assertEqual(dec['1']['status'],'REMOVE');self.assertTrue(ledger[0]['removed'])
   r['adjudication']['uncertain']=True
   self.assertFalse(apply_agreements(s,d,c,{'1':(r,Path(td)/'second.json',[0,4])})[2])
if __name__=='__main__':unittest.main()
