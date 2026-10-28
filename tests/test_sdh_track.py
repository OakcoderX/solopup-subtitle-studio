import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from sdh_track import compose
class SdhTrackTests(unittest.TestCase):
 def setUp(self):
  self.state={'standard':[{'id':'D1','start':1,'end':2,'text':'Hello'}],'sdh':[{'id':'D1','start':1,'end':2,'text':'Hello'}],'release':{'content_verified':False,'blockers':[]}}
  self.rows=[{'start':2,'end':3,'caption':'[laughing]'}, {'start':4,'end':5,'caption':'[wind]'}]
  self.decisions={'1':{'status':'KEEP','reviewer':'assistant','humanApproved':False},'2':{'status':'','recommendation':'KEEP'}}
 def test_pending_does_not_hide_decided_proposals(self):
  out=compose(self.state,self.rows,self.decisions)
  self.assertEqual(out['standard'],self.state['standard']);self.assertEqual(len(out['sdh']),2)
  self.assertFalse(out['sdh'][1]['checked']);self.assertIn('unresolved',out['sdh'][1]);self.assertEqual(out['sdhComposition']['pending'],1)
  self.assertFalse(out['release']['content_verified'])
 def test_repeat_preserves_manual_caption_edits_without_duplication(self):
  out=compose(self.state,self.rows,self.decisions);out['sdh'][1]['text']='[soft laughter]';out['sdh'][1]['end']=3.2
  self.assertEqual(compose(out,self.rows,self.decisions),out)
 def test_remove_touches_only_candidate_owned_cue(self):
  out=compose(self.state,self.rows,self.decisions);out['sdh'].append({'id':'manual','start':2,'end':3,'text':'[bell]'})
  decisions=copy.deepcopy(self.decisions);decisions['1']['status']='REMOVE'
  out=compose(out,self.rows,decisions);self.assertEqual([c['id'] for c in out['sdh']],['D1','manual'])
 def test_revision_updates_proposal_without_duplicate(self):
  out=compose(self.state,self.rows,self.decisions);d=copy.deepcopy(self.decisions);d['1'].update(status='REVISE',caption='[chuckling]')
  out=compose(out,self.rows,d);self.assertEqual(len(out['sdh']),2);self.assertEqual(out['sdh'][1]['text'],'[chuckling]')
if __name__=='__main__':unittest.main()
