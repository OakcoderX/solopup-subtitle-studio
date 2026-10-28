"""Plan evidence-bounded tail extensions. Never alter words, starts or source anchors."""
import copy
import math
import re
from fractions import Fraction
from timed_text import frame, plain, PROFILE, word_count
from presentation import groups


def extend_tails(rows, shot_changes, rate='24', scope_end=None, minimum_only=False):
    """Return a new track and per-overlimit-cue audit; missing evidence means no edit.

    shot_changes must cover the full reviewed scope; an explicit [] means verified
    no cuts. None means unknown. Cut detection alone is not audiovisual signoff.
    The half-second cap is measured from audioEnd, never the current subtitle end.
    """
    out = copy.deepcopy(rows)
    fps = float(Fraction(str(rate)))
    floor = lambda t: math.floor(float(t) * fps + 1e-7)
    cuts = sorted(shot_changes) if shot_changes is not None else None
    audit = []
    group_caps = {c.get("id"): min(x["start"] for x in g) + PROFILE["max_seconds"]
                  for g in groups(out) if len(g)>1 for c in g}
    for i, cue in enumerate(out):
        # Non-speech labels must retain the audible event's own duration.
        if not re.sub(r'\[[^\]]*\]|\s', '', plain(cue['text'])):
            continue
        a, b = frame(cue['start'], rate), frame(cue['end'], rate)
        chars = len(' '.join(plain(cue['text']).splitlines()))
        if minimum_only and b-a >= PROFILE['min_frames']:
            continue
        if b <= a or (b-a >= PROFILE['min_frames'] and chars * fps / (b-a) <= PROFILE['cps'] + 1e-6 and word_count(cue['text'])*60*fps/(b-a)<=PROFILE['wpm']+1e-6):
            continue
        record = {'id': cue.get('id'), 'text': cue['text'], 'start': cue['start'],
                  'before_end': cue['end'], 'before_cps': round(chars*fps/(b-a), 2), 'before_wpm': round(word_count(cue['text'])*60*fps/(b-a),2), 'policy': PROFILE['id']}
        needed = a + max(PROFILE['min_frames'], math.ceil(max(chars / PROFILE['cps'], word_count(cue['text'])*60/PROFILE['wpm']) * fps - 1e-7))
        if minimum_only:
            needed = a + PROFILE['min_frames']
        limits = {'max_duration': floor(cue['start'] + PROFILE['max_seconds'])}
        if cue.get('id') in group_caps:
            limits['composite_duration'] = floor(group_caps[cue['id']])
        missing = []
        if not isinstance(cue.get('audioEnd'), (int, float)) or not cue.get('timingEvidence'):
            missing.append('audio_end_evidence_missing')
        else:
            limits['audio_tail_half_second'] = floor(cue['audioEnd'] + .5)
        if cuts is None:
            missing.append('shot_evidence_missing')
        else:
            for cut in cuts:
                if cut > cue.get('audioEnd', cue['end']):
                    limits['shot_change'] = floor(cut) - PROFILE['gap_frames']
                    break
        following = next((c for c in out[i+1:] if c.get('kind')!='sound'), None)
        if following is not None:
            limits['next_cue'] = frame(following['start'], rate) - PROFILE['gap_frames']
            if isinstance(following.get('audioStart'), (int, float)):
                limits['next_audio'] = floor(following['audioStart']) - PROFILE['gap_frames']
        if scope_end is not None:
            limits['scope_end'] = floor(scope_end)
        cap = min(limits.values())
        new_b = b if missing else max(b, min(needed, cap))
        if new_b > b:
            cue['end'] = new_b / fps
            cue['checked'] = False
            if cue.get('speedReview'):
                cue['speedReview'].update(accepted=False, invalidated=True)
            cue.setdefault('timingEdits', []).append({
                'before_end': record['before_end'], 'end': cue['end'],
                'reason': 'Use available tail room; words preserved; audiovisual review pending'})
        record.update(after_end=cue['end'], after_cps=round(chars*fps/(new_b-a), 2), after_wpm=round(word_count(cue['text'])*60*fps/(new_b-a),2),
                      added_frames=new_b-b, needed_end=needed/fps,
                      limiting_factors=missing or [k for k,v in limits.items() if v == cap],
                      limits={k: v/fps for k,v in limits.items()})
        audit.append(record)
    return out, audit
