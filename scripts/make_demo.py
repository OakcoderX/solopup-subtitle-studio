#!/usr/bin/env python3
"""Generate redistributable synthetic test media offline; no cloud or voice claims."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    out=ROOT/'examples/demo/generated';out.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=640x360:rate=24:duration=6','-f','lavfi','-i','anullsrc=r=16000:cl=mono','-t','6','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(out/'demo.mp4')],check=True)
    print('Synthetic silent test clip:',out/'demo.mp4')
