import argparse
import io
from xml.etree import ElementTree as ET
import copy
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from library import Library
from project_policy import validate, profile
from timed_text import check
from quality_gate import report
from server import make_handler
import provider_settings

class SetupPolicyTests(unittest.TestCase):
    def test_target_rules_change_real_checks_without_mutating_legacy_state(self):
        cue={'id':'D1','start':0,'end':2,'text':'A long subtitle with thirty-eight chars.'}
        legacy={'standard':[cue],'sdh':[copy.deepcopy(cue)]}
        before=copy.deepcopy(legacy)
        self.assertIn('cps_over_17',[f for x in check([cue]) for f in x['flags']])
        adult=validate({'targetLanguage':'en-GB','platform':'amazon','audience':'adult'})
        self.assertNotIn('cps_over_20',[f for x in check([cue],profile=profile(adult)) for f in x['flags']])
        self.assertEqual(report({**legacy,**adult})['limits']['cps'],20)
        self.assertEqual(report(legacy)['limits']['cps'],17)
        self.assertEqual(legacy,before)
        self.assertEqual(profile({'subtitleSpec':'amazon_itt_children_13'})['cps'],13)

    def test_both_exports_keep_language_policy_and_source_rows(self):
        from export_bundle import bundle
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);video=root/'v.mp4';video.write_bytes(b'fixture')
            settings=validate({'targetLanguage':'en-GB','platform':'amazon','audience':'adult'})
            cue={'id':'D1','start':1,'end':3,'text':'Hello there.'}
            state={**settings,'projectSettings':settings,'standard':[cue],'sdh':[cue],'frameRate':'24'}
            raw=json.dumps(state);(root/'workbench_state.json').write_text(raw)
            data=bundle([{'id':'fixture','title':'Demo','folder':str(root),'status':'ready','video':str(video)}])
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                manifest=json.loads(z.read('manifest.json'))
                self.assertEqual(len(manifest['files']),2)
                for entry in manifest['files']:
                    self.assertEqual(entry['profile'],'amazon_itt_adult_20_220')
                    xml=ET.fromstring(z.read(entry['file']))
                    self.assertEqual(xml.attrib['{http://www.w3.org/XML/1998/namespace}lang'],'en-GB')
            self.assertEqual((root/'workbench_state.json').read_text(),raw)

    def test_runtime_endpoint_cannot_send_key_to_plain_http(self):
        with patch.dict(os.environ,{'QWEN_BASE_URL':'http://example.invalid'}):
            with self.assertRaises(ValueError):provider_settings.provider_config.base_url()

    def test_legacy_key_archive_is_detected_without_secret_readback(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'legacy.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('kit/config/team_api_key','fixture-only-value')
            with patch.object(provider_settings.provider_config,'ROOT',root),patch.dict(os.environ,{},clear=True):
                result=provider_settings.status(archive)
                self.assertTrue(result['configured'])
                self.assertEqual(result['key_source'],'legacy_archive')
                self.assertNotIn('fixture-only-value',json.dumps(result))

    def test_project_and_queued_job_keep_target_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            lib=Library(Path(temp)/'library',False)
            try:
                target={'targetLanguage':'en-GB','platform':'amazon','audience':'adult'}
                pid=lib.project('New series',target)
                video=Path(temp)/'v.mp4';video.write_bytes(b'fixture')
                eid=lib.enqueue(pid,[{'video':str(video)}])[0]
                config=json.loads((Path(lib.get(eid)['folder'])/'production_config.json').read_text())
                self.assertEqual(config['projectSettings']['targetLanguage'],'en-GB')
                self.assertEqual(config['projectSettings']['limits']['cps'],20)
                self.assertEqual(lib.snapshot()['projects'][0]['settings']['audience'],'adult')
                with self.assertRaises(ValueError):lib.project('New series',target)
                for field,value in [('targetLanguage','ko-KR'),('platform','other'),('audience','unknown')]:
                    with self.assertRaises(ValueError):lib.project('Invalid',{**target,field:value})
            finally:lib.close()

class SetupHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.lib=Library(self.root/'library',False)
        folder=self.root/'episode';folder.mkdir()
        (folder/'workbench_state.json').write_text(json.dumps({'standard':[],'sdh':[],'scope':[0,10],'frameRate':'24'}))
        video=self.root/'offline.mp4'
        args=argparse.Namespace(project=folder,video=video,sounds_csv=None,title='Fixture',library_instance=self.lib)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(args))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.env=patch.dict(os.environ,{k:v for k,v in os.environ.items() if k not in {'QWEN_API_KEY','DASHSCOPE_API_KEY','QWEN_BASE_URL','QWEN_AUDIO_MODEL','QWEN_TEXT_MODEL'}},clear=True);self.env.start()
        self.config=patch.object(provider_settings.provider_config,'ROOT',self.root);self.config.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.lib.close();self.config.stop();self.env.stop();self.temp.cleanup()
    def call(self,path,method='GET',data=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        body=json.dumps(data).encode() if data is not None else None
        conn.request(method,path,body,headers or {})
        response=conn.getresponse();result=response.status,response.read(),dict(response.getheaders());conn.close();return result
    def test_dns_rebinding_and_cross_site_reads_and_writes_are_rejected(self):
        hostile={'Host':f'evil.invalid:{self.server.server_port}','Origin':f'http://evil.invalid:{self.server.server_port}'}
        for method,path in [('GET','/api/library'),('HEAD','/video'),('POST','/api/library/projects')]:
            self.assertEqual(self.call(path,method,{'name':'Injected'} if method=='POST' else None,hostile)[0],403)
        self.assertEqual(self.call('/api/library',headers={'Sec-Fetch-Site':'cross-site'})[0],403)
        self.assertEqual(self.call('/api/health',headers={'Host':f'localhost:{self.server.server_port}'})[0],200)
    def test_provider_setup_needs_nonce_and_never_returns_key(self):
        code,raw,headers=self.call('/api/provider');data=json.loads(raw)
        self.assertEqual(code,200);self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertFalse(data['configured'])
        settings={'key':'fixture-only-value','base_url':'https://example.invalid/v1','audio_model':'audio-model','text_model':'text-model'}
        self.assertEqual(self.call('/api/provider','POST',settings,{'Content-Type':'application/json'})[0],403)
        auth={'Content-Type':'application/json','X-Config-Token':data['config_token']}
        code,raw,_=self.call('/api/provider','POST',settings,auth)
        self.assertEqual(code,200);self.assertNotIn(b'fixture-only-value',raw)
        self.assertFalse(json.loads(raw)['connection_tested'])
        secret=self.root/'config/team_api_key';self.assertEqual(secret.stat().st_mode&0o777,0o600)
        self.assertEqual(self.call('/api/provider','POST',{**settings,'base_url':'http://example.invalid'},auth)[0],400)
        self.assertEqual(secret.read_text().strip(),'fixture-only-value')
        self.assertEqual(self.call('/config/team_api_key')[0],404)

if __name__=='__main__':unittest.main()
