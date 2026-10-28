"""One bounded, evidence-preserving automatic repair round before publication."""
import copy,csv,json,os,re,subprocess,sys
from pathlib import Path
from repair_apply import reviewed_candidate
from timing_review import align,apply_forced
from layout_policy import prepare,resolve_long_cues,split_anchored,fit_sound_dialogue,split_internal_evidence,recover_standard_layout
from tail_room import extend_tails
from boundary_policy import repair_gaps
from sdh_track import compose
from fidelity import audit
from history import record
ROOT=Path(__file__).resolve().parents[1]

def rebuild(state,witness,forced,candidates,decisions,cuts):
 from fractions import Fraction
 rate=state.get('frameRate','24');fps=float(Fraction(str(rate)))
 base,recovered=recover_standard_layout(state['standard'],rate)
 rows,a=align(base,witness,fps);rows,b=apply_forced(rows,forced,witness,fps)
 rows,internal=split_internal_evidence(rows,forced,witness,rate)
 rows,lc=resolve_long_cues(rows,witness,rate);rows,ac=split_anchored(rows,fps)
 for c in rows:
  if c.get('timingReview')=='machine_word_matched':c['unresolved']=c.get('unresolved','').replace('时间边界尚无逐词证据，需复核。','').strip()
  else:c['timingEvidence']=''
 rows,gaps=repair_gaps(rows,rate,cuts)
 rows,ext=extend_tails(rows,cuts,rate=rate,scope_end=state['scope'][1])
 out=copy.deepcopy(state);out['standard']=rows;out['sdh']=copy.deepcopy(rows)
 # Existing groups and their transcript remain unchanged by timing/segmentation.
 out=prepare(compose(out,candidates,decisions,cuts))
 from display_repair import repair as repair_display
 from layout_policy import fit_simultaneous_dialogue
 out['standard'],standard_splits=fit_simultaneous_dialogue(out['standard'],fps)
 out['sdh'],simultaneous_splits=fit_simultaneous_dialogue(out['sdh'],fps)
 out['sdh'],display_changes=repair_display(out['sdh'],cuts,fps)
 out=prepare(out)
 if audit(out['standard'],out['sourceManifest']['standard']):raise ValueError('Repair changed transcript words')
 return out,{'exact':a,'forced':b,'splits':internal+lc+ac,'extensions':ext,'gaps':gaps,'legacy_recovery':recovered,'display_repairs':display_changes,'simultaneous_splits':simultaneous_splits,'standard_simultaneous_splits':standard_splits}

def run(video,out,state,progress,key_zip=None):
 raw=out/'repair_input.json';raw.write_text(json.dumps(state,ensure_ascii=False,indent=2));progress('targeted_repair')
 cmd=[sys.executable,str(ROOT/'workbench/repair_review.py'),'--video',str(video),'--episode',str(out),'--state',str(raw)]
 if key_zip:cmd+=['--key-zip',str(key_zip)]
 subprocess.run(cmd,check=True)
 candidate,changes=reviewed_candidate(state,sorted((out/'repair_review').glob('repair_*.json')))
 target=out/'repair_candidate.json';target.write_text(json.dumps(candidate,ensure_ascii=False,indent=2))
 (out/'repair_changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2));progress('forced_timing')
 forced=out/'forced_timing.json';runtime=os.environ.get('SDH_ALIGN_PYTHON',sys.executable)
 with (out/'forced_timing.log').open('a')as log:
  result=subprocess.run([runtime,str(ROOT/'scripts/forced_timing.py'),'--video',str(video),'--state',str(target),'--output',str(forced)],stdout=log,stderr=log)
 witness=json.loads((out/'word_timestamps.json').read_text()) if (out/'word_timestamps.json').exists() else {}
 # A failed run can leave partial data: keep evidence, but do not consume it as a completed stage.
 anchors=json.loads(forced.read_text()) if result.returncode==0 and forced.exists() else {}
 cuts=[float(x)for x in re.findall(r'pts_time:([\d.]+)',(out/'scene_changes.txt').read_text())]
 candidate,ledger=rebuild(candidate,witness,anchors,list(csv.DictReader((out/'SDH_Sound_Candidates.csv').open(encoding='utf-8-sig'))),json.loads((out/'sound_review_state.json').read_text()),cuts)
 candidate['pipeline']['targeted_repair']='completed_one_bounded_round';candidate['pipeline']['forced_alignment']='available' if anchors else 'unavailable'
 (out/'repair_timing_ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2))
 record(out,'automatic_repair_completed',state,candidate,reason='Localized audio adjudication, independent boundary checks, preserved-word formatting; unresolved findings still block delivery.')
 return candidate
