import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'))
from provider_settings import production_needs_provider,require_production_provider
class ProviderOnboardingTests(unittest.TestCase):
 def test_cloud_jobs_fail_before_queue_without_key(self):
  for policy,entries in [({'workflow':'sdh'},[{'video':'sample.mp4'}]),({'workflow':'bilingual'},[{'source_subtitles':'source.srt'}]),({'workflow':'bilingual'},[{}])]:
   self.assertTrue(production_needs_provider(policy,entries))
   with self.assertRaisesRegex(ValueError,'Qwen'):require_production_provider(policy,entries,{'configured':False})
 def test_two_subtitle_imports_need_no_key(self):
  policy={'workflow':'bilingual'};entries=[{'source_subtitles':'source.srt','target_subtitles':'target.srt'}]
  self.assertFalse(production_needs_provider(policy,entries));require_production_provider(policy,entries,{'configured':False})
 def test_key_presence_is_not_represented_as_quota_or_billing_validation(self):
  require_production_provider({'workflow':'sdh'},[{}],{'configured':True,'connection_tested':False})
 def test_guide_has_no_inference_call_or_secret_storage(self):
  code=(ROOT/'workbench/provider_onboarding.js').read_text()
  self.assertNotIn('/chat/completions',code);self.assertNotIn('localStorage',code)
  self.assertIn('qwenGuideSeen',code);self.assertIn('sessionStorage',code)
  for page in ['index.html','bilingual.html','project_hub.html']:self.assertIn('provider_onboarding.js',(ROOT/'workbench'/page).read_text())
