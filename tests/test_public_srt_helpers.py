import csv,io,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'docs/downloads/scripts'))
from public_srt import parse
from compare_srt import compare
from review_csv import write_review
from srt_change_summary import summarize
from srt_offset_preview import preview
CUE='1\n00:00:00,500 --> 00:00:02,500\n你好。\n'
class PublicSrtHelperTests(unittest.TestCase):
    def test_pair_alignment_different_text(self):self.assertTrue(compare(CUE,CUE.replace('你好。','Hello.'))['aligned'])
    def test_pair_one_ms_difference(self):self.assertEqual(compare(CUE,CUE.replace('02,500','02,501'))['timing_mismatches'],[1])
    def test_csv_multiline_and_quote(self):
        stream=io.StringIO();write_review(CUE.replace('你好。','Hello, "you"\nNext line.'),stream);rows=list(csv.reader(io.StringIO(stream.getvalue())));self.assertEqual(rows[1][3],'Hello, "you"\nNext line.');self.assertEqual(rows[1][4],'pending');self.assertEqual(rows[1][6],'pending')
    def test_csv_formula_text_escaped(self):
        stream=io.StringIO();write_review(CUE.replace('你好。','=1+1'),stream);self.assertEqual(list(csv.reader(io.StringIO(stream.getvalue())))[1][3],"'=1+1")
    def test_summary_independent_text_and_timing(self):
        a=summarize(CUE,CUE.replace('你好。','Hello.').replace('02,500','02,501'));self.assertEqual(a['text_changed_at_positions'],[1]);self.assertEqual(a['timing_changed_at_positions'],[1])
    def test_summary_extra_cue(self):
        a=summarize(CUE,CUE+'\n2\n00:00:03,000 --> 00:00:04,000\nNext.');self.assertEqual(a['extra_after_positions'],[2])
    def test_offset_preserves_caption_and_duration(self):
        a=parse(preview(CUE,1001))[0];self.assertEqual(a['start_ms'],1501);self.assertEqual(a['end_ms'],3501);self.assertEqual(a['text'],'你好。')
    def test_negative_offset_rejected(self):
        with self.assertRaises(ValueError):preview(CUE,-501)
    def test_offset_no_in_place_change(self):self.assertEqual(preview(CUE,0),CUE)
    def test_crlf_and_bom(self):self.assertEqual(parse('\ufeff'+CUE.replace('\n','\r\n'))[0]['start_ms'],500)
    def test_bad_overlap(self):
        with self.assertRaises(ValueError):parse(CUE+'\n2\n00:00:02,000 --> 00:00:03,000\nNext.')
    def test_unrecognized_blocks_fail(self):
        with self.assertRaises(ValueError):parse(CUE+'\nunknown')
