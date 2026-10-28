import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from tail_room import extend_tails

class TailRoomTests(unittest.TestCase):
    def cue(self, **kwargs):
        return dict(dict(id='D1', start=0, end=1, text='abcdefghijklmnopqr',
                         audioEnd=1, timingEvidence='word anchors', checked=True), **kwargs)

    def test_extend_without_changing_words_or_source(self):
        c=self.cue(); out, audit=extend_tails([c], [], scope_end=10)
        self.assertEqual(out[0]['text'], c['text']); self.assertEqual(c['end'],1)
        self.assertLessEqual(audit[0]['after_cps'],17); self.assertFalse(out[0]['checked'])

    def test_word_rate_can_require_extension_below_cps_limit(self):
        c=self.cue(text='a b c');out,_=extend_tails([c],[])
        self.assertEqual(out[0]['end'],1.5);self.assertEqual(out[0]['text'],'a b c')

    def test_half_second_is_total_not_per_run(self):
        c=self.cue(text='x'*40); out,_=extend_tails([c], [])
        self.assertEqual(out[0]['end'],1.5)
        again,_=extend_tails(out, []); self.assertEqual(again,out)

    def test_next_cue_cut_and_scope_limits(self):
        for cuts,scope,following,expected in [([],10,[self.cue(start=1.25,end=3)],28/24),
                                             ([1.25],10,[],28/24),([],1.25,[],1.25)]:
            out,_=extend_tails([self.cue(text='x'*40)]+following,cuts,scope_end=scope)
            self.assertEqual(out[0]['end'],expected)

    def test_missing_evidence_no_change(self):
        for c,cuts in [(self.cue(timingEvidence=''),[]),(self.cue(),None)]:
            out,_=extend_tails([c],cuts); self.assertEqual(out,[c])

    def test_max_duration_and_acceptance_invalidation(self):
        c=self.cue(end=6.8,audioEnd=7,text='x'*140,speedReview={'accepted':True})
        out,_=extend_tails([c],[]); self.assertEqual(out[0]['end'],7)
        self.assertFalse(out[0]['speedReview']['accepted'])

    def test_never_shorten_existing_cue(self):
        c=self.cue(end=1.6,text='x'*40)
        out,_=extend_tails([c],[1.25]); self.assertEqual(out,[c])

    def test_sound_label_duration_is_not_extended(self):
        c=self.cue(text='[friends chatter excitedly]')
        out,_=extend_tails([c],[]); self.assertEqual(out,[c])

    def test_short_slow_caption_still_gets_minimum_duration(self):
        c=self.cue(text='Oh',end=.6,audioEnd=.6)
        out,_=extend_tails([c],[])
        self.assertEqual(out[0]['end'],20/24)

    def test_extension_cannot_make_composite_longer_than_seven_seconds(self):
        sound=self.cue(id='S',text='[music]',start=0,end=6.5)
        speech=self.cue(id='D',text='x'*100,start=6,end=6.9,audioEnd=6.9)
        out,_=extend_tails([sound,speech],[])
        self.assertEqual(out[-1]['end'],7)

if __name__=='__main__':unittest.main()
