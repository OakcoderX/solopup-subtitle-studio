import sys,tempfile,unittest
from pathlib import Path
from xml.etree import ElementTree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from timed_text import check,write_itt
from confirmed_sounds import inherit,media_key,save_human
from review_pass import cache_valid
class DeliveryPolicyTests(unittest.TestCase):
 def c(self,i,a,b,text,**kw):return dict(id=i,start=a,end=b,text=text,sourceText='' if kw.get('kind')=='sound' else text,sourceGroup=i,**kw)
 def test_simultaneous_lines_checked_across_nonadjacent_cues(self):
  rows=[self.c('D',0,6,'This first line has a longer sentence.\nThe second line needs its own space.'),self.c('S',1,2,'[wind]',kind='sound'),self.c('T',3,4,'[bell]',kind='sound')]
  issues=check(rows);self.assertEqual(sum('simultaneous_line_limit' in i['flags'] for i in issues),2)
 def test_sound_format_and_voiceover(self):
  self.assertIn('sound_all_caps',check([self.c('S',0,3,'[WIND]',kind='sound')])[0]['flags'])
  self.assertIn('italic_required',check([self.c('D',0,3,'Hello',presentation='voiceover')])[0]['flags'])
 def test_long_dialogue_overlap_cannot_hide_behind_short_sound(self):
  rows=[self.c('A',0,6,'Hello'),self.c('S',1,2,'[bell]',kind='sound'),self.c('B',3,5,'Yes')]
  self.assertTrue(any('simultaneous_dialogue_overlap' in i['flags'] for i in check(rows)))
 def test_relative_span_uses_absolute_frame_difference(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.itt';write_itt([self.c('D',.020,4,'Hello'),self.c('S',1.023,3,'[wind]',kind='sound')],p)
   paras=E.parse(p).findall('.//{http://www.w3.org/ns/ttml}p')
   self.assertEqual(paras[1].get('begin'),'00:00:01:01')
   self.assertEqual(''.join(paras[1].itertext()),'[wind]Hello')
 def test_minimum_is_twenty_frames_at_30fps(self):
  self.assertFalse(check([self.c('D',0,20/30,'Hello')],rate='30'))
  self.assertIn('duration_short',check([self.c('D',0,19/30,'Hello')],rate='30')[0]['flags'])
 def test_combined_itt_retains_independent_relative_onsets(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.itt';write_itt([self.c('D',1,4,'Hello',italic=True),self.c('S',2,3,'[wind]',kind='sound')],p)
   root=E.parse(p);ns={'t':'http://www.w3.org/ns/ttml'};paras=root.findall('.//t:p',ns)
   self.assertEqual(len(paras),3)
   self.assertEqual([(''.join(p.itertext()),p.get('begin'),p.get('end')) for p in paras],[('Hello','00:00:01:00','00:00:02:00'),('[wind]Hello','00:00:02:00','00:00:03:00'),('Hello','00:00:03:00','00:00:04:00')])
   self.assertEqual([len(p.findall('t:br',ns)) for p in paras],[0,1,0])
 def test_confirmation_cannot_be_overridden(self):
  old={'start':1,'end':3,'decision':{'status':'KEEP','caption':'[wind]','reviewer':'human','humanApproved':True}}
  out,conflicts=inherit([{'start':1,'end':3}],{'1':{'status':'REMOVE','caption':'[chewing]'}},[old])
  self.assertEqual(out['1']['status'],'');self.assertEqual(out['1']['confirmedPrior'],old);self.assertTrue(conflicts)
  out,conflicts=inherit([{'start':1,'end':3}],{'1':{'status':'KEEP','caption':'[wind]'}},[old]);self.assertTrue(out['1']['humanApproved']);self.assertFalse(conflicts)
 def test_missing_confirmation_blocks_inheritance_silently_lost(self):
  _,events=inherit([],{},[{'start':1,'end':3,'decision':{'status':'KEEP'}}]);self.assertEqual(events[0]['status'],'missing_or_ambiguous_match')
 def test_old_review_file_does_not_complete_changed_input(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'review.json';p.write_text('{"input_fingerprint":"old"}')
   self.assertFalse(cache_valid(p,'new'));self.assertTrue(cache_valid(p,'old'))
   p.write_text('{bad');self.assertFalse(cache_valid(p,'old'))
 def test_song_identifier_before_music_note_is_valid(self):
  self.assertFalse(check([self.c('L',0,5,'[both singing] ♪ Hello ♪',kind='song',italic=True)]))
 def test_media_key_follows_bytes_not_filename(self):
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/'a';b=Path(d)/'b';a.write_bytes(b'video');b.write_bytes(b'video');self.assertEqual(media_key(a),media_key(b));b.write_bytes(b'other');self.assertNotEqual(media_key(a),media_key(b))
if __name__=='__main__':unittest.main()
