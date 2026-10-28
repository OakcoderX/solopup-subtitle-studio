"""Do not send truncated decoded audio as if it covered a complete interval."""
import json,math,subprocess
from pathlib import Path

def validate_duration(actual,expected,tolerance=.15):
    if not math.isfinite(actual) or actual<=0 or expected<=0 or abs(actual-expected)>tolerance:
        raise ValueError(f'Incomplete extracted original audio: expected {expected:.3f}s, decoded {actual:.3f}s; do not transcribe partial audio')

def verify_clip(path,expected):
    result=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)],text=True)
    actual=float(json.loads(result)['format']['duration'])
    validate_duration(actual,expected)
    return actual

def extract_clip(video,start,end,path):
    """A zero exit code alone is insufficient: reject decoder errors or holes."""
    log=Path(path).with_suffix('.decode.log')
    with log.open('w') as err:
        result=subprocess.run(['ffmpeg','-v','error','-ss',str(start),'-i',str(video),
            '-t',str(end-start),'-vn','-ac','1','-ar','24000','-b:a','64k','-y',str(path)],stderr=err)
    if result.returncode or log.stat().st_size:
        raise ValueError(f'Original audio extraction/decoding failed for {start:.3f}–{end:.3f}s; evidence: {log}; no provider request sent')
    return verify_clip(path,end-start)
