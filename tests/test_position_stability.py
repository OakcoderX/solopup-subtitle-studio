import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from presentation import position_changes,stabilize
from sound_readability import improve
from timed_text import frame,check
from layout_policy import prepare
class StabilityTests(unittest.TestCase):
 def cue(self,id,start,end,text,**kw):return dict(id=id,start=start,end=end,text=text,**kw)
 def test_detect_both_directions(self):
  rows=[self.cue('S',0,4,'[wind]',kind='sound'),self.cue('D',1,3,'Hello')]
  self.assertEqual([x['time']for x in position_changes(rows,frame,'24')],[1,3])
 def test_joint_entry_exit_and_replacement_not_jumps(self):
  rows=[self.cue('S',0,2,'[wind]',kind='sound'),self.cue('D',0,2,'Hello'),self.cue('E',2,4,'Goodbye')]
  self.assertEqual(position_changes(rows,frame,'24'),[])
 def test_gap_and_two_line_cue_not_false_positive(self):
  rows=[self.cue('D',0,2,'A fairly long sentence that needs two lines to display.'),self.cue('E',3,4,'Hello')]
  self.assertEqual(position_changes(rows,frame,'24'),[])
 def test_reviewed_timing_survives_helpers(self):
  rows=[self.cue('S',1,2,'[cat meowing]',kind='sound',displayTimingLock={'reason':'reviewed'}),self.cue('D',1,2.3,'Hello')]
  self.assertEqual(stabilize(improve(rows,[],24))[0],rows[0])
 def test_generation_and_delivery_report_warning(self):
  rows=[self.cue('S',0,4,'[wind]',kind='sound'),self.cue('D',1,3,'Hello')]
  self.assertEqual(len(prepare({'sdh':rows,'standard':[]})['presentationTasks']),2)
  items=[x for x in check(rows) if 'vertical_position_jump' in x['flags']]
  self.assertEqual(len(items),2)
  self.assertTrue(all(not x['blocking_flags']for x in items))
if __name__=='__main__':unittest.main()
