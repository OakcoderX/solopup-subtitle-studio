import json,sys,tempfile,time,threading,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from library import Library
class ParallelLibraryTests(unittest.TestCase):
 def test_three_workers_claim_each_episode_once(self):
  launches=[];lock=threading.Lock()
  class Process:
   def __init__(self,command,**kw):
    self.until=time.monotonic()+.8
    with lock:launches.append((command[command.index('--output')+1],time.monotonic()))
   def poll(self):return None if time.monotonic()<self.until else 0
   def wait(self,**kw):return 0
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'runtime.json').write_text(json.dumps({'episode_workers':3}))
   video=root/'test.mp4';video.write_bytes(b'test fixture')
   with patch('library.subprocess.Popen',Process):
    lib=Library(root);pid=lib.project('test')
    ids=lib.enqueue(pid,[{'video':str(video),'title':str(i)}for i in range(3)])
    limit=time.monotonic()+5
    while time.monotonic()<limit and any(lib.get(i)['status']!='ready'for i in ids):time.sleep(.05)
    self.assertTrue(all(lib.get(i)['status']=='ready'for i in ids));self.assertEqual(len(launches),3)
    self.assertEqual(len(set(p for p,t in launches)),3)
    self.assertLess(max(t for p,t in launches)-min(t for p,t in launches),.6)
    self.assertEqual(lib.snapshot()['concurrency'],3);lib.close()

class ReviewCacheCoverageTests(unittest.TestCase):
    def test_incomplete_response_is_not_reused(self):
        from review_pass import cache_valid
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'review.json'
            path.write_text(json.dumps({'input_fingerprint':'a','parsed':{'cue_reviews':[{'id':'D1'}],'sound_reviews':[{'id':'1','decision':'KEEP','caption':'[wind]'}]}}))
            self.assertTrue(cache_valid(path,'a',{'D1'},{'1'}))
            self.assertFalse(cache_valid(path,'a',{'D1','D2'},{'1'}))
            self.assertFalse(cache_valid(path,'a',{'D1'},{'1','2'}))
            path.write_text(json.dumps({'input_fingerprint':'a','parsed':{'cue_reviews':[{'id':'D1'}],'sound_reviews':[{'id':'1','verdict':'agree','caption':'[wind]'}]}}))
            self.assertFalse(cache_valid(path,'a',{'D1'},{'1'}))

    def test_uncertain_correction_preserves_original_words(self):
        from repair_apply import reviewed_candidate
        state={'standard':[{'id':'a','text':'Hello, Iris.','sourceText':'Hello, Iris.','sourceGroup':'a','start':1,'end':3}],'release':{}}
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'repair.json'
            p.write_text(json.dumps({'parsed':{'verdicts':[{'id':'a','action':'CORRECT','text':'Hello, Chamille.','uncertain':True,'reason':'name unclear'}]}}))
            candidate,_=reviewed_candidate(state,[p])
            self.assertEqual(candidate['standard'][0]['text'],'Hello, Iris.')
            self.assertTrue(candidate['standard'][0]['unresolved'])

    def test_zero_length_asr_word_cannot_replace_valid_cue_time(self):
        from timing_review import align
        cue={'id':'a','text':'Amazing!','start':81.8,'end':82.7}
        witness={'segments':[{'words':[{'word':'Amazing!','start':82.62,'end':82.62,'probability':.96}]}]}
        rows,events=align([cue],witness,24)
        self.assertEqual((rows[0]['start'],rows[0]['end']),(81.8,82.7))
        self.assertEqual(events,[])
        self.assertTrue(rows[0]['timingReview'].startswith('pending'))
