"""Real subprocess ownership checks; no mock platform or production library."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

WORKBENCH=Path(__file__).resolve().parents[1]/'workbench'
sys.path.insert(0,str(WORKBENCH))
from library import Library

CHILD='''
import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from library import Library
try:
    lib=Library(sys.argv[2],False)
except RuntimeError as exc:
    print(str(exc),flush=True)
    sys.exit(23)
if sys.argv[3]=='probe':
    lib.close()
else:
    root=Path(sys.argv[2]);(root/'ready').touch()
    while not (root/'release').exists():time.sleep(.02)
    lib.close()
'''

class InstanceLockTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/'字幕 library'
    def tearDown(self):self.temp.cleanup()
    def command(self,mode):return [sys.executable,'-c',CHILD,str(WORKBENCH),str(self.root),mode]
    def probe(self,env=None):return subprocess.run(self.command('probe'),capture_output=True,text=True,timeout=15,env=env)
    def test_second_process_cannot_requeue_or_write_runtime(self):
        lib=Library(self.root,False)
        try:
            video=self.root/'synthetic.mp4';video.write_bytes(b'fixture')
            pid=lib.project('Fixture');eid=lib.enqueue(pid,[{'video':str(video)}])[0]
            lib.query("UPDATE episodes SET status='running' WHERE id=?",(eid,))
            runtime=self.root/'runtime.json';runtime.write_text('{}',encoding='utf-8')
            result=self.probe({**os.environ,'SDH_ALIGN_PYTHON':'synthetic-test-value'})
            self.assertEqual(result.returncode,23,result.stderr)
            self.assertIn('already open',result.stdout)
            self.assertEqual(lib.get(eid)['status'],'running')
            self.assertEqual(runtime.read_text(encoding='utf-8'),'{}')
        finally:lib.close()
        self.assertEqual(self.probe().returncode,0)
    def test_owner_normal_and_abrupt_exit_release_lock(self):
        for abrupt in (False,True):
            with self.subTest(abrupt=abrupt):
                self.root.mkdir(parents=True,exist_ok=True)
                for name in ('ready','release'):(self.root/name).unlink(missing_ok=True)
                child=subprocess.Popen(self.command('hold'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                try:
                    deadline=time.monotonic()+15
                    while not (self.root/'ready').exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.02)
                    self.assertTrue((self.root/'ready').exists(),'child failed to acquire lock')
                    self.assertEqual(self.probe().returncode,23)
                    if abrupt:child.kill() # only this synthetic test child
                    else:(self.root/'release').touch()
                    child.communicate(timeout=15)
                    self.assertEqual(self.probe().returncode,0)
                finally:
                    if child.poll() is None:child.kill()
                    child.communicate(timeout=15)
    def test_initialization_failure_releases_lock(self):
        self.root.mkdir(parents=True)
        runtime=self.root/'runtime.json';runtime.write_text('{invalid',encoding='utf-8')
        with self.assertRaises(ValueError):Library(self.root,False)
        runtime.write_text('{}',encoding='utf-8')
        with patch('library.sqlite3.connect',side_effect=OSError('synthetic init failure')):
            with self.assertRaises(OSError):Library(self.root,False)
        self.assertEqual(self.probe().returncode,0)

if __name__=='__main__':unittest.main()
