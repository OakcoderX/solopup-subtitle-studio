import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from reconcile_review import restore_matching_anchors,deduplicate_review_witnesses,unique_review_key
from finish_pipeline import review_worker_count,expected_window_coverage
from fidelity import audit,words
from produce import same_boundary_witness

def cue(text,ident,start,end):
    return dict(id=ident,start=start,end=end,text=text,sourceText=text,sourceGroup=ident,kind='speech',checked=False)

class ReconciliationTests(unittest.TestCase):
    def test_review_worker_override_is_bounded(self):
        import os
        prior=os.environ.get('SDH_REVIEW_WORKERS')
        try:
            os.environ['SDH_REVIEW_WORKERS']='2';self.assertEqual(review_worker_count(),2)
            os.environ['SDH_REVIEW_WORKERS']='99';self.assertEqual(review_worker_count(),4)
            os.environ['SDH_REVIEW_WORKERS']='bad';self.assertEqual(review_worker_count(),3)
        finally:
            if prior is None:os.environ.pop('SDH_REVIEW_WORKERS',None)
            else:os.environ['SDH_REVIEW_WORKERS']=prior
    def test_retry_coverage_matches_review_window_ownership(self):
        state={'standard':[{'id':'overlap','start':8,'end':12},{'id':'owned','start':10.2,'end':11},{'id':'after','start':11.2,'end':12}]}
        cues,sounds=expected_window_coverage(state,10,11,20,[{'start':'10.1'},{'start':'11.0'}])
        self.assertEqual(cues,{'overlap','owned'})
        self.assertEqual(sounds,{'1'})
    def test_second_pass_ids_do_not_collide_with_source_draft_ids_or_groups(self):
        used={'Q0001','Q0002','R0085'}
        self.assertEqual(unique_review_key(1,used),'Q0003')
        self.assertEqual(unique_review_key(2,used),'Q0004')
    def test_second_pass_shared_witness_is_not_a_second_utterance(self):
        a=dict(cue('Hello!','a',10,12),witnessIds=['D1'])
        b=dict(cue('Hello.','b',10.1,12.1),witnessIds=['D1'])
        result,removed=deduplicate_review_witnesses([a,b])
        self.assertEqual(len(result),1);self.assertEqual(len(removed),1)
        b['witnessIds']=['D2'];self.assertEqual(len(deduplicate_review_witnesses([a,b])[0]),2)
        b.update(start=13,end=14,witnessIds=['D1']);self.assertEqual(len(deduplicate_review_witnesses([a,b])[0]),2)
    def test_boundary_complete_utterance_supersedes_truncated_prefix(self):
        a=dict(cue("Let's learn to build with",'a',419.5,421),witnessIds=['R1'],kind='speech')
        b=dict(cue("Let's learn to build with our bright toolkit!",'b',419.5,422.7),witnessIds=['R1','R2'],kind='speech')
        rows,removed=deduplicate_review_witnesses([a,b])
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['text'],b['text'])
        self.assertEqual(rows[0]['witnessIds'],['R1','R2']);self.assertEqual(len(removed),1)
    def test_boundary_punctuation_does_not_duplicate_spoken_word(self):
        a=dict(text='Perfect!',start=336.6,end=337.3,kind='speech',evidence='a.json')
        b=dict(text='Perfect.',start=336.6,end=337.4,kind='speech',evidence='b.json')
        self.assertTrue(same_boundary_witness(a,b))
        b['text']='Perfect, perfect!';self.assertFalse(same_boundary_witness(a,b))
        b.update(text='Perfect!',start=338,end=339);self.assertFalse(same_boundary_witness(a,b))
    def test_exact_words_restore_duration_without_rewriting(self):
        new=cue('What are you up to today?','n',69.29,70.79)
        old=dict(cue('What are you up to today?','o',68.2083,70.7917),audioStart=68.22,audioEnd=70.8,timingEvidence='word anchors')
        result,log=restore_matching_anchors([new],[old])
        self.assertEqual(result[0]['text'],new['text']);self.assertEqual(result[0]['start'],old['start']);self.assertFalse(audit(result));self.assertEqual(len(log),1)
    def test_hyphenated_one_to_one_match_restores_parent_source_group(self):
        new=cue('One-third teaspoon of salt.','n',10,11)
        old=dict(cue('One-third teaspoon of salt.','o',10,11),sourceGroup='R8',sourceText='One-third teaspoon of salt.',audioStart=10,audioEnd=11,timingEvidence='word anchors')
        result,log=restore_matching_anchors([new],[old])
        self.assertEqual(result[0]['sourceGroup'],'R8');self.assertEqual(result[0]['sourceText'],old['sourceText'])
        self.assertFalse(audit(result));self.assertEqual(len(log),1)
    def test_restored_part_keeps_parent_source_group_when_source_was_layout_split(self):
        full="Let's learn to build with our bright toolkit!"
        new=cue('Let\'s learn to build with','Q1',419.5,421.0)
        old1=dict(cue("Let's learn to build with",'R0099-S1',419.5,421.0),sourceGroup='R0099',sourceText=full,audioStart=419.5,audioEnd=421.0,timingEvidence='word anchors')
        old2=dict(cue("our bright toolkit!",'R0099-S2',421.08,422.7),sourceGroup='R0099',sourceText=full,audioStart=421.08,audioEnd=422.7,timingEvidence='word anchors')
        result,log=restore_matching_anchors([new],[old1,old2])
        self.assertEqual(result[0]['sourceGroup'],'R0099')
        self.assertEqual(result[0]['sourceText'],full)
        self.assertFalse(audit(result+[old2]))
        self.assertEqual(len(log),1)
    def test_no_lexical_substitution_from_old_caption(self):
        new=cue('Mix everything together.','n',10,12)
        old=dict(cue('Mix together.','o',10,13),audioStart=10,audioEnd=12.5,timingEvidence='word anchors')
        result,log=restore_matching_anchors([new],[old])
        self.assertEqual(result,[new]);self.assertFalse(log)
    def test_merge_phrases_preserves_every_repetition(self):
        a=cue('Whisk, whisk,','a',10,10.5);b=cue('whisk!','b',10.6,11)
        old=dict(cue('Whisk, whisk, whisk!','o',9.9,11.5),audioStart=9.9,audioEnd=11,timingEvidence='word anchors')
        result,_=restore_matching_anchors([a,b],[old]);self.assertEqual(words(result[0]['text']),['whisk']*3);self.assertFalse(audit(result))
    def test_same_words_elsewhere_are_not_matching_evidence(self):
        new=cue('Thank you!','n',60,61)
        old=dict(cue('Thank you!','o',10,12),audioStart=10,audioEnd=11.5,timingEvidence='word anchors')
        result,log=restore_matching_anchors([new],[old]);self.assertEqual(result,[new]);self.assertFalse(log)

if __name__=='__main__':unittest.main()
