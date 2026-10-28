import io,json,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'));sys.path.insert(0,str(ROOT/'scripts'))
from character_policy import merged_protected_names
from character_lookup import hints
from timed_text import check
from subtitle_wiki import page
class PublicContractTests(unittest.TestCase):
 def test_only_explicit_project_names_receive_merge_protection(self):
  self.assertTrue(merged_protected_names('Iris and Noah','IrisNoah',['Iris','Noah']))
  self.assertFalse(merged_protected_names('Iris and Noah','IrisNoah',[]))
 def test_name_lookup_does_not_invent_character_speech_behavior(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'names.md';p.write_text('| Name | Evidence | Variant |\n| Iris | script spelling | |\n')
   text=hints(p);self.assertIn('Iris',text);self.assertNotIn('nonverbal',text)
 def test_generic_ingredient_word_is_not_a_hardcoded_name_error(self):
  c={'id':'a','start':0,'end':3,'text':'Chamomile tea.','sourceText':'Chamomile tea.','sourceGroup':'a'}
  self.assertFalse(any('name_variant' in x['flags'] for x in check([c])))
 def test_reference_pages_are_original_summaries_with_explicit_limits(self):
  root=ROOT/'references/subtitle_wiki'
  for key in ['en','zh','ja','ko']:self.assertTrue((root/(key+'.md')).is_file())
  self.assertIn('Implementation',page(root,'/prime-style-guides').decode())
  self.assertFalse((root/'sources').exists());self.assertNotIn('/subtitle-wiki/sources/',page(root,'/prime-style-guides').decode())
 def test_manifest_contains_no_production_or_runtime_folders(self):
  manifest=json.loads((ROOT/'PORTABLE_MANIFEST.json').read_text())
  self.assertEqual(manifest['product'],'SoloPup Subtitle Studio')
  self.assertFalse(manifest['contains_project_knowledge']);self.assertFalse(manifest['contains_credentials'])
  for n in manifest['files']:
   self.assertNotIn(n.split('/')[0],{'projects','config','Subtitle_Library','Subtitle_Projects'})
   self.assertNotIn(Path(n).suffix,{'.docx','.pdf','.npz','.mp4','.sqlite3'})
